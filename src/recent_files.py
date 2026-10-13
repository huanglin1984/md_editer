"""
最近打开文件列表管理。

把 QSettings 的读/写/去重/上限/死链过滤都封装进 RecentFilesManager,
主窗口只需要 add(path) / clear() / 拿到当前 paths 列表即可刷新菜单。

特性:
- 跨会话持久化(QSettings:Windows 注册表 / macOS plist / Linux ini)
- 自动去重 + LIFO 顺序
- 上限 DEFAULT_RECENT_FILES_LIMIT (8)
- 加载时过滤磁盘上已删除的条目(死链清理)
- 跨平台 list 落盘格式兼容(str / binary)
"""

import os
from PyQt5.QtCore import QSettings


# 默认上限(可被实例参数覆盖)
DEFAULT_RECENT_FILES_LIMIT = 8


class RecentFilesManager:
    """最近打开文件列表的状态机 + 持久化。

    用法::
        mgr = RecentFilesManager(org="md_editor", app="md_editor")
        for path in mgr.paths:
            print(path)
        mgr.add(r"D:/notes/hello.md")
        mgr.clear()
    """

    def __init__(
        self,
        org: str = "md_editor",
        app: str = "md_editor",
        limit: int = DEFAULT_RECENT_FILES_LIMIT,
    ):
        self._settings = QSettings(org, app)
        self._limit = limit
        self._paths = self._load()

    # ==================== 公开 API ====================

    @property
    def paths(self) -> list:
        """当前最近打开列表(返回副本,外部修改不影响内部状态)。"""
        return list(self._paths)

    @property
    def limit(self) -> int:
        return self._limit

    def add(self, path: str):
        """把 path 加到列表头部(去重),超过上限丢弃尾部,立即写 QSettings。"""
        if not path:
            return
        path = os.path.abspath(path)
        # 去重:若已存在则移到最前
        self._paths = [p for p in self._paths if p != path]
        self._paths.insert(0, path)
        self._paths = self._paths[:self._limit]
        self._save()

    def clear(self):
        """清空列表,立即写盘。"""
        self._paths = []
        self._save()

    # ==================== 内部 ====================

    def _load(self) -> list:
        """从 QSettings 读 + 过滤死链 + 截断到上限。"""
        raw = self._settings.value("recent_files", [])
        # 某些 Qt 平台上 QSettings 会把 list 存回字符串
        if isinstance(raw, str):
            raw = [r for r in raw.split("\n") if r]
        if not isinstance(raw, list):
            raw = []
        # 只保留存在的文件(死链清理)
        return [p for p in raw[:self._limit] if p and os.path.isfile(p)]

    def _save(self):
        """写回 QSettings。"""
        self._settings.setValue("recent_files", self._paths)
        self._settings.sync()