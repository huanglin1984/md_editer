"""
Markdown → HTML 解析器。

主流程:
    原始 Markdown 文本
        ↓ markdown-it-py (CommonMark + GFM 兼容)
        ↓ + dollarmath 插件 (识别 $..$ / $$..$$)
        ↓ + tasklists 插件 (- [ ] / - [x])
        ↓ + footnote 插件 ([^1])
    标准 HTML 字符串
        ↓ 后处理:数学公式 → LaTeX → base64 PNG (MathRenderer)
        ↓ 后处理:代码块 → Pygments 高亮
        ↓ 后处理:图片 src → 相对路径解析
    最终 HTML(供 QTextEdit / 浏览器渲染)

设计取舍:
  - 用 markdown-it-py 而非自实现:100% CommonMark/GFM 兼容,插件生态成熟
    (dollarmath/tasklists/footnote 等),省去维护边界 case 的成本
  - 保留 math_renderer.py:LaTeX → PNG 管线仍然走本地引擎(本机有完整 TeX Live,
    比 KaTeX 支持更多语法如 \\begin{align}),markdown-it 只负责"识别",不负责"渲染"
  - 后处理用 regex 而非 token 流:简单可控,markdown-it 已经输出稳定 HTML,
    我们只需要在已知标签上做精确替换
  - 保留 markdown_to_html(text) 签名兼容:原来自实现调用的地方(test_table.py 等)
    不需要改 import 路径

依赖:
  - markdown-it-py (100% CommonMark + GFM)
  - mdit-py-plugins (dollarmath/tasklists/footnote)
  - linkify-it-py (URL 自动识别,MarkdownIt 启用 linkify 必须)
  - Pygments (代码块语法高亮,300+ 语言)
"""

import html as html_lib
import os
import re
from pathlib import Path
from typing import Optional

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.footnote import footnote_plugin

from pygments import highlight as pygments_highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from .math_renderer import get_default_renderer


# ----------------------------------------------------------------------------
# Markdown 解析器实例(模块级单例,共享渲染配置)
# ----------------------------------------------------------------------------
# 选 "gfm-like" preset:GitHub Flavored Markdown 风格,自带表格/删除线/任务列表基础支持
# 启用插件:
#   - dollarmath: 行内 $..$ / 块级 $$..$$ 公式,输出 <span class="math inline">/<div class="math block">
#   - tasklists:  - [ ] / - [x> 任务列表(checkbox)
#   - footnote:   [^1] 脚注引用
# 链接选项:
#   - html=True:    允许原始 HTML 标签通过(用户写 <details> 等能保留)
#   - linkify=True: 自动识别 URL 转链接(需 linkify-it-py)
#   - typographer=True: 智能标点(中文逗号转英文等,中文场景禁用避免误转换)
_MD = (
    MarkdownIt("gfm-like", {"html": True, "linkify": True, "typographer": False})
    .use(dollarmath_plugin)
    .use(tasklists_plugin)
    .use(footnote_plugin)
)


def markdown_to_html(text: str, file_dir: Optional[str] = None) -> str:
    """Markdown → HTML 主入口。

    Args:
        text: 原始 Markdown 文本。
        file_dir: 当前 MD 文件所在目录(用于解析图片相对路径);None 时图片原样保留。

    Returns:
        QTextEdit / 浏览器可渲染的 HTML 字符串。
    """
    html = _MD.render(text)

    # 后处理流水线(顺序很关键):
    #   1. 公式 → 必须先于代码块高亮(避免 Pygments 处理 <span class="math">)
    #   2. 代码块高亮 → 必须先于图片解析(代码块里可能有 <img> 但极少)
    #   3. 图片相对路径解析
    html = _render_math(html)
    html = _highlight_code(html)
    if file_dir:
        html = _resolve_image_paths(html, file_dir)

    return html


# ----------------------------------------------------------------------------
# 后处理 1: 数学公式 → base64 PNG
# ----------------------------------------------------------------------------
# dollarmath 插件输出格式:
#   行内: <span class="math inline">E = mc^2</span>
#   块级: <div class="math block">\int_0^1 x^2 dx\n</div>
# 我们把内容部分喂给 MathRenderer 渲染成 base64 PNG,再替换原标签。
_INLINE_MATH_RE = re.compile(
    r'<span class="math inline">(.+?)</span>',
    re.DOTALL,
)
_BLOCK_MATH_RE = re.compile(
    r'<div class="math block">\s*(.+?)\s*</div>',
    re.DOTALL,
)


def _render_math(html: str) -> str:
    """把 dollarmath 输出的 <span class="math inline">/<div class="math block">
    替换成 MathRenderer 生成的 base64 PNG <img>(/降级占位)。
    """
    renderer = get_default_renderer()

    def _inline_repl(m):
        latex = m.group(1)
        return renderer.render_inline(latex)

    def _block_repl(m):
        latex = m.group(1)
        return renderer.render_block(latex)

    # 注意:先块级后行内(块级 div 可能包含 span,但本场景不会)
    html = _BLOCK_MATH_RE.sub(_block_repl, html)
    html = _INLINE_MATH_RE.sub(_inline_repl, html)
    return html


# ----------------------------------------------------------------------------
# 后处理 2: 代码块 Pygments 高亮
# ----------------------------------------------------------------------------
# markdown-it-py 输出格式:
#   <pre><code class="language-python">code...</code></pre>
# Pygments 输出格式(默认 HtmlFormatter):
#   <div class="highlight"><pre><span class="k">def</span> ...</pre></div>
# 不能识别的语言保持原样,避免降级影响显示
_CODE_BLOCK_RE = re.compile(
    r'<pre><code class="language-(\w+)">(.+?)</code></pre>',
    re.DOTALL,
)


def _highlight_code(html: str) -> str:
    """把 <pre><code class="language-xxx">...</code></pre> 替换为 Pygments 高亮产物。"""
    def _repl(m):
        lang = m.group(1)
        # 反 HTML 转义:Pygments 期望原始代码,而 markdown-it 已转义过 < & >
        code = html_lib.unescape(m.group(2))
        try:
            lexer = get_lexer_by_name(lang)
        except ClassNotFound:
            # 未注册的语言(text / 拼错等)保持原样
            return m.group(0)
        # wrap_lines=True 让 <pre> 标签保留(QTextEdit 才能正常显示)
        return pygments_highlight(code, lexer, HtmlFormatter(wrap_lines=True))

    return _CODE_BLOCK_RE.sub(_repl, html)


def get_pygments_css(style_name: str = "monokai") -> str:
    """返回 Pygments 高亮 CSS,用于 <style> 标签注入。

    主窗口在生成完整预览文档时调,把 CSS 加到 base 样式表里。
    """
    return HtmlFormatter(style=style_name).get_style_defs(".highlight")


# ----------------------------------------------------------------------------
# 后处理 3: 图片相对路径解析
# ----------------------------------------------------------------------------
# markdown-it 输出 <img src="..." />,src 可能是:
#   - http(s)://...  → 跳过
#   - data:image/... → 跳过
#   - 绝对路径 D:/... → 已存在就用,否则原样
#   - 相对路径 ./pic.png / pic.png → 在以下位置查找(第一个匹配):
#       file_dir / pic.png
#       file_dir / images / pic.png
#       file_dir / img / pic.png
#       file_dir / assets / pic.png
#       file_dir / media / pic.png
#       file_dir / figures / pic.png
#       file_dir / 递归搜索 pic.png (大小写不敏感)
# 找到 → 转换为 file:/// 绝对 URL(QTextEdit 可加载本地文件)
# 找不到 → 原样保留(broken image)
_IMG_SRC_RE = re.compile(r'<img\s+([^>]*?)src="([^"]+)"', re.IGNORECASE)


def _resolve_image_paths(html: str, file_dir: str) -> str:
    """把 <img src=...> 的 src 转换为可加载的 file:/// 绝对 URL。"""

    def _repl(m):
        attrs = m.group(1)
        src = m.group(2)
        resolved = _resolve_image_src(src, file_dir)
        return f'<img {attrs}src="{resolved}"'

    return _IMG_SRC_RE.sub(_repl, html)


def _resolve_image_src(src: str, file_dir: str) -> str:
    """把单个图片 src 解析为可加载路径,无法解析时原样返回。"""
    # 网络图片 / data URL 跳过
    if src.startswith(("http://", "https://", "data:", "ftp://")):
        return src

    # 绝对路径:存在就用,否则原样
    if os.path.isabs(src):
        return Path(src).as_uri() if Path(src).exists() else src

    # 相对路径:按优先级搜索常见子目录
    base = Path(file_dir)
    common_subdirs = ["", "images", "img", "assets", "media", "figures", "figure"]
    for sub in common_subdirs:
        candidate = base / sub / src if sub else base / src
        if candidate.exists():
            return candidate.resolve().as_uri()

    # 兜底:递归搜索整个目录(大小写不敏感)
    src_name = Path(src).name
    for p in base.rglob(src_name):
        return p.resolve().as_uri()

    # 找不到 → 原样(QTextEdit 会显示 broken image)
    return src