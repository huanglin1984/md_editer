# Markdown Editor

一个基于 **PyQt5** 的 Markdown 桌面编辑器,支持**编辑模式**与**阅读模式**实时切换。
内置轻量 Markdown → HTML 解析器(含 GFM 表格),开箱即用、单文件即可分发。

![mode](https://img.shields.io/badge/PyQt5-5.15%2B-blue) ![py](https://img.shields.io/badge/Python-3.8%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green)

---

## ✨ 功能特性

- **双模式切换**:阅读模式(全屏沉浸式预览)/ 编辑模式(左右分栏),`Ctrl+E` 一键切换
- **新建临时文档**:`Ctrl+N` 在系统临时目录创建真实的 `.md` 文件,**默认进入编辑模式**;保存时自动走"另存为"对话框,放弃/关闭时**自动清理临时文件,不污染磁盘**
- **文件菜单**:新建 / 打开 / **最近打开(8 个,跨会话持久化)** / 关闭当前 / 退出
- **实时预览**:编辑左侧源码,右侧实时渲染;阅读模式全屏呈现整篇文档
- **滚动同步**:编辑框与预览框的垂直滚动位置**双向同步**,带防回环标志
- **字体缩放**:工具栏滑块 50% ~ 200%,实时作用于阅读模式 / 编辑器 / 预览三个区域
- **文件操作**:新建 / 打开 / 保存 / **另存为** Markdown 文件;**关闭前自动提示未保存内容**
- **GFM 表格**:支持 GitHub Flavored Markdown 表格语法,自动补齐或截断列数
- **轻量解析器**:零外部 Markdown 依赖,自实现的 `markdown_to_html` 内嵌于主类
- **跨会话配置**:最近打开列表通过 `QSettings` 持久化(Windows 注册表 / macOS plist / Linux ini)

---

$$
\Large
\sum_{i=1}^{n} i = \frac{n(n+1)}{2} 
$$
---
## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建 MD 文档(临时文件,默认编辑模式) |
| `Ctrl+O` | 打开 Markdown 文件 |
| `Ctrl+S` | 保存当前文件(临时文件上自动另存为) |
| `Ctrl+E` | 切换编辑 / 阅读模式 |
| `Ctrl+W` | 关闭当前文件(不退出程序) |
| `Ctrl+Q` | 退出程序 |

> 最近打开列表里的条目带有 `&1` ~ `&8` 数字加速键,按 `Alt+R` 打开后可直接 `Alt+数字` 选中。

---

## 📦 项目结构

```
md_editer/
├── main.py                  # 程序入口:日志初始化 + 异常钩子 + Windows 控制台隐藏
├── src/                     # 核心代码(已按职责拆分,便于扩展)
│   ├── __init__.py          # 公开 API: from src import MarkdownEditor
│   ├── markdown_parser.py   # 纯函数 Markdown → HTML(无 Qt 依赖,含 LaTeX 公式识别)
│   ├── preview_renderer.py  # 预览 HTML 模板渲染
│   ├── recent_files.py      # 最近打开列表(RecentFilesManager)
│   ├── file_controller.py   # 文件状态机(FileController) + 临时文件生命周期
│   ├── math_renderer.py     # LaTeX → base64 PNG(MathRenderer,可选依赖)
│   └── main_window.py       # MarkdownEditor 主类(UI 壳,委托给 controller)
├── utils/
│   └── resource_path.py     # dev / 打包后的资源路径适配
├── UI/
│   └── md_edit.ui           # Qt Designer 设计的界面文件
├── tests/                   # 测试套件(从根目录迁移)
│   ├── __init__.py          # 把项目根加入 sys.path
│   ├── test_table.py        # 23 个 CommonMark + GFM + 任务列表/脚注/代码高亮用例
│   ├── test_e2e.py          # Qt offscreen 真实渲染 E2E 测试
│   ├── test_math.py         # 30 个 LaTeX 公式解析 + 渲染 + 缓存 + 降级用例
│   └── test_menu.py         # 87 个菜单 + 临时文件 + 预览切换的功能用例
├── MD_editer.spec           # PyInstaller onedir 打包配置(conda-forge 兼容)
├── requirements.txt         # 仅依赖 PyQt5>=5.15.0
├── LICENSE                  # MIT
├── logs/                    # 按天滚动日志目录(运行后自动生成,保留 7 天)
└── .vscode/                 # launch.json + settings.json(可选)
```

> **关于 `main.pyw`**:旧版 README 提到的"无控制台入口"并不以独立文件存在 —— `main.py` 内部通过
> `ctypes.windll.kernel32 / user32` 在 Windows 上隐藏控制台窗口,无需额外 `.pyw` 双版本。

---

## 🚀 安装与运行

### 1. 准备环境

```bash
# 推荐 Python 3.8+
pip install -r requirements.txt
# 等价写法: pip install "PyQt5>=5.15.0"
```

### 2. 运行程序

```bash
python main.py
```

启动后:

- 自动创建 `logs/` 日志目录(控制台 INFO + 文件 DEBUG,按天滚动保留 7 天)
- 启动横幅打印 Python / Qt / PyQt5 版本到日志
- 默认进入**阅读模式**并**最大化窗口**

> Windows 下控制台窗口会被自动隐藏;若想查看调试日志,直接打开 `logs/md_editor_YYYY-MM-DD.log`。

---

## 🧪 测试

仓库自带两层测试,**无需手工启动 GUI**:

```bash
# 1) CommonMark + GFM 解析测试 —— 23 个用例,涵盖表格对齐/空单元格/列数不匹配/
#    任务列表/脚注/代码块高亮/链接/图片等
python tests/test_table.py

# 2) Qt 真实渲染端到端测试 —— 使用 QT_QPA_PLATFORM=offscreen 启动无头 Qt,
#    验证 edit_preview.toHtml() 产出的富文本 DOM 是否包含正确属性
python tests/test_e2e.py

# 3) LaTeX 公式测试 —— 30 个用例,验证语法识别 + 真实 LaTeX 渲染 +
#    LRU 缓存 + 降级路径。未装 LaTeX 时仍可跑(降级用例单独测)。
python tests/test_math.py

# 4) 菜单 + 最近打开 + 临时文件 + 预览切换测试 —— 87 个用例,验证 actions /
#    快捷键 / QSettings 持久化 / new_file 创建临时文件 / save_file_as 清理
#    临时文件 / 工具栏保存完整路径 / 临时文件输入后切阅读模式 / 保存后切阅读模式 /
#    _file_label_text / _window_title 三态分支
#    通过类属性 SETTINGS_ORG / SETTINGS_APP 隔离,不会污染真实配置
python tests/test_menu.py
```

---

## 📦 打包发布(PyInstaller)

```bash
pyinstaller MD_editer.spec
```

打包配置要点:

- **onedir 模式**(`COLLECT` 段):产物为 `dist/MD_editer/` 目录
- **conda-forge 兼容**:自动从 `D:\software\miniforge3` 收集 `libffi` 等 DLL,按本机路径修改 `CONDA_ROOT`
- **无控制台**(`console=False`):等同 `pyinstaller -w`
- **post-build**:spec 末尾的 Python 代码会把 `_internal/UI/` 目录搬回顶层,避免双层 `UI` 路径

---

## 🔧 Markdown 支持一览

| 语法 | 支持 | 备注 |
|------|:---:|------|
| 标题 `#` ~ `######` | ✅ | h1 ~ h6 |
| 粗体 `**text**` / `__text__` | ✅ | |
| 斜体 `*text*` / `_text_` | ✅ | |
| 粗斜体 `***text***` | ✅ | |
| 行内代码 `` `code` `` | ✅ | |
| 代码块 ` ```lang ... ``` ` | ✅ | 必须先于行内代码处理(源码已保证) |
| 无序列表 `- item` / `* item` | ✅ | 自动包 `<ul>` |
| 有序列表 `1. item` | ✅ | |
| 引用 `> text` | ✅ | |
| 水平线 `---` / `***` | ✅ | |
| 链接 `[text](url)` | ✅ | |
| 图片 `![alt](src)` | ✅ | |
| **GFM 表格** | ✅ | `:` / `---` 对齐标记转 `style="text-align:..."` 属性 |
| **任务列表** `- [ ]` / `- [x]` | ✅ | 渲染为 checkbox(input 禁用) |
| **脚注** `[^1]` | ✅ | 学术文档常用 |
| **代码块高亮** `\`\`\`python` | ✅ | Pygments 引擎,300+ 语言,默认 monokai 主题 |
| **数学公式** `$x$` / `$$x$$` | ✅ | 调用本地 LaTeX 引擎 → `latex` 编译 + `dvipng` 转 PNG → base64 嵌入 HTML |
| 删除线 `~~text~~` | ❌ | 当前未实现 |

> 解析器基于 [markdown-it-py](https://github.com/executablebooks/markdown-it-py) (100% CommonMark + GFM 兼容),通过 `mdit-py-plugins` 启用 dollarmath / tasklists / footnote,后处理接入 Pygments 代码高亮 + 图片相对路径解析。复杂文档建议导出后用专业 Markdown 工具渲染。

---

## 🏗️ 架构设计要点

1. **入口分层**:`main.py` 只做基础设施(日志、异常钩子、控制台隐藏),GUI 主循环在 `src.main_window.main()`。
2. **资源路径**:`resource_path()` 通过 `sys.frozen` 区分开发模式与 PyInstaller 打包后的 exe 同级目录;dev 模式 base = utils/ 的上级 = 项目根。
3. **模块拆分**:核心代码在 `src/` 包,5 个模块各司其职:`markdown_parser`(纯函数) / `preview_renderer`(HTML 模板) / `recent_files`(持久化) / `file_controller`(文件状态机 + 临时文件) / `main_window`(UI 壳 + 信号路由)。
4. **FileController 中心化**:current_file / is_modified / _temp_file 状态机 + 临时文件生命周期全部在 `FileController` 里,主窗口只负责 UI 联动(load_content / set_content / get_content 三个回调把编辑器接入 controller)。
5. **RecentFilesManager 独立**:`QSettings` 持久化、去重、上限、死链过滤都封装,主窗口只调 `add(path)` / `clear()` / `paths`。
6. **样式策略**:所有 QSS 集中在 `MarkdownEditor._apply_font_zoom_styles()`;字体缩放时仅重建样式表字符串,不重建控件。
7. **滚动同步**:用 `_syncing_scroll` 标志位防止 valueChanged 信号互相触发形成死循环。
8. **表格解析**:`_convert_tables` 在 `markdown_to_html` 的**段落处理之前**调用,避免被 `<p>` 包裹。
9. **菜单骨架 + 代码填充**:Qt Designer 只保留 `menu_file` / `menu_recent` 两个空 widget,所有 actions 在 `setup_menu()` 里用代码创建并 connect,统一管理快捷键。
10. **配置隔离**:`QSettings` 的 org/app 通过 `MarkdownEditor.SETTINGS_ORG / SETTINGS_APP` 类属性暴露,测试可覆盖而不污染用户配置;`RecentFilesManager` 接受 org/app 作为构造参数,主窗口把类属性透传。
11. **死链自动清理**:`RecentFilesManager._load` 用 `os.path.isfile` 过滤掉磁盘上已删除的条目。
12. **临时文件语义**:`FileController.new_file()` 创建磁盘真实临时文件(`untitled_xxx.md` in 系统 Temp),让编辑器内 `textChanged` 信号走真实路径;`save_file_as()` 内部清理临时文件并把 `current_file` 切到用户命名的新路径。
13. **临时文件清理责任**:`FileController._cleanup_temp_file` 集中处理删除磁盘文件 + 复位标志,在 `_confirm_discard` 的 Discard 分支、未修改分支、`close_current`、`load_file`、`save_file_as` / `_write_to_path` 等多处调用,保证不会留下垃圾临时文件。
14. **测试 Mock 友好**:`FileController.save_file_as` 调 `self.prompt_save_path()`(公开方法),测试只 `win._files.prompt_save_path = lambda: ...` 就能完整覆盖清理与转正逻辑。
15. **临时文件预览不走磁盘**:新建产生的临时文件在用户输入字符时**不会**实时同步到磁盘(避免每次按键 I/O),因此 `_update_read_preview` 在 `is_temp_file()` 状态下从 `editor.toPlainText()` 读取最新内容,不依赖磁盘;`show_read_mode` 切换时主动调用 `_update_read_preview` 保证 read_preview 总是当前状态的渲染(保存/重打开都不需要)。
16. **文件切换必须同时刷新双预览**:FileController 通过 `_fire_file_changed()` 通知主窗口,主窗口 `_refresh_file_display` 必须**同时**调 `_update_read_preview()` 和 `_update_edit_preview()` —— 否则用户在阅读模式下打开文件会看到空预览(只有切模式后才刷新),误以为「打开失效」。
17. **LaTeX 公式渲染管线**:`MathRenderer` 用 `latex` + `dvipng` 把 LaTeX 转 base64 PNG → 嵌入 HTML `<img>`;`markdown_parser` 在代码块处理之后、引用/列表/链接之前做公式识别(占位符保护代码块免被 `$` 误识别);渲染失败(LaTeX 不可用 / 语法错)走降级 HTML 显示源码,文档仍可读。
18. **LaTeX 自动检测**:`MathRenderer._detect_tex_bin` 先查 PATH,再遍历 `DEFAULT_TEX_BIN_CANDIDATES`(覆盖 TeX Live 2021/2022/2023/2024、MacTeX、Linux texlive),自动找到本机引擎;测试通过 `tex_bin_dir=""` 显式禁用自动检测走降级路径。

---

## 🖼️ 界面说明

- **工具栏**(可移动 = false):打开 · 保存 · 模式切换 · 文件名标签 · 缩放滑块 · 缩放百分比
- **阅读模式**:浅灰背景 `#fafafa`,40px 内边距,大字号正文字体
- **编辑模式**:左侧深色 `#1e1e1e` + Consolas 等宽字体,右侧白色背景 + 微软雅黑 / Segoe UI

---

## 🛠️ 系统要求

| 项 | 要求 |
|----|------|
| Python | 3.8+ |
| 操作系统 | Windows / macOS / Linux(界面针对 Windows 设计) |
| PyQt5 | 5.15.0+ |
| **LaTeX**(仅数学公式)| 可选。Windows:MiKTeX / TeX Live;macOS:MacTeX;Linux:texlive 包 |
| 磁盘 | < 50 MB(PyInstaller 打包后) + LaTeX 引擎(~200 MB ~ 5 GB) |

---

## 📄 许可证

[MIT License](LICENSE) © 2026 huanglin1984