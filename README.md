# Markdown Editor(markdown file edit and review mini-tool)

一个基于 PyQt5 的 Markdown 编辑器，支持编辑模式和阅读模式。

## 功能特性

- **双模式切换**：默认阅读模式（全书预览），编辑模式（左右分栏）
- **实时预览**：编辑模式下，左侧编辑源码，右侧实时预览
- **滚动同步**：编辑框与预览框滚动位置自动同步
- **字体缩放**：工具栏滑块可调整字体大小（50%~200%）
- **文件操作**：支持打开、保存 Markdown 文件

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开文件 |
| Ctrl+S | 保存文件 |
| Ctrl+E | 切换编辑/阅读模式 |

## 项目结构

```
md_editor/
├── main.py           # 程序入口（控制台版）
├── main.pyw          # 程序入口（无控制台版）
├── md_editor.py      # 主程序
├── requirements.txt  # 依赖列表
└── UI/
    └── md_edit.ui    # Qt Designer UI 文件
```

## 安装与运行

### 1. 安装依赖

```bash
pip install PyQt5>=5.15.0
```

### 2. 运行程序

**方式一**：双击 `main.pyw` 直接运行（推荐，无控制台窗口）

**方式二**：命令行运行

```bash
cd F:\01_projects\py_proj\md_editor
python main.pyw
```

## 技术说明

- **GUI 框架**：PyQt5
- **UI 设计**：使用 Qt Designer 设计界面，存储为 `.ui` 文件
- **Markdown 解析**：内置简单的 Markdown 到 HTML 转换器（支持标题、粗体、斜体、代码块、列表等）
- **预览引擎**：使用 QTextEdit 的 HTML 渲染功能

## 界面预览

### 阅读模式
- 全屏 Markdown 预览
- 适合阅读大型文档

### 编辑模式
- 左侧：深色主题编辑器（等宽字体）
- 右侧：实时预览窗口
- 支持拖拽调整左右比例

## 系统要求

- Python 3.8+
- Windows 操作系统
- PyQt5 5.15.0+
