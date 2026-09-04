#!/usr/bin/env python3
"""Convert markdown file to PDF via HTML + WeasyPrint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

CSS = """
@page {
    size: A4;
    margin: 2cm;
}
body {
    font-family: "DejaVu Sans", "Liberation Sans", sans-serif;
    font-size: 11pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1 {
    font-size: 18pt;
    border-bottom: 2px solid #333;
    padding-bottom: 0.3em;
    margin-top: 0;
}
h2 {
    font-size: 14pt;
    margin-top: 1.4em;
    color: #222;
}
h3 {
    font-size: 12pt;
    margin-top: 1em;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
}
th, td {
    border: 1px solid #bbb;
    padding: 6px 10px;
    text-align: left;
}
th {
    background: #f0f0f0;
    font-weight: bold;
}
pre, code {
    font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
    font-size: 9.5pt;
}
pre {
    background: #f7f7f9;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 10px 14px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}
hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 1.5em 0;
}
p { margin: 0.6em 0; }
ul { margin: 0.5em 0; }
em { color: #555; }
"""


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{md_path.stem}</title>
  <style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""
    HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(pdf_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert markdown to PDF")
    parser.add_argument("input", type=Path, help="Input .md file")
    parser.add_argument("-o", "--output", type=Path, help="Output .pdf file")
    args = parser.parse_args()
    out = args.output or args.input.with_suffix(".pdf")
    md_to_pdf(args.input, out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
