"""
文件状态机 —— 集中管理 current_file / is_modified / 临时文件生命周期。

设计目标:
- 主体逻辑(打开/保存/新建/关闭 + 临时文件清理)从主窗口剥离
- 无 UI widget 直接依赖(弹窗用 parent=self._parent)
- 与主窗口通过回调耦合:set_content / load_content / get_content
  让主窗口决定"内容如何存 / 取 / 写入编辑器",controller 只负责流程编排
- 后续可以无 GUI 单测(controller 自身只需要 QApplication,不需要主窗口)

状态机:
    current_file: str | None
    is_modified:  bool
    _temp_file:   bool (current_file 指向『新建』产生的临时文件)

    三态:
        (None, F, F)        —— 未打开文件
        (path, *, F)        —— 真实文件(* = is_modified)
        (tmp_path, *, T)    —— 临时文件
"""

import os
import logging
import tempfile
from typing import Callable, Optional

from PyQt5.QtWidgets import QFileDialog, QMessageBox


# 临时文件名前缀(便于识别与排序)
TEMP_FILE_PREFIX = "untitled_"
TEMP_FILE_SUFFIX = ".md"


class FileController:
    """文件状态机 + 临时文件生命周期管理。

    必传回调(主窗口实现):
      - load_content(path) -> Optional[str]:
          从 path 读取文件内容,返回字符串;失败返回 None(controller 会弹错)。
      - set_content(text: str):
          把内容写入编辑器(主窗口调 self.editor.setPlainText)。
      - get_content() -> str:
          返回编辑器当前内容(主窗口调 self.editor.toPlainText())。

    可选回调:
      - on_file_changed(callable):
          current_file / _temp_file 变化后调用,主窗口用它刷新 file_label + title。
    """

    def __init__(
        self,
        parent=None,
        *,
        load_content: Callable[[str], Optional[str]],
        set_content: Callable[[str], None],
        get_content: Callable[[], str],
        on_file_changed: Optional[Callable[[], None]] = None,
    ):
        self._parent = parent
        self._load_content = load_content
        self._set_content = set_content
        self._get_content = get_content
        self._on_file_changed = on_file_changed

        # 状态
        self.current_file: Optional[str] = None
        self.is_modified: bool = False
        self._temp_file: bool = False

    # ==================== 公开 API ====================

    def new_file(self) -> bool:
        """新建临时 MD 文档:
        - 先处理上一个文件的未保存提示(_confirm_discard 会顺带清理临时文件)
        - 创建磁盘临时文件(.md 后缀、唯一名、放在系统临时目录)
        - 写入 current_file,_temp_file=True,is_modified=False
        - 默认进入编辑模式由调用方负责(此处只返回状态)

        Returns:
            True 表示成功切换到新文档,False 表示用户取消。
        """
        if not self._confirm_discard():
            return False

        # 创建磁盘临时文件
        fd, path = tempfile.mkstemp(
            suffix=TEMP_FILE_SUFFIX,
            prefix=TEMP_FILE_PREFIX,
            text=True,
        )
        os.close(fd)

        self.current_file = path
        self._temp_file = True
        self.is_modified = False
        self._set_content("")  # 清空编辑器
        self._fire_file_changed()
        return True

    def open_file_dialog(self) -> bool:
        """弹出打开对话框,加载选中的 .md 文件。
        Returns: True 成功加载,False 用户取消或加载失败。
        """
        if not self._confirm_discard():
            return False
        path, _ = QFileDialog.getOpenFileName(
            self._parent, "打开 Markdown 文件", "",
            "Markdown 文件 (*.md *.markdown *.txt);;所有文件 (*)"
        )
        if not path:
            return False
        return self.load_file(path)

    def load_file(self, path: str) -> bool:
        """把 path 加载到编辑器。临时文件(若有)会被先清理。
        Returns: True 成功,False 失败(弹 QMessageBox 报错)。
        """
        try:
            content = self._load_content(path)
        except Exception as e:
            QMessageBox.critical(self._parent, "错误", f"无法打开文件:\n{e}")
            return False
        if content is None:
            return False

        # 加载真实文件前,清掉上一个临时文件(双保险)
        self._cleanup_temp_file()

        self.current_file = path
        self._temp_file = False
        self.is_modified = False
        self._set_content(content)
        self._fire_file_changed()
        return True

    def save_file(self) -> bool:
        """保存当前文件。
        - current_file 为 None → 自动走 save_file_as
        - _temp_file 为 True   → 自动走 save_file_as(强制另存为)
        - 否则直接覆盖写入 current_file
        Returns: True 写入成功,False 用户取消或失败。
        """
        if not self.current_file or self._temp_file:
            return self.save_file_as()

        content = self._get_content()
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self._parent, "错误", f"无法保存文件:\n{e}")
            return False

        self.is_modified = False
        return True

    def save_file_as(self) -> bool:
        """另存为 —— 弹窗获取新路径,写入并转正。
        若当前是临时文件,先清掉临时文件,避免产生两份。
        Returns: True 成功,False 用户取消或失败。
        """
        path, _ = self.prompt_save_path()
        if not path:
            return False
        if not path.endswith(('.md', '.markdown')):
            path += '.md'
        return self._write_to_path(path)

    def prompt_save_path(self):
        """弹『另存为』对话框,返回 (path, filter)。
        公开方法便于测试用 monkey-patch 替换。
        """
        return QFileDialog.getSaveFileName(
            self._parent, "保存 Markdown 文件", "",
            "Markdown 文件 (*.md);;所有文件 (*)"
        )

    def close_current(self) -> bool:
        """关闭当前文件,回到未打开状态。
        Returns: True 成功关闭,False 用户取消。
        """
        if not self._confirm_discard():
            return False
        self._cleanup_temp_file()
        self.current_file = None
        self._temp_file = False
        self.is_modified = False
        self._set_content("")
        self._fire_file_changed()
        return True

    def try_close(self) -> bool:
        """程序退出前调用:处理未保存提示 + 临时文件清理。
        Returns: True 表示可关闭,False 用户取消。
        """
        return self._confirm_discard()

    # ==================== 状态查询 ====================

    def is_temp_file(self) -> bool:
        """当前 current_file 是否指向『新建』产生的临时文件。"""
        return self._temp_file and self.current_file is not None

    def has_open_file(self) -> bool:
        return self.current_file is not None

    # ==================== 展示文本 ====================

    def file_label_text(self) -> str:
        """工具栏文件名标签的展示文本。"""
        if not self.current_file:
            return "未打开文件"
        if self._temp_file:
            return "未命名"
        return os.path.basename(self.current_file)

    def window_title(self, mode: str) -> str:
        """根据当前模式与文件状态生成窗口标题。"""
        base = "Markdown Editor" if mode == "edit" else "Markdown Viewer"
        if self.is_temp_file():
            return f"{base} - 未命名"
        if self.current_file:
            return f"{base} - {self.current_file}"
        return base

    # ==================== 内部 ====================

    def _confirm_discard(self) -> bool:
        """未保存时弹 Save/Discard/Cancel 对话框。
        同时负责清理临时文件(Discard / 未脏分支)。

        Returns:
            True 表示可继续(已保存或用户确认丢弃),
            False 表示用户取消,调用方应中止后续动作。
        """
        if not self.is_modified:
            # 即使内容未变,临时文件也要清理
            self._cleanup_temp_file()
            return True
        reply = QMessageBox.question(
            self._parent, '确认',
            "文件尚未保存，是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        if reply == QMessageBox.Save:
            return self.save_file()  # 临时文件自动走另存为
        if reply == QMessageBox.Discard:
            # 用户明确丢弃 → 临时文件必须删
            self._cleanup_temp_file()
            return True
        return False  # Cancel

    def _cleanup_temp_file(self):
        """若当前指向临时文件,删除磁盘文件并复位标志。
        失败不抛异常(只记日志)。
        """
        if not self.is_temp_file():
            return
        path = self.current_file
        self._temp_file = False
        self.current_file = None
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logging.warning(f"清理临时文件失败: {path} ({e})")

    def _write_to_path(self, file_path: str) -> bool:
        """把当前编辑器内容写入 file_path(不含弹窗)。
        若当前是临时文件,先清掉临时文件,避免产生两份。
        写入成功后转正(current_file 指向新路径,_temp_file=False)。
        """
        # 保存前:如果当前是临时文件,先清掉它
        self._cleanup_temp_file()

        content = self._get_content()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self._parent, "错误", f"无法保存文件:\n{e}")
            self.current_file = None  # 回滚
            return False

        self.current_file = file_path
        self._temp_file = False
        self.is_modified = False
        self._fire_file_changed()
        return True

    def _fire_file_changed(self):
        """current_file / _temp_file 变化后通知主窗口刷新展示。"""
        if self._on_file_changed:
            try:
                self._on_file_changed()
            except Exception as e:
                logging.warning(f"on_file_changed 回调失败: {e}")