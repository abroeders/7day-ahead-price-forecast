"""MkDocs hook: links to the designs open on GitHub, and GitHub's theme fragments become Material's."""

import re

REPO = "https://github.com/abroeders/7day-ahead-price-forecast"
_LINK = re.compile(r"\]\(design/([^)]*)\)")
# an image for one theme: GitHub shows it with #gh-…-mode-only, Material with #only-…
_THEME = {"#gh-light-mode-only)": "#only-light)", "#gh-dark-mode-only)": "#only-dark)"}


def _on_github(match: re.Match) -> str:
    path = match.group(1)
    return f"]({REPO}/blob/main/docs/design/{path})" if path else f"]({REPO}/tree/main/docs/design)"


def on_page_markdown(markdown: str, **_) -> str:
    markdown = _LINK.sub(_on_github, markdown)
    for github, material in _THEME.items():
        markdown = markdown.replace(github, material)
    return markdown
