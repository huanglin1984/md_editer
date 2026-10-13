"""
预览 HTML 模板渲染。

把 Markdown → HTML 产物(由 markdown_parser 产出)包成
QTextEdit 能正确渲染的完整 HTML 文档(含 <style>)。

字号缩放策略:
  - body 字号 = base_font_size * zoom / 100
  - 标题字号 = 固定比例 * zoom / 100
  - 最小字号保护:8px / 10px / 11px / 12px / 14px

扩展性:
  - pygments_css 参数: 注入 Pygments 代码高亮 CSS
  - theme_css 参数: 用户选的主题 CSS(预留,目前用默认)
"""

from .markdown_parser import get_pygments_css, markdown_to_html


def render_markdown(
    md_text: str,
    font_zoom: int = 100,
    base_font_size: int = 28,
    file_dir: str | None = None,
    pygments_style: str = "monokai",
) -> str:
    """一步到位:Markdown 文本 → 完整预览 HTML。

    串联 markdown_to_html + render_preview,主窗口直接调这个最省事。
    """
    content = markdown_to_html(md_text, file_dir=file_dir)
    return render_preview(
        content,
        font_zoom=font_zoom,
        base_font_size=base_font_size,
        pygments_style=pygments_style,
    )


def render_preview(
    content: str,
    font_zoom: int = 100,
    base_font_size: int = 28,
    pygments_style: str = "monokai",
) -> str:
    """生成用于预览窗格的完整 HTML 文档。

    Args:
        content: 已经过 markdown_to_html 的 HTML 片段。
        font_zoom: 缩放百分比(50 ~ 200)。
        base_font_size: 正文字体基准大小(像素)。
        pygments_style: Pygments 高亮样式名(默认 monokai)。

    Returns:
        QTextEdit 可直接 setHtml 的 HTML 字符串。
    """
    body_size = max(8, int(base_font_size * font_zoom / 100))
    h1_size = max(14, int(56 * font_zoom / 100))
    h2_size = max(12, int(44 * font_zoom / 100))
    h3_size = max(11, int(36 * font_zoom / 100))
    # 注入 Pygments CSS(代码高亮色 + 行号等);无 <pre class="highlight"> 时也无害
    pygments_css = get_pygments_css(pygments_style)
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
        /* Pygments 代码高亮(由 get_pygments_css 注入) */
        {pygments_css}
    </style>
    </head>
    <body>
        {content}
    </body>
    </html>
    """