"""
tests 包标记文件。

sys.path 在每个测试文件头部单独设置,把项目根(本目录的上级)加入 sys.path,
这样测试可以 `from src import MarkdownEditor` 导入。
"""

# 把项目根加入 sys.path,确保 `import src` 能找到
import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)