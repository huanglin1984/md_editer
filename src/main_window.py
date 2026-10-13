"""
MarkdownEditor 主窗口 —— 把各个模块串起来的『壳』。

职责拆分(本类只剩 UI 装配 + 信号路由):
  - 加载 .ui 文件,初始化 FileController / RecentFilesManager
  - 构建菜单 + 连接信号
  - 应用样式表
  - 模式切换(阅读 / 编辑)
  - 编辑器 ↔ 预览同步(滚动 / 文本变化)
  - 缩放滑块
  - 预览 HTML 生成(委托 preview_renderer.render_preview)
  - 关闭事件

文件 I/O 与最近打开列表走 FileController / RecentFilesManager。
Markdown 解析走 markdown_parser.markdown_to_html(由 preview_renderer 串联)。
"""

import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QShortcut, QToolBar, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5 import uic

from utils.resource_path import resource_path

from .markdown_parser import markdown_to_html
from .preview_renderer import render_markdown, render_preview
from .recent_files import RecentFilesManager
from .file_controller import FileController


class MarkdownEditor(QMainWindow):
    """Markdown 编辑器主窗口(UI 壳)。

    类属性:
      SETTINGS_ORG / SETTINGS_APP —— QSettings 命名空间,
      测试可通过覆盖这两个属性来隔离,避免污染用户真实配置。
    """

    SETTINGS_ORG = "md_editor"
    SETTINGS_APP = "md_editor"

    def __init__(self):
        super().__init__()

        # ================ UI 加载 ================
        ui_path = resource_path('UI', 'md_edit.ui')
        uic.loadUi(ui_path, self)

        # ================ 状态变量 ================
        self.mode = "read"            # 当前模式:read / edit
        self.font_zoom = 100          # 字体缩放比例(%)
        self.base_font_size = 28      # 正文字体基准大小
        self._syncing_scroll = False  # 防止滚动同步死循环

        # ================ 模块注入 ================
        self._recent = RecentFilesManager(
            org=self.SETTINGS_ORG, app=self.SETTINGS_APP,
        )
        self._files = FileController(
            parent=self,
            load_content=self._load_content_from_disk,
            set_content=self._set_editor_content_silently,
            get_content=lambda: self.editor.toPlainText(),
            on_file_changed=self._refresh_file_display,
        )

        # ================ 装配顺序 ================
        self.apply_styles()           # 样式表(字体缩放依赖此处的样式字符串拼接)
        self.setup_menu()             # 菜单(QAction 需要 menu_file / menu_recent 容器)
        self.setup_connections()      # 工具栏按钮 + 菜单 actions + 编辑器信号
        self._populate_recent_menu()  # 用最近打开列表填充 submenu
        self._refresh_file_display()  # file_label / window_title 复位

        # 默认进入阅读模式并最大化
        self.show_read_mode()
        self.showMaximized()

    # ====================================================================
    # UI 装配
    # ====================================================================

    def setup_connections(self):
        """连接工具栏按钮 / 编辑器信号 / 键盘快捷键。"""
        self.open_btn.clicked.connect(self._on_open_btn_clicked)
        self.save_btn.clicked.connect(self._on_save_btn_clicked)
        self.mode_btn.clicked.connect(self.toggle_mode)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_scroll)
        self.edit_preview.verticalScrollBar().valueChanged.connect(self._on_preview_scroll)

        # 键盘快捷键
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.new_file)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._on_open_btn_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_btn_clicked)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_mode)

    def setup_menu(self):
        """构建文件菜单。所有 QAction 用代码创建,统一管理快捷键 + 回调。"""
        self.menubar.setVisible(True)

        # 新建
        self.action_new = self.menu_file.addAction("新建(&N)")
        self.action_new.setShortcut(QKeySequence("Ctrl+N"))
        self.action_new.triggered.connect(self.new_file)

        # 打开
        self.action_open = self.menu_file.addAction("打开(&O)...")
        self.action_open.setShortcut(QKeySequence("Ctrl+O"))
        self.action_open.triggered.connect(self._on_open_btn_clicked)

        # 最近打开(子菜单 widget 在 .ui 里预置)
        self.menu_file.addAction(self.menu_recent.menuAction())

        self.menu_file.addSeparator()

        # 关闭当前
        self.action_close = self.menu_file.addAction("关闭当前(&C)")
        self.action_close.setShortcut(QKeySequence("Ctrl+W"))
        self.action_close.triggered.connect(self.close_current_file)

        self.menu_file.addSeparator()

        # 退出
        self.action_quit = self.menu_file.addAction("退出(&Q)")
        self.action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.action_quit.triggered.connect(self.close)

    def apply_styles(self):
        """应用样式表 + 布局边距 + 工具栏迁移到 QToolBar。"""
        # 布局边距
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.mode_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_layout.setSpacing(0)
        self.read_layout.setContentsMargins(20, 20, 20, 20)
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_layout.setSpacing(0)
        self.toolbar_layout.setContentsMargins(3, 3, 3, 3)
        self.toolbar_layout.setSpacing(6)

        # 把工具栏部件移到 QToolBar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        while self.toolbar_widget.layout().count():
            item = self.toolbar_widget.layout().takeAt(0)
            if item.widget():
                toolbar.addWidget(item.widget())
        self.addToolBar(toolbar)

        # 尺寸策略
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        policy.setHorizontalStretch(1)
        policy.setVerticalStretch(1)
        self.read_widget.setSizePolicy(policy)
        self.edit_widget.setSizePolicy(policy)
        self.splitter.setSizePolicy(policy)
        self.editor.setSizePolicy(policy)
        self.edit_preview.setSizePolicy(policy)
        self.mode_container.setSizePolicy(policy)

        self.splitter.setSizes([700, 700])

        # 样式表(初始,会被 on_zoom_changed 覆盖)
        self._apply_font_zoom_styles()

        self.file_label.setStyleSheet("color: gray; padding: 0 10px;")

    # ====================================================================
    # 模式切换
    # ====================================================================

    def show_read_mode(self):
        """切换到阅读模式(全屏预览)。"""
        self.mode = "read"
        self.edit_widget.hide()
        self.read_widget.show()
        self.mode_btn.setText("✏️ 编辑模式")
        self.setWindowTitle(self._files.window_title(self.mode))
        self.statusBar().showMessage("阅读模式")
        # 切到阅读模式必须刷新 read_preview,否则看到的是旧内容
        self._update_read_preview()
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())

    def show_edit_mode(self):
        """切换到编辑模式(左右分栏)。"""
        self.mode = "edit"
        self.read_widget.hide()
        self.edit_widget.show()
        self.mode_btn.setText("📖 阅读模式")
        self.setWindowTitle(self._files.window_title(self.mode))
        self.statusBar().showMessage("编辑模式")
        self._update_edit_preview()
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())

    def toggle_mode(self):
        """在阅读 / 编辑模式之间切换。"""
        if self.mode == "read":
            self.show_edit_mode()
        else:
            self.show_read_mode()

    # ====================================================================
    # 编辑器信号
    # ====================================================================

    def _on_text_changed(self):
        """编辑器内容变化 —— 标记修改 + 刷新预览 + 同步滚动。"""
        # 注意:set_content_silently 已经 blockSignals,这里只处理用户输入
        self._files.is_modified = True
        self._update_edit_preview()
        self._sync_preview_scroll_to_cursor()

    def _on_editor_scroll(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        try:
            editor_sb = self.editor.verticalScrollBar()
            preview_sb = self.edit_preview.verticalScrollBar()
            if editor_sb.maximum() > 0:
                ratio = value / editor_sb.maximum()
                preview_sb.setValue(int(ratio * preview_sb.maximum()))
        finally:
            self._syncing_scroll = False

    def _on_preview_scroll(self, value):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        try:
            preview_sb = self.edit_preview.verticalScrollBar()
            editor_sb = self.editor.verticalScrollBar()
            if preview_sb.maximum() > 0:
                ratio = value / preview_sb.maximum()
                editor_sb.setValue(int(ratio * editor_sb.maximum()))
        finally:
            self._syncing_scroll = False

    def _sync_preview_scroll_to_cursor(self):
        """把预览窗格滚动条同步到编辑器光标行。"""
        cursor = self.editor.textCursor()
        cursor_line = cursor.blockNumber()
        total_lines = self.editor.document().blockCount()
        if total_lines <= 1:
            return
        scroll_ratio = cursor_line / max(1, total_lines - 1)
        scrollbar = self.edit_preview.verticalScrollBar()
        scrollbar.setValue(int(scroll_ratio * scrollbar.maximum()))

    def on_zoom_changed(self, value):
        """缩放滑块 —— 重算三种样式 + 刷新预览。"""
        self.font_zoom = value
        self.zoom_label.setText(f"{value}%")
        self._apply_font_zoom_styles()
        self._update_edit_preview()
        self._update_read_preview()

    # ====================================================================
    # 预览渲染
    # ====================================================================

    def _update_edit_preview(self):
        """更新编辑模式右侧预览。

        file_dir 传给 render_markdown → markdown_parser → 图片相对路径解析,
        临时文件下传 None(系统 Temp 目录不适合作为图片基准)。
        """
        md_text = self.editor.toPlainText()
        file_dir = self._file_dir_for_preview()
        self.edit_preview.setHtml(render_markdown(
            md_text, self.font_zoom, self.base_font_size, file_dir=file_dir,
        ))

    def _update_read_preview(self):
        """更新阅读模式的全屏预览。
        临时文件状态从编辑器读(磁盘可能还没写);
        真实文件从磁盘读;无文件占位。
        """
        file_dir = self._file_dir_for_preview()
        if self._files.is_temp_file():
            md_text = self.editor.toPlainText()
            self.read_preview.setHtml(render_markdown(
                md_text, self.font_zoom, self.base_font_size, file_dir=file_dir,
            ))
            return
        if self._files.current_file:
            try:
                md_text = self._load_content_from_disk(self._files.current_file) or ""
            except Exception as e:
                self.read_preview.setHtml(f"<p>错误: {e}</p>")
                return
            self.read_preview.setHtml(render_markdown(
                md_text, self.font_zoom, self.base_font_size, file_dir=file_dir,
            ))
        else:
            self.read_preview.setHtml(
                "<p style='color: gray; text-align: center;'>"
                "请打开一个 Markdown 文件</p>"
            )

    def _file_dir_for_preview(self):
        """返回用于图片相对路径解析的目录。

        仅真实文件用其父目录,临时文件 / 无文件返回 None
        (系统 Temp 目录作为基准意义不大,且临时文件用户大概率不带图片)。
        """
        if self._files.current_file and not self._files.is_temp_file():
            return os.path.dirname(self._files.current_file)
        return None

    # ====================================================================
    # FileController 适配(回调 + UI 联动)
    # ====================================================================

    def _load_content_from_disk(self, path: str):
        """FileController.load_content 回调:从磁盘读文件内容。"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _set_editor_content_silently(self, text: str):
        """FileController.set_content 回调:阻断信号设置编辑器内容,避免触发 on_text_changed。"""
        self.editor.blockSignals(True)
        try:
            self.editor.setPlainText(text)
        finally:
            self.editor.blockSignals(False)

    def _refresh_file_display(self):
        """FileController.on_file_changed 回调:刷新 file_label + window_title + 双预览。

        必须同时刷新两个预览:
          - _update_read_preview:阅读模式下用户看到的全屏预览
          - _update_edit_preview:编辑模式下右侧实时预览
        否则用户切换模式前/后会看到空/旧内容,误以为『打开没生效』。
        """
        self.file_label.setText(self._files.file_label_text())
        self.setWindowTitle(self._files.window_title(self.mode))
        self._update_read_preview()
        self._update_edit_preview()

    def _on_open_btn_clicked(self):
        """工具栏打开 / 菜单打开 / Ctrl+O —— 全部走 FileController。"""
        if self._files.open_file_dialog() and self._files.current_file:
            self._recent.add(self._files.current_file)
            self._populate_recent_menu()
            self.statusBar().showMessage(f"已打开: {self._files.current_file}")

    def _on_save_btn_clicked(self):
        """工具栏保存 / 菜单保存 / Ctrl+S。"""
        before_temp = self._files.is_temp_file()
        if self._files.save_file():
            # 临时文件保存后已转正,加入最近打开
            if before_temp and self._files.current_file:
                self._recent.add(self._files.current_file)
                self._populate_recent_menu()
            self.statusBar().showMessage(f"已保存: {self._files.current_file}")
            # 刷新阅读模式预览(切过去时也能看到最新)
            self._update_read_preview()

    # ====================================================================
    # 公开便捷方法(菜单 action / 快捷键 / 工具栏)
    # ====================================================================

    def new_file(self):
        """新建临时文档,默认进入编辑模式。"""
        if self._files.new_file():
            self.show_edit_mode()
            self._update_read_preview()  # 占位就绪
            self.statusBar().showMessage(
                "已新建临时文档 - 按 Ctrl+S 另存为", 5000
            )

    def close_current_file(self):
        """关闭当前文件,回到未打开状态(不退出程序)。"""
        if self._files.close_current():
            self.show_read_mode()
            self.statusBar().showMessage("已关闭当前文件", 3000)

    def _open_recent_file(self, path: str):
        """最近打开菜单触发的打开动作。"""
        if self._files.load_file(path):
            self._recent.add(path)
            self._populate_recent_menu()
            self.statusBar().showMessage(f"已打开: {path}")
            self._update_read_preview()

    # ====================================================================
    # 最近打开菜单
    # ====================================================================

    def _populate_recent_menu(self):
        """用 RecentFilesManager.paths 重新填充 menu_recent。"""
        self.menu_recent.clear()
        paths = self._recent.paths
        if not paths:
            empty = self.menu_recent.addAction("(空)")
            empty.setEnabled(False)
            return

        for idx, path in enumerate(paths, start=1):
            label = f"&{idx}  {os.path.basename(path)}"
            act = self.menu_recent.addAction(label)
            act.setToolTip(path)
            # 用默认参数捕获,避免 lambda 闭包陷阱
            act.triggered.connect(
                lambda checked=False, p=path: self._open_recent_file(p)
            )

        self.menu_recent.addSeparator()
        clear = self.menu_recent.addAction("清空列表")
        clear.triggered.connect(self._clear_recent_files)

    def _clear_recent_files(self):
        self._recent.clear()
        self._populate_recent_menu()
        self.statusBar().showMessage("已清空最近打开列表", 3000)

    # ====================================================================
    # 字体缩放样式
    # ====================================================================

    def _apply_font_zoom_styles(self):
        """根据 font_zoom 重算三个区域的样式表字符串。"""
        body_size = max(10, int(28 * self.font_zoom / 100))
        editor_size = max(10, int(32 * self.font_zoom / 100))
        preview_size = max(10, int(28 * self.font_zoom / 100))

        self.read_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: #fafafa;
                border: none;
                padding: 40px;
                font-size: {body_size}px;
            }}
        """)
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
        self.edit_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: #ffffff;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: {preview_size}px;
                padding: 15px;
                border: none;
            }}
        """)

    # ====================================================================
    # 窗口事件
    # ====================================================================

    def closeEvent(self, event):
        if self._files.try_close():
            event.accept()
        else:
            event.ignore()


# ====================================================================
# 程序入口
# ====================================================================

def main():
    """程序主入口。"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))

    window = MarkdownEditor()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()