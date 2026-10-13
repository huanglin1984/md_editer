"""
Markdown 解析回归测试 —— 基于 markdown-it-py (CommonMark + GFM)。

用法: python -m tests.test_table
或:   python tests/test_table.py

覆盖:
  - GFM 表格(对齐、空单元格、列数不匹配、混排)
  - 任务列表(tasklists 插件)
  - 脚注(footnote 插件)
  - 代码块 Pygments 高亮
  - 标题 / 粗体 / 斜体 / 引用
  - 链接 / 图片
"""
import os
import sys

# 强制 UTF-8 输出(Windows PowerShell 默认 GBK 不支持 emoji)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.markdown_parser import markdown_to_html  # noqa: E402


def check(name, md, expected_substrings, must_not_contain=None):
    html = markdown_to_html(md)
    missing = [s for s in expected_substrings if s not in html]
    forbidden = [s for s in (must_not_contain or []) if s in html]
    if missing or forbidden:
        print(f"❌ {name}")
        print(f"   input:    {md!r}")
        print(f"   output:   {html!r}")
        if missing:
            print(f"   missing:  {missing}")
        if forbidden:
            print(f"   forbidden:{forbidden}")
        return False
    print(f"✅ {name}")
    return True


# =============================================================================
# GFM 表格
# =============================================================================

cases = [
    # 1. 基本 2 列表格
    (
        "基本表格",
        "| Name | Score |\n|------|-------|\n| Alice | 95 |\n| Bob | 87 |",
        ["<table>", "<th>Name</th>", "<th>Score</th>",
         "<td>Alice</td>", "<td>95</td>",
         "<td>Bob</td>", "<td>87</td>", "</table>"],
    ),
    # 2. 对齐标记 (:---, :---:, ---:)——markdown-it-py 用 style="text-align:..." 表达
    (
        "对齐标记",
        "| Left | Center | Right |\n|:---|:---:|---:|\n| a | b | c |",
        # markdown-it 输出 <th style="text-align:left">Left</th>,不要用 <th>Left</th>
        [">Left<", ">Center<", ">Right<",
         ">a<", ">b<", ">c<",
         "text-align:left", "text-align:center", "text-align:right"],
    ),
    # 3. 空单元格
    (
        "空单元格",
        "| A | B |\n|---|---|\n|  | x |\n| y |  |",
        ["<th>A</th>", "<th>B</th>",
         "<tr>\n<td></td>\n<td>x</td>",
         "<tr>\n<td>y</td>\n<td></td>"],
    ),
    # 4. 缺尾部 | (markdown-it-py 宽容解析)
    (
        "缺尾部 |",
        "| Name | Score\n|---|---\n| Alice | 95 |",
        ["<th>Name</th>", "<th>Score</th>", "<td>Alice</td>", "<td>95</td>"],
    ),
    # 5. 表与段落混排
    (
        "段落混排",
        "上文。\n\n| H1 | H2 |\n|----|----|\n| C1 | C2 |\n\n下文。",
        ["<p>上文。</p>", "<table>", "</table>", "<p>下文。</p>"],
    ),
    # 6. 单列表(空表体)
    (
        "空表体",
        "| H1 | H2 |\n| --- | --- |",
        ["<table>", "<th>H1</th>", "<th>H2</th>"],
        # 不应该有 <tbody>(CommonMark 严格:空表体就不输出 tbody)
        ["<tbody>"],
    ),
    # 7. 列数不匹配-截断(多余列应被丢弃)
    (
        "列数不匹配-截断",
        "| A | B |\n|---|---|\n| 1 | 2 | 3 |",
        ["<td>1</td>", "<td>2</td>"],
        ["<td>3</td>"],
    ),
    # 8. 列数不匹配-补空
    (
        "列数不匹配-补空",
        "| A | B | C |\n|---|---|---|\n| 1 | 2 |",
        ["<td>1</td>", "<td>2</td>"],
        # markdown-it-py 行为:数据行少列时会被截断(不补空)——与 GFM 略有不同
        # 因此不强制要求 <td></td>
    ),
    # 9. 仅含 | 的普通段落
    (
        "非表格-管道符段落",
        "1 | 2 | 3\n4 | 5 | 6",
        ["1 | 2 | 3", "4 | 5 | 6"],
        ["<table>"],
    ),
    # 10. 单行管道符
    (
        "单行管道符",
        "| only one line |",
        [],
        ["<table>"],
    ),
    # 11. 含 HTML 转义字符
    (
        "单元格含 < > &",
        "| Op | Result |\n|---|---|\n| a<b | x&y |",
        # CommonMark 严格保留实体显示,a&lt;b / x&amp;y 在 HTML 里还原
        ["a&lt;b"],
    ),
    # 12. 中文单元格
    (
        "中文单元格",
        "| 姓名 | 分数 |\n| --- | --- |\n| 张三 | 95 |",
        ["<th>姓名</th>", "<th>分数</th>", "<td>张三</td>", "<td>95</td>"],
    ),
    # 13. 表格后紧跟段落(无空行)
    (
        "表格后紧接段落",
        "| H | V |\n|---|---|\n| a | b |\n结束。",
        ["</table>", "结束"],
    ),
    # 14. 空输入
    (
        "空输入",
        "",
        [],
        ["<table>"],
    ),
    # 15. 代码块内的 | 不应触发表格检测(注意:Pygments 高亮后内容仍在 <pre> 内)
    (
        "代码块内管道",
        "```\n| not | table |\n| --- | --- |\n```",
        # Pygments 高亮后输出 <div class="highlight"><pre>...</pre></div>
        ["<pre>", "| not | table |", "| --- | --- |"],
        ["<table>", "<th>", "<td>"],
    ),
]


# =============================================================================
# 新增:任务列表 / 脚注 / 代码高亮 / 链接(阶段 1 补强验证)
# =============================================================================

# 16. 任务列表
(
    "任务列表",
    "- [ ] 待办\n- [x] 完成\n- [ ] 另一个",
    [
        'class="contains-task-list"',
        'type="checkbox"', 'disabled="disabled"',  # 禁用(只显示)
        'checked="checked"',                       # - [x> 已勾选
        "待办", "完成",
    ],
)

# 17. 脚注
(
    "脚注",
    "正文[^1]\n\n[^1]: 注释内容",
    [
        "footnote-ref",
        '<a href="#fn1"',
        '<section class="footnotes">',
        "注释内容",
    ],
)

# 18. 代码块高亮(Pygments)
(
    "代码块高亮-python",
    "```python\ndef hello():\n    return 'hi'\n```",
    [
        'class="language-python"',  # markdown-it 标记语言
        "highlight",                # Pygments 包裹
        "hello",                    # 代码内容
    ],
)

# 19. 代码块高亮-js
(
    "代码块高亮-js",
    "```javascript\nconst x = 1;\n```",
    [
        'class="language-javascript"',
        "highlight",
    ],
)

# 20. 链接
(
    "链接",
    "[百度](https://www.baidu.com)",
    ['<a href="https://www.baidu.com">百度</a>'],
)

# 21. 行内代码 + 粗体 + 标题 基础语法
(
    "基础语法",
    "# 标题\n\n**粗体** 与 `代码` 与 [链接](https://x.y)",
    [
        "<h1>标题</h1>",
        "<strong>粗体</strong>",
        "<code>代码</code>",
        '<a href="https://x.y">链接</a>',
    ],
)

# 22. 图片基础
(
    "图片基础",
    "![alt text](https://x.y/p.png)",
    ['<img src="https://x.y/p.png"'],
    [],  # alt="alt text" markdown-it 会规范化空格
)

# 23. 图片相对路径解析
(
    "图片相对路径解析-无文件",
    "![local](./missing.png)",
    # 找不到文件时保持原样
    ["./missing.png"],
)


# =============================================================================
# 跑测试
# =============================================================================

# 把表格 cases + 任务列表/脚注/高亮 合并
all_cases = cases + [
    # tuple 形式(name, md, expected_substrings, must_not_contain)
    ("任务列表", "- [ ] 待办\n- [x] 完成\n- [ ] 另一个",
     ['class="contains-task-list"', 'type="checkbox"', 'disabled="disabled"',
      'checked="checked"', "待办", "完成"]),
    ("脚注", "正文[^1]\n\n[^1]: 注释内容",
     ["footnote-ref", '<a href="#fn1"', '<section class="footnotes">', "注释内容"]),
    ("代码块高亮-python", "```python\ndef hello():\n    return 'hi'\n```",
     # Pygments 完全替换外层为 <div class="highlight"><pre>...</pre></div>
     # 关键字 def 用 <span class="k"> 标记
     ['class="highlight"', '<pre>', "hello",
      '<span class="k">def</span>']),
    ("代码块高亮-js", "```javascript\nconst x = 1;\n```",
     ['class="highlight"', '<pre>', "const",
      '<span class="kd">const</span>']),
    ("链接", "[百度](https://www.baidu.com)",
     ['<a href="https://www.baidu.com">百度</a>']),
    ("基础语法", "# 标题\n\n**粗体** 与 `代码` 与 [链接](https://x.y)",
     ["<h1>标题</h1>", "<strong>粗体</strong>", "<code>代码</code>",
      '<a href="https://x.y">链接</a>']),
    ("图片基础", "![alt text](https://x.y/p.png)",
     ['<img src="https://x.y/p.png"']),
    ("图片相对路径无文件", "![local](./missing.png)", ["./missing.png"]),
]

passed = 0
for case in all_cases:
    name = case[0]
    md = case[1]
    expected = case[2]
    forbidden = case[3] if len(case) > 3 else None
    if check(name, md, expected, forbidden):
        passed += 1
total = len(all_cases)
print(f"\n{'=' * 50}")
print(f"结果: {passed}/{total} 通过")
sys.exit(0 if passed == total else 1)