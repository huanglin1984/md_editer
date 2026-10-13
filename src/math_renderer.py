"""
LaTeX 数学公式渲染器 —— 把 LaTeX 源码转成 base64 编码的 PNG 嵌入 HTML。

工作流程:
    LaTeX 源码 -> 临时 .tex 文件 -> latex 编译 -> .dvi
                -> dvipng 转 PNG -> base64 编码 -> data:image/png;base64,...

设计权衡:
  - 完整 LaTeX 引擎(pdflatex/latex + dvipng)能渲染几乎所有数学语法
    (\\begin{align} 矩阵、宏、多行公式等),质量等同 VSCode KaTeX
  - 依赖外部 TeX Live(本机在 D:\\texlive\\2021\bin\win32),
    matplotlib mathtext 不支持 \\begin{...} 等高级语法
  - 缓存机制:相同公式不重复编译(LRU)
  - 失败降级:LaTeX 不可用 / 编译失败 / 公式语法错 -> 显示源码占位,
    让文档仍可读,而不是崩溃

跨平台:
  - Windows: TeX Live (MiKTeX 也可)
  - macOS:   MacTeX (/usr/local/texlive/<year>/bin)
  - Linux:   texlive 包(/usr/bin/latex / /usr/bin/dvipng)
"""

import base64
import functools
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional


# 字号命令(LaTeX 标准 10 档:从 \tiny 到 \Huge)
# 在数学模式里这些命令直接写会触发
# "LaTeX Font Warning: Command \Large invalid in math mode"
# 修复方法:从公式里剥离出来,放到 $..$ / \[..\] 外面的文本模式 group
# 注意:re 模式里 \L / \H / \l / \h 不是合法转义,用字符类规避
_SIZE_CMD_NAMES = (
    "tiny", "scriptsize", "footnotesize", "small", "normalsize",
    "large", "Large", "LARGE", "huge", "Huge",
)
_SIZE_CMD_PATTERN = re.compile(
    r"^\\(" + "|".join(_SIZE_CMD_NAMES) + r")\s*(.*)$",
    re.DOTALL,
)


# Windows 默认 texlive bin 路径(MiKTeX / texlive 都可能)
DEFAULT_TEX_BIN_CANDIDATES = [
    r"D:\texlive\2021\bin\win32",
    r"D:\texlive\2022\bin\win32",
    r"D:\texlive\2023\bin\win32",
    r"D:\texlive\2024\bin\win32",
    r"C:\texlive\2021\bin\win32",
    r"C:\texlive\2022\bin\win32",
    r"C:\texlive\2023\bin\win32",
    r"C:\texlive\2024\bin\win32",
    # macOS
    "/usr/local/texlive/2024/bin/universal-darwin",
    "/usr/local/texlive/2023/bin/universal-darwin",
    "/usr/local/texlive/2022/bin/universal-darwin",
    "/Library/TeX/texbin",
    # Linux
    "/usr/bin",
    "/usr/local/bin",
]

# LaTeX 模板:行内公式
# 注意: \Large 等字号命令必须用 group 包裹 $..$ 才生效
# {%s ... %s} 整个 group 内字号都是 Large,数学模式继承
INLINE_TEMPLATE = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{amssymb}
\pagestyle{empty}
\begin{document}
\thispagestyle{empty}
{%s\noindent $%s$}
\end{document}
"""

# LaTeX 模板:块级公式(居中 + displaymath 环境)
# 用 \[...\] 而非 $$..$$ —— 后者在跨行场景下 LaTeX 解析有歧义
# group 包裹整个 displaymath,字号命令在里面生效
BLOCK_TEMPLATE = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{amssymb}
\pagestyle{empty}
\begin{document}
\thispagestyle{empty}
\begin{center}
{%s\[%s\]}
\end{center}
\end{document}
"""

# 错误占位 HTML(LaTeX 不可用或公式语法错时显示)
INLINE_FALLBACK = '<code class="math-error" style="background:#fee;color:#c00;">$%s$</code>'
BLOCK_FALLBACK = (
    '<div class="math-error" style="background:#fee;color:#c00;'
    'border:1px solid #fcc;padding:8px;margin:8px 0;text-align:center;">'
    '$$%s$$<br><small>(公式渲染失败,显示源码)</small></div>'
)

# 块级公式成功包装(居中 + 上下边距)
BLOCK_IMG_TEMPLATE = (
    '<div class="math math-block-wrap" '
    'style="text-align:center;margin:1em 0;">'
    '<img src="data:image/png;base64,{b64}" '
    'alt="{alt}" '
    'class="math math-block" '
    'style="display:inline-block;vertical-align:middle;">'
    '</div>'
)

# 行内公式成功包装(垂直居中 + 基线对齐)
INLINE_IMG_TEMPLATE = (
    '<img src="data:image/png;base64,{b64}" '
    'alt="{alt}" '
    'class="math math-inline" '
    'style="vertical-align:middle;">'
)


class MathRenderer:
    """LaTeX 数学公式 -> base64 PNG 渲染器。

    用法::
        r = MathRenderer()            # 自动检测 latex 路径
        if r.is_available():
            html = r.render_inline("E = mc^2")
            # html 里是 <img src="data:image/png;base64,..." alt="E = mc^2">
    """

    def __init__(self, tex_bin_dir=None, dpi: int = 200):
        """tex_bin_dir: latex/dvipng 所在目录。
        - None (默认):自动检测(PATH / 常见路径)
        - "": 显式禁用(测试用,任何公式都走降级路径)
        - 其他:指定的 bin 目录
        dpi: dvipng 渲染分辨率,默认 200(平衡清晰度与 base64 大小)。
        """
        if tex_bin_dir is None:
            self._bin_dir = self._detect_tex_bin()
        elif tex_bin_dir == "":
            self._bin_dir = None
        else:
            self._bin_dir = tex_bin_dir
        self._dpi = dpi
        # LRU 缓存:(latex_source, mode) -> base64 png 字符串
        self._cache: dict = {}

    # ==================== 公开 API ====================

    def is_available(self) -> bool:
        """LaTeX 引擎是否可用(latex + dvipng 都能找到)。"""
        if not self._bin_dir:
            return False
        return (
            self._exe_ok("latex") and
            self._exe_ok("dvipng")
        )

    def render_inline(self, formula: str) -> str:
        """行内公式 LaTeX -> HTML 片段。

        Returns:
            `<img src="data:image/png;base64,..." alt="...">` 或失败占位。
        """
        return self._render(formula, mode="inline")

    def render_block(self, formula: str) -> str:
        """块级公式 LaTeX -> HTML 片段(居中块)。"""
        return self._render(formula, mode="block")

    def clear_cache(self):
        """清空 LRU 缓存(测试时有用)。"""
        self._cache.clear()

    # ==================== 内部 ====================

    def _render(self, formula: str, mode: str) -> str:
        formula = formula.strip()
        if not formula:
            return ""

        # 缓存命中
        key = (formula, mode)
        if key in self._cache:
            return self._cache[key]

        # 引擎不可用 / 渲染失败 -> 降级
        if not self.is_available():
            html = self._fallback_html(formula, mode)
            self._cache[key] = html
            return html

        try:
            png_b64 = self._compile_to_png_b64(formula, mode)
        except Exception as e:
            logging.warning(f"公式渲染失败: {formula!r} ({e})")
            html = self._fallback_html(formula, mode)
            self._cache[key] = html
            return html

        html = self._wrap_img(png_b64, formula, mode)
        self._cache[key] = html
        return html

    def _wrap_img(self, png_b64: str, formula: str, mode: str) -> str:
        """把 base64 PNG 包成 HTML:
        - 块级: <div text-align:center> + <img> 居中显示
        - 行内: <img vertical-align:middle> 与文本基线对齐
        """
        template = BLOCK_IMG_TEMPLATE if mode == "block" else INLINE_IMG_TEMPLATE
        return template.format(b64=png_b64, alt=self._escape_attr(formula))

    def _compile_to_png_b64(self, formula: str, mode: str) -> str:
        """调用 latex + dvipng 编译公式,返回 base64 PNG。"""
        template = BLOCK_TEMPLATE if mode == "block" else INLINE_TEMPLATE
        size_cmd, body = self._split_size_cmd(formula)
        # 第一个槽位填 size_cmd(可能为空),第二个填 body
        tex_source = template % (size_cmd, self._escape_tex(body))

        # 临时工作目录
        work_dir = tempfile.mkdtemp(prefix="md_math_")
        try:
            tex_file = os.path.join(work_dir, "formula.tex")
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(tex_source)

            # 步骤 1:latex 编译 -> .dvi
            self._run_exe(
                "latex",
                [
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory", work_dir,
                    tex_file,
                ],
                cwd=work_dir,
                timeout=15,
            )

            # 步骤 2:dvipng 转 PNG
            dvi_file = os.path.join(work_dir, "formula.dvi")
            if not os.path.exists(dvi_file):
                raise RuntimeError("latex 未生成 dvi 文件")
            png_file = os.path.join(work_dir, "formula.png")
            self._run_exe(
                "dvipng",
                [
                    "-D", str(self._dpi),
                    "-T", "tight",
                    "-bg", "Transparent",
                    "-o", png_file,
                    dvi_file,
                ],
                cwd=work_dir,
                timeout=15,
            )

            if not os.path.exists(png_file):
                raise RuntimeError("dvipng 未生成 png 文件")

            with open(png_file, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _run_exe(self, name: str, args: list, cwd: str, timeout: int):
        """调用外部 LaTeX 工具,捕获日志,出错抛出。"""
        exe_path = self._exe_path(name)
        if not exe_path:
            raise RuntimeError(f"{name} 不在 PATH 中")
        # Windows 上 subprocess 需要 list 传参 + shell=False
        result = subprocess.run(
            [exe_path] + args,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{name} exit={result.returncode}\n"
                f"stdout: {result.stdout[-500:]}\n"
                f"stderr: {result.stderr[-500:]}"
            )

    def _exe_path(self, name: str) -> Optional[str]:
        """获取 latex/dvipng 可执行路径,带 .exe 后缀(Windows)。"""
        if not self._bin_dir:
            return None
        exe_name = f"{name}.exe" if os.name == "nt" else name
        path = os.path.join(self._bin_dir, exe_name)
        return path if os.path.isfile(path) else None

    def _exe_ok(self, name: str) -> bool:
        return self._exe_path(name) is not None

    @staticmethod
    def _detect_tex_bin() -> Optional[str]:
        """自动检测 TeX bin 目录:先看 PATH,再遍历常见路径。"""
        # PATH 里直接有
        import shutil
        for name in ("latex", "dvipng"):
            path = shutil.which(name)
            if path:
                return os.path.dirname(path)
        # 遍历默认候选
        for d in DEFAULT_TEX_BIN_CANDIDATES:
            if (os.name == "nt"
                    and os.path.isfile(os.path.join(d, "latex.exe"))
                    and os.path.isfile(os.path.join(d, "dvipng.exe"))):
                return d
            if (os.name != "nt"
                    and os.path.isfile(os.path.join(d, "latex"))
                    and os.path.isfile(os.path.join(d, "dvipng"))):
                return d
        return None

    @staticmethod
    def _split_size_cmd(formula: str) -> tuple:
        """从公式开头剥离字号命令(\\tiny ... \\Huge),返回 (size_cmd, body)。

        LaTeX 设计上 \\Large / \\small / \\huge 等字号命令在数学模式内**无效**
        (warning: 'Command \\Large invalid in math mode')。
        但搬到 $..$ 外面的文本模式 group 内会让数学模式继承字号。

        用户写 $\\Large y = x + 2$ 时:
            传入 formula = "\\Large y = x + 2"
            返回 ("\\Large", "y = x + 2")
        模板组装后:
            {\\Large
            \\noindent $y = x + 2$
            }
        数学模式继承外层 group 的字号,渲染放大。
        """
        m = _SIZE_CMD_PATTERN.match(formula.strip())
        if m:
            # group(1) 是 \\tiny / \\Large 等(已带反斜杠,re 匹配 \\ 还原为 \)
            return "\\" + m.group(1), m.group(2).strip()
        return "", formula.strip()

    @staticmethod
    def _escape_tex(formula: str) -> str:
        """LaTeX 模板替换前转义 %(模板用 %s,公式里出现 % 会触发格式化错误)。"""
        return formula.replace("%", r"\%")

    @staticmethod
    def _escape_attr(formula: str) -> str:
        """HTML 属性值转义:& < > "。"""
        return (
            formula.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
        )

    @staticmethod
    def _fallback_html(formula: str, mode: str) -> str:
        """渲染失败时的占位 HTML,显示源码让用户能读。"""
        template = BLOCK_FALLBACK if mode == "block" else INLINE_FALLBACK
        return template % formula.replace("%", "%%")


# 模块级单例(进程内共享缓存)
_default_renderer: Optional[MathRenderer] = None


def get_default_renderer() -> MathRenderer:
    """获取默认渲染器(进程级单例)。"""
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = MathRenderer()
    return _default_renderer