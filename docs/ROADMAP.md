# md_editor 完善 Markdown 文本解析渲染功能 — 路线图建议

> 本文档基于 GitHub 类似项目调研 + 本项目现状 + 本机环境(D:\texlive\2021 已装)
> 生成于 2026-10-13。

## 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 1 | markdown-it-py + Pygments 代码高亮 + 图片相对路径解析 | ✅ 完成 (149 用例全过) |
| 阶段 2 | 主题系统 / HTML 导出 / Ctrl+F 搜索 | 待办 |
| 阶段 3 | 切到 PyQtWebEngine + KaTeX(架构级,谨慎) | 不推荐 |

---

## 一、本项目现状速览

```
md_editor/
├── src/
│   ├── markdown_parser.py   ← 自实现 regex 解析器(35+ 正则)
│   ├── preview_renderer.py  ← HTML 模板渲染
│   ├── math_renderer.py     ← LaTeX → PNG (latex + dvipng)
│   ├── recent_files.py      ← QSettings 持久化
│   ├── file_controller.py   ← 文件状态机 + 临时文件
│   └── main_window.py       ← MarkdownEditor(QTextEdit)
├── tests/ (140 用例)
└── main.py
```

**已支持**：标题 / 粗斜体 / 代码块 / 列表 / 引用 / 水平线 / 链接 / 图片 / GFM 表格 / 行内+块级 LaTeX 公式 / `\Large` 等字号命令 / 临时文件管理 / 最近打开

**渲染引擎**：QTextEdit（不支持 `<script>` + CSS 子集受限）

**LaTeX 路径**：调用本地 `latex` + `dvipng` → base64 PNG 嵌入 HTML（**完整 LaTeX 语法支持**）

---

## 二、GitHub 类似项目调研

### 主流方案对比

| 项目 | 渲染引擎 | Markdown 库 | 公式 | 代码高亮 | 主题 |
|---|---|---|---|---|---|
| **[Guilherme-alexander/markdown-editor](https://github.com/Guilherme-alexander/markdown-editor)** | PyQtWebEngine | python-markdown | KaTeX | ❌ | light/dark |
| **[caomengxuan666/QtMarkdownEditor](https://github.com/caomengxuan666/QtMarkdownEditor)** | PyQtWebEngine | python-markdown | KaTeX | ✅ | 多主题 |
| **[Zhang-Tianxu/CuteMarkEd](https://github.com/Zhang-Tianxu/CuteMarkEd)** | Qt WebEngine (C++) | Discount | MathJax | PEG Markdown | 多 |
| **[noted](https://github.com/tanthehack/noted)** | **QTextEdit** | 自实现 | ❌ | ❌ | light/dark |
| **[QuickMD](https://github.com/AhmedElkomey/QuickMD)** | Qt WebEngine | python-markdown | ❌ | ✅ Pygments | ini 配置 |

### 关键洞察

1. **主流路线**：PyQtWebEngine + python-markdown + KaTeX(CDN) → **与 VSCode/GitHub 100% 一致**
2. **本项目路线（差异化）**：QTextEdit + 自实现 parser + 本地 LaTeX 引擎 → **零网页依赖 + 完整 LaTeX 支持**
3. **parser 标准**：GitHub 上 Python Markdown 工具的**事实标准**是 [`markdown-it-py`](https://github.com/executablebooks/markdown-it-py) —— **100% CommonMark + GFM**，插件生态丰富

---

## 三、本项目路线 vs 主流路线 — 优势/劣势

| 维度 | 本项目（QTextEdit + 本地 LaTeX） | 主流（WebEngine + KaTeX） |
|---|---|---|
| 包体积 | **+0 MB**（仅 PyQt5） | +50 MB（PyQtWebEngine = Chromium 内核） |
| 离线工作 | ✅ 完全离线 | ❌ KaTeX 需 CDN 或本地打包 |
| LaTeX 兼容 | ✅ **完整**（`\begin{align}` `\begin{bmatrix}` 矩阵 / 宏 / 多行） | ❌ KaTeX 不支持 `align` 等 AMS 环境 |
| 渲染速度 | 慢（每次公式调 `latex` 子进程，~50-200ms） | 快（JS 客户端，~5ms） |
| 主题/CSS 灵活性 | ❌（QSS 子集） | ✅ 任意 CSS |
| 启动速度 | 快 | 慢（Chromium 初始化） |
| 与 VSCode 渲染一致性 | 中（自实现 parser 有边界 case） | 高（同一 markdown-it 内核） |
| 故障域 | subprocess 失败 → 公式降级占位 | Chromium 渲染崩溃 → 白屏 |

**结论**：本项目"QTextEdit + 本地 LaTeX"路线是**有意识的差异化选择**，不应盲目切到 WebEngine。建议**沿当前路线补强**。

---

## 四、按优先级排序的建议清单

### 🟢 P0 — 高价值 / 低风险

#### 1. 集成 `markdown-it-py` 替代自实现 parser ✅ **2026-10-13 已完成**

```bash
pip install markdown-it-py
```

**替换 `src/markdown_parser.py`**：
- 100% CommonMark + GFM 兼容 → 边界 case 大幅减少
- 启用插件：
  - `dollarmath` —— 行内/块级公式识别（**自动**，无需我们的 `\$...\$` regex）
  - `tasklists` —— `- [ ]` / `- [x]` 任务列表
  - `footnote` —— `[^1]` 学术引用
  - `front_matter` —— YAML frontmatter（可选）
- **与现有 `math_renderer.py` 对接**：让 markdown-it-py 输出含特殊标记的 HTML（如 `<span class="math" data-latex="...">`），`preview_renderer` 再调 LaTeX 渲染替换
- 体积 ~2 MB pip 包

**迁移路径**：
```
保留 markdown_parser.py 作为薄包装
保留 math_renderer.py 完全不动
只把核心解析逻辑换成 markdown-it-py + 插件
```

**实际收益**：
- test_table.py 用例 15 个 → 23 个（增加任务列表/脚注/代码高亮/链接等覆盖）
- 边界 case 自动符合 CommonMark 标准,不再需要手动维护
- 文件体积变化:`+2 MB`(markdown-it-py+mdit-py-plugins+Pygments+linkify-it-py)

#### 2. 代码块语法高亮（Pygments）✅ **2026-10-13 已完成**

```bash
pip install Pygments
```

**集成点**：
- 识别 `\`\`\`python` / `\`\`\`javascript` 等 fenced code block 语言
- 调用 `pygments.highlight(code, lexer, HtmlFormatter(style='monokai'))`
- 注入 Pygments CSS 到 HTML 模板（暗色用 `monokai` / 浅色用 `friendly`）
- 300+ 语言支持，零配置

#### 3. 图片相对路径解析 ✅ **2026-10-13 已完成**

当前问题：`![alt](picture.png)` 无法解析相对文件目录。

**实现**（参考 CSDN 那篇博客的 `_process_image_paths`）：
```python
def resolve_image_src(src: str, file_dir: Path) -> str:
    if src.startswith(("http://", "https://", "data:")):
        return src
    if os.path.isabs(src) and Path(src).exists():
        return Path(src).resolve().as_uri()
    # 尝试常见子目录
    for sub in ["", "images/", "img/", "assets/", "media/", "figures/"]:
        candidate = file_dir / sub / src
        if candidate.exists():
            return candidate.resolve().as_uri()
    # 递归搜索
    for p in file_dir.rglob(src):
        return p.resolve().as_uri()
    return src  # fallback:原样保留
```

**集成点**：`preview_renderer.render_preview` 接收 `file_dir` 参数，图片 src 在注入前 resolve 一次。

---

### 🟡 P1 — 高价值 / 中风险

#### 4. 主题系统（light / dark / GitHub 风格）

- 拆分 **Qt widget 样式**（QSS，给主窗口/按钮用）和 **HTML 预览样式**（CSS，给预览窗格用）
- 用户菜单切换：`视图 → 主题 → 浅色/深色/GitHub`
- CSS 文件抽到 `assets/themes/light.css` / `dark.css` / `github.css`

**风险点**：当前样式集中在 `main_window._apply_font_zoom_styles()`，需要重构为可切换的 dict。

#### 5. 导出 HTML

- 当前只能保存 .md → 加 `文件 → 导出为 HTML`
- 用 `HTMLGenerator` 整合：
  - base64 嵌入所有图片（`<img src="data:image/...">`）
  - 内联 CSS（Pygments 主题 + 用户选的主题）
  - 内联 LaTeX PNG（已经做了）
- 产物：单文件 .html，浏览器可直接打开

#### 6. 编辑器搜索（Ctrl+F）

- PyQt5 原生支持：`editor.find(text, flags)`
- 加简单的搜索条（QToolBar 顶部可折叠）
- 高亮所有匹配 + 上下导航

---

### 🔴 P2 — 低价值或架构级（**不推荐**）

#### 7. 切到 PyQtWebEngine + KaTeX

- **否决**：丢失"零网页依赖"差异化优势 + +50 MB 体积
- KaTeX 不支持 `\begin{align}` 等环境（用户当前用得很爽）
- 除非有用户明确要求"我要 VSCode 一样的渲染"

#### 8. 多文件 Tab

- **否决**：本项目定位是单文件 mini-tool，多 Tab 增加复杂度
- 如需要多文档，不如直接装 VSCode

#### 9. 侧栏文件树 / 大纲导航

- **低优**：阅读模式已经全屏预览，不缺大纲
- 如要做：用 markdown-it-py 的 token 流生成 H1/H2/H3 大纲数据即可

#### 10. 编辑器内 Markdown 语法高亮

- **中难度中价值**：用 Pygments 自定义 QSyntaxHighlighter
- 多数轻量编辑器不做（VSCode 那种级别才值得）

---

## 五、本机环境特别建议

```
D:\texlive\2021\bin\win32  ← 已装,完整 LaTeX 引擎
D:\software\miniforge3      ← conda-forge,spec 文件面向
```

- **保留 LaTeX 路径**（KaTeX 不支持 `align`/`matrix`，本机有完整 TeX Live 是差异化优势）
- `spec` 文件 `CONDA_ROOT` 已经硬编码为 `D:\software\miniforge3` → 打包时无需改
- 新增 Pygments / markdown-it-py 后，`requirements.txt` 需要更新

---

## 六、推荐实施路径

```
┌────────────────────────────────────────────────────────────────────┐
│ 阶段 1（明天 / 高价值低风险）                                       │
│   ├── 1. 集成 markdown-it-py + dollarmath + tasklists + footnote    │
│   ├── 2. Pygments 代码块高亮                                         │
│   └── 3. 图片相对路径解析                                            │
├────────────────────────────────────────────────────────────────────┤
│ 阶段 2（如有余力 / 高价值中风险）                                    │
│   ├── 4. 主题系统（light / dark / GitHub）                          │
│   ├── 5. 导出 HTML（自包含）                                        │
│   └── 6. 编辑器 Ctrl+F 搜索                                       │
├────────────────────────────────────────────────────────────────────┤
│ 阶段 3（如有用户明确要求）                                          │
│   └── 7. 切到 PyQtWebEngine + KaTeX（架构级重构，谨慎）            │
└────────────────────────────────────────────────────────────────────┘
```

---

## 七、决策点（明天可选）

1. **是否集成 markdown-it-py**？
   - 优点：CommonMark 标准、插件生态、减少边界 case
   - 缺点：放弃自实现（学习价值）、增加 2 MB 依赖

2. **Pygments 代码高亮用浅色 / 暗色 / 双主题**？
   - 建议：跟随主窗口主题自动切换（阶段 1 做简单版：固定 monokai 暗色）

3. **图片路径解析的"激进度"**？
   - 保守：只解析相对当前文件目录
   - 激进：递归搜索子目录 + 大小写不敏感（参考 CSDN 博客）
   - 建议：**激进**（用户友好）

---

## 八、参考链接

- [Guilherme-alexander/markdown-editor](https://github.com/Guilherme-alexander/markdown-editor) — WebEngine + python-markdown
- [caomengxuan666/QtMarkdownEditor](https://github.com/caomengxuan666/QtMarkdownEditor) — WebEngine + 多主题
- [Zhang-Tianxu/CuteMarkEd](https://github.com/Zhang-Tianxu/CuteMarkEd) — C++ Qt + Discount
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py) — 100% CommonMark + 插件
- [Pygments](https://pygments.org/) — Python 语法高亮标准库
- [KaTeX](https://katex.org/) — Web 端公式库（**不支持 `align` 等 AMS 环境**）
- [CSDN 从零开发 Markdown 预览器](https://blog.csdn.net/dhjabc_1/article/details/161293692) — 图片路径解析参考实现

---

**最后更新**：2026-10-13  
**当前状态**：140 用例全过，本路线"QTextEdit + 本地 LaTeX"差异化优势明显  
**下一步**：建议按阶段 1 三项推进（markdown-it-py + Pygments + 图片路径）