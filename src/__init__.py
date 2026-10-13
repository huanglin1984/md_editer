"""
md_editor 核心代码包。

公开 API:
  - MarkdownEditor: 主窗口类
  - main():          程序入口(供 main.py 调用)

模块拆分:
  - markdown_parser: 纯函数 Markdown → HTML(无 Qt 依赖)
  - preview_renderer: 预览 HTML 模板渲染
  - recent_files:    最近打开列表管理(RecentFilesManager)
  - file_controller: 文件状态机(FileController)
  - main_window:     MarkdownEditor 主类(UI 壳)
"""

from .main_window import MarkdownEditor, main

__all__ = ["MarkdownEditor", "main"]