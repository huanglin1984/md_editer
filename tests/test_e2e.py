"""
端到端验证:Qt 实际渲染产出的富文本表格结构是否正确。
判断标准改用属性存在性(border/cellspacing/cellpadding/bgcolor),
而非字面子串(Qt 会改写标签)。
"""
import os
import sys

# Windows PowerShell 默认 GBK 编码不支持 emoji
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import warnings
warnings.filterwarnings("ignore")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication
from src import MarkdownEditor

app = QApplication(sys.argv)
win = MarkdownEditor()

sample = """# 表格测试

| 姓名 | 分数 | 等级 |
| :--- | ---: | :---: |
| 张三 | 95 | A |
| 李四 | 87 | B |
| 王五 | 72 | C |

代码块:

```python
def hello():
    print("world")
```
"""

# 直接 setPlainText 让 on_text_changed 自动触发 _update_edit_preview
# (blockSignals 会跳过预览刷新,而 e2e 不在乎 is_modified 副作用)
win.editor.setPlainText(sample)
QCoreApplication.processEvents()
html = win.edit_preview.toHtml()

# Qt 重写后的标签特征
checks = {
    "有 <table> 元素":      "<table" in html,
    "有 <thead>":            "<thead>" in html,
    "有 3 行 <tr> (1 表头 + 2 数据)": html.count("<tr>") >= 3,
    "表头底色 #f4f4f4":      "#f4f4f4" in html,           # 来自模板 th { background-color }
    "姓名出现":              "姓名" in html,
    "张三出现":              "张三" in html,
    "李四出现":              "李四" in html,
    "王五出现":              "王五" in html,
    "表格带边框属性":        'border=' in html or 'border-' in html,
}

ok = all(checks.values())
print("Qt 渲染结构检查:")
for k, v in checks.items():
    print(f"  {'✅' if v else '❌'} {k}")
print(f"\n端到端: {'✅ PASS' if ok else '❌ FAIL'}")

sys.exit(0 if ok else 1)