"""
表格解析回归测试 —— 不启动 GUI，直接调用 markdown_to_html 验证 HTML 输出。

用法: python test_table.py
"""
import os
import sys

# 强制 UTF-8 输出（Windows PowerShell 默认 GBK 不支持 emoji）
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 跳过 __init__（避免加载 .ui / 创建 QApplication）
from md_editor import MarkdownEditor  # noqa: E402

editor = MarkdownEditor.__new__(MarkdownEditor)


def check(name, md, expected_substrings, must_not_contain=None):
    html = editor.markdown_to_html(md)
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


cases = [
    # 1. 基本 2 列表格
    (
        "基本表格",
        "| Name | Score |\n|------|-------|\n| Alice | 95 |\n| Bob | 87 |",
        [
            "<table>", "<thead>", "<th>Name</th>", "<th>Score</th>",
            "<tbody>", "<td>Alice</td>", "<td>95</td>",
            "<td>Bob</td>", "<td>87</td>", "</table>"
        ],
        # 修复前: 4 行被包成 <p>; 修复后这些子串都不应出现
        ["<p>| Name | Score |</p>", "<p>|------|-------|</p>"],
    ),
    # 2. 对齐标记 (:---, :---:, ---:)
    (
        "对齐标记",
        "| Left | Center | Right |\n|:---|:---:|---:|\n| a | b | c |",
        ["<th>Left</th>", "<th>Center</th>", "<th>Right</th>",
         "<td>a</td>", "<td>b</td>", "<td>c</td>"],
    ),
    # 3. 空单元格
    (
        "空单元格",
        "| A | B |\n|---|---|\n|  | x |\n| y |  |",
        ["<th>A</th>", "<th>B</th>",
         "<tr><td></td><td>x</td></tr>",
         "<tr><td>y</td><td></td></tr>"],
    ),
    # 4. 缺尾部 | (宽松解析)
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
    # 6. 单列表格（仅表头+分隔，无数据行）
    (
        "空表体",
        "| H1 | H2 |\n| --- | --- |",
        ["<table>", "<thead>", "<th>H1</th>", "<th>H2</th>", "<tbody>"],
    ),
    # 7. 列数不匹配（数据行多 1 列）—— 应截断
    (
        "列数不匹配-截断",
        "| A | B |\n|---|---|\n| 1 | 2 | 3 |",
        ["<td>1</td>", "<td>2</td>"],
        ["<td>3</td>"],  # 多余列应被丢弃
    ),
    # 8. 列数不匹配（数据行少 1 列）—— 应补空
    (
        "列数不匹配-补空",
        "| A | B | C |\n|---|---|---|\n| 1 | 2 |",
        ["<td>1</td>", "<td>2</td>", "<td></td>"],
    ),
    # 9. 仅含 | 的普通段落 —— 不应误判为表格
    (
        "非表格-管道符段落",
        "1 | 2 | 3\n4 | 5 | 6",
        ["<p>1 | 2 | 3</p>", "<p>4 | 5 | 6</p>"],
        ["<table>"],
    ),
    # 10. 单行管道符（无下一行做分隔）—— 不应误判
    (
        "单行管道符",
        "| only one line |",
        [],
        ["<table>"],
    ),
    # 11. 含 HTML 转义字符的单元格（< > & 已被 escape，应保留显示）
    (
        "单元格含 < > &",
        "| Op | Result |\n|---|---|\n| a<b | x&y |",
        # &amp; &lt; &gt; 是 HTML 转义结果，Qt 会还原显示
        ["<td>a&lt;b</td>", "<td>x&amp;y</td>"],
    ),
    # 12. 中文/Unicode 单元格
    (
        "中文单元格",
        "| 姓名 | 分数 |\n| --- | --- |\n| 张三 | 95 |",
        ["<th>姓名</th>", "<th>分数</th>", "<td>张三</td>", "<td>95</td>"],
    ),
    # 13. 表格后紧跟另一段（无空行）—— 应正确分离
    (
        "表格后紧接段落",
        "| H | V |\n|---|---|\n| a | b |\n结束。",
        ["</table>", "<p>结束。</p>"],
    ),
    # 14. 空输入
    (
        "空输入",
        "",
        [],
        ["<table>"],
    ),
    # 15. 代码块内的 | 不应触发表格检测
    (
        "代码块内管道",
        "```\n| not | table |\n| --- | --- |\n```",
        # 整段被 <pre><code>...</code></pre> 包裹
        ["<pre><code>", "</code></pre>"],
        ["<table>", "<th>", "<td>"],
    ),
]

passed = 0
for case in cases:
    name = case[0]
    md = case[1]
    expected = case[2]
    forbidden = case[3] if len(case) > 3 else None
    if check(name, md, expected, forbidden):
        passed += 1
total = len(cases)
print(f"\n{'=' * 50}")
print(f"结果: {passed}/{total} 通过")
sys.exit(0 if passed == total else 1)