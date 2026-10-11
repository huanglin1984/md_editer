"""
Markdown Editor 程序入口
运行方式: python main.py

日志策略:
    - 控制台 (stderr) + 文件双输出
    - 文件位于 ./logs/, 按天滚动, 保留最近 7 天
    - 安装全局 excepthook, 捕获未处理异常并落盘
    - 启动时打印 Python / Qt / PyQt5 环境横幅
"""

import sys
import os
import logging
import logging.handlers
import platform
from datetime import datetime
from pathlib import Path


# ==================== 日志配置 ====================
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """初始化根日志。控制台 INFO+, 文件 DEBUG+。

    注意: setup_logging 可能在 reload 场景下被重复调用,
    这里清空已有 handler 防止重复注册。
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 1) 控制台 handler (stderr): INFO 及以上
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    # 2) 文件 handler: DEBUG 及以上, 按天滚动, 保留 7 天
    log_file = LOG_DIR / f"md_editor_{datetime.now():%Y-%m-%d}.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",      # 每天 0 点切分
        interval=1,
        backupCount=7,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return root


logger = setup_logging()


# ==================== 启动横幅 ====================
logger.info("=" * 60)
logger.info("Markdown Editor 启动")
logger.info(f"  Python:   {platform.python_version()}")
logger.info(f"  平台:     {platform.platform()}")
logger.info(f"  工作目录: {os.getcwd()}")
logger.info(f"  日志目录: {LOG_DIR}")
try:
    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    logger.info(f"  Qt:       {QT_VERSION_STR}")
    logger.info(f"  PyQt5:    {PYQT_VERSION_STR}")
except Exception as e:
    logger.warning(f"Qt/PyQt 版本探测失败: {e}")
logger.info("=" * 60)


# ==================== 全局异常钩子 ====================
def _excepthook(exc_type, exc_value, exc_tb):
    """未捕获异常 → 写日志 + 调用默认 excepthook 打印 traceback。"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Ctrl+C 不算异常, 走默认处理 (干净退出)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook


# ==================== Windows 控制台隐藏 ====================
if os.name == 'nt':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hWnd = kernel32.GetConsoleWindow()
        if hWnd:
            user32.ShowWindow(hWnd, 0)
            user32.SetWindowPos(hWnd, 0, 0, 0, 0, 0, 0x0080 | 0x0001 | 0x0002)
        logger.debug("Windows 控制台已隐藏")
    except Exception as e:
        logger.warning(f"隐藏控制台失败: {e}", exc_info=True)


# ==================== 项目模块导入 ====================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_editor import main  # noqa: E402


if __name__ == '__main__':
    logger.info("调用 md_editor.main() 进入 Qt 事件循环")
    try:
        main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
        logger.info(f"Qt 事件循环退出, exit code = {code}")
        raise  # 让 sys.exit 正常生效 (决定进程退出码)