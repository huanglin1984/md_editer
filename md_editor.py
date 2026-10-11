"""
Markdown Editor - 基于 PyQt5 的 Markdown 编辑器，支持编辑和预览模式
从 UI/md_edit.ui 文件加载界面
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, 
                              QShortcut, QToolBar, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5 import uic
from utils.resource_path import resource_path


class MarkdownEditor(QMainWindow):
    """Markdown 编辑器主窗口"""

    def __init__(self):
        super().__init__()

        # 从 UI 文件夹加载界面
        try:
            ui_path = os.path.join(os.path.dirname(__file__), 'UI', 'md_edit.ui')
            uic.loadUi(ui_path, self)
        except:
            ui_path = resource_path('UI', 'md_edit.ui')
            uic.loadUi(ui_path, self)
        
        # 状态变量
        self.current_file = None          # 当前打开的文件路径
        self.is_modified = False           # 文件是否已修改
        self.mode = "read"                # 当前模式：read(阅读) / edit(编辑)
        self.font_zoom = 100              # 字体缩放比例 (百分比)
        self.base_font_size = 28          # 正文字体基准大小

        # 连接信号和槽
        self.setup_connections()

        # 应用样式和布局设置
        self.apply_styles()

        # 默认显示阅读模式
        self.show_read_mode()

        # 窗口最大化启动
        self.showMaximized()

    # ==================== 信号连接 ====================

    def setup_connections(self):
        """连接 UI 信号到对应的槽函数"""
        self.open_btn.clicked.connect(self.open_file)           # 打开文件按钮
        self.save_btn.clicked.connect(self.save_file)          # 保存文件按钮
        self.mode_btn.clicked.connect(self.toggle_mode)         # 模式切换按钮
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)  # 字体缩放滑块
        self.editor.textChanged.connect(self.on_text_changed)  # 编辑器内容变化
        self.editor.verticalScrollBar().valueChanged.connect(self.on_editor_scroll)
        self.edit_preview.verticalScrollBar().valueChanged.connect(self.on_preview_scroll)

        # 是否正在同步滚动（避免循环触发）
        self._syncing_scroll = False

        # 键盘快捷键
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_file)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_mode)

    # ==================== 样式设置 ====================

    def apply_styles(self):
        """应用样式表和布局边距到各个控件"""
        # 布局边距设置（在代码中设置，不在 UI 文件中）
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)      # 主布局无边距
        self.verticalLayout.setSpacing(0)                       # 主布局无间距
        self.mode_layout.setContentsMargins(0, 0, 0, 0)         # 模式容器无边距
        self.mode_layout.setSpacing(0)                           # 模式容器无间距
        self.read_layout.setContentsMargins(20, 20, 20, 20)     # 阅读模式内边距
        self.edit_layout.setContentsMargins(0, 0, 0, 0)          # 编辑模式无边距
        self.edit_layout.setSpacing(0)                            # 编辑模式无间距
        self.toolbar_layout.setContentsMargins(3, 3, 3, 3)      # 工具栏内边距
        self.toolbar_layout.setSpacing(6)                        # 工具栏元素间距

        # 将工具栏部件移动到 QToolBar
        toolbar = QToolBar()
        toolbar.setMovable(False)                                # 工具栏不可移动
        while self.toolbar_widget.layout().count():
            item = self.toolbar_widget.layout().takeAt(0)
            if item.widget():
                toolbar.addWidget(item.widget())
        self.addToolBar(toolbar)

        # 设置模式控件的尺寸策略（使控件自动填充可用空间）
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        policy.setHorizontalStretch(1)
        policy.setVerticalStretch(1)

        self.read_widget.setSizePolicy(policy)
        self.edit_widget.setSizePolicy(policy)
        self.splitter.setSizePolicy(policy)
        self.editor.setSizePolicy(policy)
        self.edit_preview.setSizePolicy(policy)
        self.mode_container.setSizePolicy(policy)

        # 设置编辑器分割器初始大小
        self.splitter.setSizes([700, 700])

        # 应用样式表
        self.read_preview.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: none;
                padding: 40px;
                font-size: 36px;
            }
        """)

        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 32px;
                line-height: 1.5;
                padding: 15px;
                border: none;
            }
        """)

        self.edit_preview.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 28px;
                padding: 15px;
                border: none;
            }
        """)

        self.file_label.setStyleSheet("color: gray; padding: 0 10px;")

    # ==================== 模式切换 ====================

    def show_read_mode(self):
        """切换到阅读模式（全屏预览）"""
        self.mode = "read"
        self.edit_widget.hide()
        self.read_widget.show()
        self.mode_btn.setText("✏️ 编辑模式")
        self.setWindowTitle("Markdown Viewer" + (f" - {self.current_file}" if self.current_file else ""))
        self.statusBar().showMessage("阅读模式")
        # 强制刷新布局
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())

    def show_edit_mode(self):
        """切换到编辑模式（左右分栏）"""
        self.mode = "edit"
        self.read_widget.hide()
        self.edit_widget.show()
        self.mode_btn.setText("📖 阅读模式")
        self.setWindowTitle("Markdown Editor" + (f" - {self.current_file}" if self.current_file else ""))
        self.statusBar().showMessage("编辑模式")
        # 强制刷新布局
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())
        self.update_preview()

    def toggle_mode(self):
        """在阅读模式和编辑模式之间切换"""
        if self.mode == "read":
            self.show_edit_mode()
        else:
            self.show_read_mode()

    # ==================== 编辑功能 ====================

    def on_text_changed(self):
        """处理编辑器内容变化"""
        self.is_modified = True
        self.update_preview()
        # 同步预览窗口滚动位置到编辑器光标位置
        self.sync_preview_scroll()

    def sync_preview_scroll(self):
        """同步预览窗口滚动位置到编辑器光标位置"""
        # 获取编辑器光标位置（行号）
        cursor = self.editor.textCursor()
        cursor_line = cursor.blockNumber()
        total_lines = self.editor.document().blockCount()
        
        if total_lines <= 1:
            return
        
        # 计算滚动条位置（百分比）
        scroll_ratio = cursor_line / max(1, total_lines - 1)
        
        # 设置预览窗口的垂直滚动条位置
        scrollbar = self.edit_preview.verticalScrollBar()
        max_value = scrollbar.maximum()
        scrollbar.setValue(int(scroll_ratio * max_value))

    def on_editor_scroll(self, value):
        """编辑器滚动时同步预览窗口"""
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        
        editor_scrollbar = self.editor.verticalScrollBar()
        preview_scrollbar = self.edit_preview.verticalScrollBar()
        
        if editor_scrollbar.maximum() > 0:
            ratio = value / editor_scrollbar.maximum()
            preview_scrollbar.setValue(int(ratio * preview_scrollbar.maximum()))
        
        self._syncing_scroll = False

    def on_preview_scroll(self, value):
        """预览窗口滚动时同步编辑器"""
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        
        preview_scrollbar = self.edit_preview.verticalScrollBar()
        editor_scrollbar = self.editor.verticalScrollBar()
        
        if preview_scrollbar.maximum() > 0:
            ratio = value / preview_scrollbar.maximum()
            editor_scrollbar.setValue(int(ratio * editor_scrollbar.maximum()))
        
        self._syncing_scroll = False

    def on_zoom_changed(self, value):
        """处理字体缩放滑块变化"""
        self.font_zoom = value
        self.zoom_label.setText(f"{value}%")

        # 根据缩放比例计算字体大小
        body_size = max(10, int(28 * value / 100))
        editor_size = max(10, int(32 * value / 100))
        preview_size = max(10, int(28 * value / 100))

        # 更新阅读模式预览样式
        self.read_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: #fafafa;
                border: none;
                padding: 40px;
                font-size: {body_size}px;
            }}
        """)

        # 更新编辑器样式
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: {editor_size}px;
                line-height: 1.5;
                padding: 15px;
                border: none;
            }}
        """)

        # 更新编辑模式预览样式
        self.edit_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: #ffffff;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: {preview_size}px;
                padding: 15px;
                border: none;
            }}
        """)

        # 刷新预览以应用新的缩放级别
        self.update_preview()
        self.update_read_preview()

    # ==================== Markdown 解析 ====================

    def update_preview(self):
        """更新编辑模式下的预览窗格"""
        markdown_text = self.editor.toPlainText()
        html_content = self.markdown_to_html(markdown_text)
        self.edit_preview.setHtml(self.get_html_template(html_content))

    def get_html_template(self, content):
        """生成用于预览的 HTML 模板（Qt 支持的 HTML 子集）"""
        body_size = max(8, int(self.base_font_size * self.font_zoom / 100))
        h1_size = max(14, int(56 * self.font_zoom / 100))
        h2_size = max(12, int(44 * self.font_zoom / 100))
        h3_size = max(11, int(36 * self.font_zoom / 100))
        return f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: {body_size}px;
                line-height: 1.6;
                color: #333;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #2c3e50;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
            h1 {{ font-size: {h1_size}px; border-bottom: 1px solid #ccc; padding-bottom: 8px; }}
            h2 {{ font-size: {h2_size}px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
            h3 {{ font-size: {h3_size}px; }}
            code {{
                background-color: #f4f4f4;
                padding: 2px 4px;
                font-family: Consolas, monospace;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 10px;
            }}
            blockquote {{
                border-left: 3px solid #ccc;
                margin-left: 0;
                padding-left: 15px;
                color: #666;
            }}
            a {{ color: #3498db; }}
            img {{ max-width: 100%; }}
            table {{
                border-collapse: collapse;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
            }}
            th {{ background-color: #f4f4f4; }}
        </style>
        </head>
        <body>
            {content}
        </body>
        </html>
        """

    def markdown_to_html(self, text):
        """简单的 Markdown 到 HTML 转换器"""
        import re

        html = text

        # HTML 转义
        html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # 标题 (# 到 h1-h6)
        html = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
        html = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # 粗体和斜体
        html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

        # 代码块（必须先于行内代码处理，否则裸 ``` 会先被 ` 反引号正则吃掉）
        html = re.sub(r'```(\w*)\n(.+?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)

        # 行内代码
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

        # 引用
        html = re.sub(r'^&gt;\s+(.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

        # 无序列表
        html = re.sub(r'^[-*]\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.+</li>\n?)+', r'<ul>\g<0></ul>', html)

        # 有序列表
        html = re.sub(r'^\d+\.\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

        # 链接
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)

        # 图片
        html = re.sub(r'!\[(.+?)\]\((.+?)\)', r'<img src="\2" alt="\1">', html)

        # 水平线
        html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)
        html = re.sub(r'^\*\*\*+$', '<hr>', html, flags=re.MULTILINE)

        # 表格解析 (GFM 风格) —— 在段落处理之前，避免表格行被包成 <p>
        html = self._convert_tables(html)

        # 段落处理
        lines = html.split('\n')
        paragraphs = []
        in_pre = False
        for line in lines:
            if '<pre>' in line:
                in_pre = True
            if '</pre>' in line:
                in_pre = False
                paragraphs.append(line)
            elif not in_pre and line.strip() and not line.startswith('<'):
                paragraphs.append(f'<p>{line}</p>')
            else:
                paragraphs.append(line)

        html = '\n'.join(paragraphs)

        # 清理空段落
        html = re.sub(r'<p>\s*</p>', '', html)

        return html

    def _convert_tables(self, text):
        """将 GFM 风格的 Markdown 表格转换为 HTML 表格

        支持的格式::

            | 列1 | 列2 |
            | --- | --- |
            | 数据1 | 数据2 |

        处理规则:
        - 表头行必须以 ``|`` 开头
        - 第二行必须是分隔符行（仅含 ``- : |`` 与空白）
        - 数据行以 ``|`` 开头，连续收集直到非表格行
        - 列数以表头为准，自动补齐或截断数据行
        - 对齐标记 ``:---`` / ``---:`` 被识别但不做样式区分（Qt 富文本不支持单元格 text-align）
        """
        import re

        lines = text.split('\n')
        result = []
        i = 0
        n = len(lines)

        # 分隔符行: 可选前导 |, 列定义 :?-+:?, 列间 |, 可选尾部 |
        sep_pattern = re.compile(
            r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$'
        )

        def parse_row(line):
            """解析单行表格为单元格列表（自动剥离首尾的 |）"""
            line = line.strip()
            if line.startswith('|'):
                line = line[1:]
            if line.endswith('|'):
                line = line[:-1]
            return [cell.strip() for cell in line.split('|')]

        while i < n:
            # 检测表格起始: 当前行以 | 开头 且 下一行匹配分隔符模式
            if (i + 1 < n
                    and lines[i].lstrip().startswith('|')
                    and sep_pattern.match(lines[i + 1])):

                headers = parse_row(lines[i])
                num_cols = len(headers)

                # 收集所有数据行（以 | 开头的连续行）
                body_rows = []
                j = i + 2
                while j < n and lines[j].lstrip().startswith('|'):
                    body_rows.append(parse_row(lines[j]))
                    j += 1

                # 构建表头
                th_cells = ''.join(f'<th>{h}</th>' for h in headers)

                # 构建表体（补齐或截断到表头列数）
                body_trs = []
                for cells in body_rows:
                    if len(cells) < num_cols:
                        cells = cells + [''] * (num_cols - len(cells))
                    else:
                        cells = cells[:num_cols]
                    td_cells = ''.join(f'<td>{c}</td>' for c in cells)
                    body_trs.append(f'<tr>{td_cells}</tr>')

                table_html = (
                    '<table>'
                    f'<thead><tr>{th_cells}</tr></thead>'
                    f'<tbody>{"".join(body_trs)}</tbody>'
                    '</table>'
                )
                result.append(table_html)
                i = j
            else:
                result.append(lines[i])
                i += 1

        return '\n'.join(result)

    def update_read_preview(self):
        """更新阅读模式的预览"""
        if self.current_file:
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                html_content = self.markdown_to_html(content)
                self.read_preview.setHtml(self.get_html_template(html_content))
            except Exception as e:
                self.read_preview.setHtml(f"<p>错误: {e}</p>")
        else:
            self.read_preview.setHtml("<p style='color: gray; text-align: center;'>请打开一个 Markdown 文件</p>")

    # ==================== 文件操作 ====================

    def open_file(self):
        """打开 Markdown 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开 Markdown 文件", "",
            "Markdown 文件 (*.md *.markdown *.txt);;所有文件 (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                self.current_file = file_path
                self.editor.setPlainText(content)
                self.update_preview()
                self.update_read_preview()

                self.file_label.setText(file_path.split('/')[-1].split('\\')[-1])
                self.setWindowTitle(("Markdown Editor" if self.mode == "edit" else "Markdown Viewer")
                                   + f" - {self.current_file}")
                self.statusBar().showMessage(f"已打开: {file_path}")
                self.is_modified = False

            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法打开文件:\n{str(e)}")

    def save_file(self):
        """保存当前文件"""
        if self.current_file:
            try:
                with open(self.current_file, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())

                self.is_modified = False
                self.statusBar().showMessage(f"已保存: {self.current_file}")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法保存文件:\n{str(e)}")
        else:
            self.save_file_as()

    def save_file_as(self):
        """另存为 - 使用新名称保存文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件", "",
            "Markdown 文件 (*.md);;所有文件 (*)"
        )

        if file_path:
            if not file_path.endswith(('.md', '.markdown')):
                file_path += '.md'

            self.current_file = file_path
            self.save_file()
            self.file_label.setText(file_path.split('/')[-1].split('\\')[-1])

    # ==================== 窗口事件 ====================

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        if self.is_modified:
            reply = QMessageBox.question(
                self, '确认',
                "文件尚未保存，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )

            if reply == QMessageBox.Save:
                self.save_file()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ==================== 程序入口 ====================

def main():
    """程序主入口"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 设置应用程序字体
    font = QFont('Segoe UI', 10)
    app.setFont(font)

    window = MarkdownEditor()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()