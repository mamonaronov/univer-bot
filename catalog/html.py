"""Convert WordPress HTML into Telegram-safe HTML."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

_SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "button"}
_BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "blockquote",
    "figure",
    "figcaption",
    "br",
    "hr",
}

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_WHITESPACE_RE = re.compile(r"[ \t]+\n")
_MANY_NL_RE = re.compile(r"\n{3,}")
_MANY_SPACES_RE = re.compile(r"[ \t]{2,}")
_PDF_RE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)(?:$|\?)", re.I)


def decode_title(raw: str) -> str:
    return html.unescape(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))


def extract_file_links(markup: str, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(markup or "", "html.parser")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        href = urljoin(page_url, tag["href"].strip())
        if href in seen or not _PDF_RE.search(href):
            continue
        title = tag.get_text(" ", strip=True) or href.rsplit("/", 1)[-1]
        seen.add(href)
        found.append((title[:80], href))
    return found


def html_to_telegram(markup: str, page_url: str = "") -> str:
    soup = BeautifulSoup(markup or "", "html.parser")
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()
    chunks: list[str] = []
    _emit(soup.body if soup.body else soup, chunks, page_url)
    text = "".join(chunks)
    text = html.unescape(text)
    text = _MANY_SPACES_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub("\n", text)
    text = _MANY_NL_RE.sub("\n\n", text)
    return text.strip()


def _emit(node: Tag | NavigableString, out: list[str], page_url: str) -> None:
    if isinstance(node, NavigableString):
        text = str(node)
        if not text:
            return
        out.append(html.escape(text, quote=False))
        return
    if not isinstance(node, Tag):
        return
    name = node.name.lower()
    if name in _SKIP_TAGS:
        return
    if name == "br":
        out.append("\n")
        return
    if name == "hr":
        out.append("\n")
        return
    if name == "table":
        _emit_table(node, out)
        return
    if name == "li":
        out.append("• ")
        for child in node.children:
            _emit(child, out, page_url)
        out.append("\n")
        return
    if name in _HEADING_TAGS:
        inner: list[str] = []
        for child in node.children:
            _emit(child, inner, page_url)
        heading = "".join(inner).strip()
        if heading:
            out.append(f"\n<b>{heading}</b>\n")
        return
    if name == "a":
        href = (node.get("href") or "").strip()
        if href and page_url:
            href = urljoin(page_url, href)
        inner = []
        for child in node.children:
            _emit(child, inner, page_url)
        label = "".join(inner).strip() or href
        if href and href.startswith(("http://", "https://", "mailto:", "tg://")):
            out.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        else:
            out.append(label)
        return
    if name in {"b", "strong"}:
        out.append("<b>")
        for child in node.children:
            _emit(child, out, page_url)
        out.append("</b>")
        return
    if name in {"i", "em"}:
        out.append("<i>")
        for child in node.children:
            _emit(child, out, page_url)
        out.append("</i>")
        return
    if name in {"u", "s", "code", "pre"}:
        out.append(f"<{name}>")
        for child in node.children:
            _emit(child, out, page_url)
        out.append(f"</{name}>")
        return
    if name in _BLOCK_TAGS:
        out.append("\n")
        for child in node.children:
            _emit(child, out, page_url)
        out.append("\n")
        return
    for child in node.children:
        _emit(child, out, page_url)


def _emit_table(table: Tag, out: list[str]) -> None:
    out.append("\n")
    for row in table.find_all("tr"):
        cells = []
        for cell in row.find_all(["th", "td"], recursive=False):
            text = cell.get_text(" ", strip=True)
            if text:
                cells.append(text)
        if not cells:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            cells = [c for c in cells if c]
        if cells:
            line = " — ".join(cells) if len(cells) <= 2 else " | ".join(cells)
            out.append(html.escape(line, quote=False))
            out.append("\n")
    out.append("\n")
