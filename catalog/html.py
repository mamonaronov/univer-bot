"""Convert WordPress HTML into Telegram-safe HTML."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

_SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "form",
    "button",
    "input",
    "textarea",
    "select",
    "label",
    "img",
    "video",
    "source",
    "canvas",
}
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
_EMPTY_FORMAT_RE = re.compile(r"<(b|i|u|s)>\s*</\1>", re.I)
_LAYOUT_TOKENS = {
    "bg",
    "box",
    "box-image",
    "box-text",
    "box-text-inner",
    "col",
    "col-inner",
    "image",
    "image-box",
    "page-box",
    "page-col",
    "row",
    "section-bg",
    "section-content",
    "section-title",
}
_LAYOUT_LINE_RE = re.compile(r"^[\s.#\-]*[A-Za-z][\w.\s#-]*$")


def decode_title(raw: str) -> str:
    return html.unescape(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))


def extract_file_links(markup: str, page_url: str) -> list[tuple[str, str]]:
    soup = _prepare_soup(markup)
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
    soup = _prepare_soup(markup)
    chunks: list[str] = []
    _emit(soup.body if soup.body else soup, chunks, page_url)
    text = "".join(chunks)
    text = html.unescape(text)
    text = _collapse_empty_format(text)
    text = _MANY_SPACES_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub("\n", text)
    text = _drop_layout_lines(text)
    text = _MANY_NL_RE.sub("\n\n", text)
    return text.strip()


def strip_self_and_child_nav(body: str, title: str, child_titles: list[str]) -> str:
    """Drop the page heading and child titles copied from site navigation cards."""
    skip = {_norm_heading(title), *(_norm_heading(item) for item in child_titles)}
    skip.discard("")
    kept: list[str] = []
    for line in body.split("\n"):
        plain = _norm_heading(line)
        if plain and plain in skip:
            continue
        kept.append(line)
    return _MANY_NL_RE.sub("\n\n", "\n".join(kept)).strip()


def _norm_heading(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    plain = html.unescape(plain)
    return re.sub(r"\s+", " ", plain).casefold().strip()


def _prepare_soup(markup: str) -> BeautifulSoup:
    soup = BeautifulSoup(markup or "", "html.parser")
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    return soup


def _collapse_empty_format(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = _EMPTY_FORMAT_RE.sub("", text)
    return text


def _drop_layout_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.split("\n"):
        plain = re.sub(r"<[^>]+>", "", line).strip()
        if plain and _is_layout_noise(plain):
            continue
        kept.append(line)
    return "\n".join(kept)


def _is_layout_noise(plain: str) -> bool:
    if not _LAYOUT_LINE_RE.match(plain):
        return False
    tokens = [part.lower() for part in re.split(r"[\s.#]+", plain.strip(".# ")) if part]
    if not tokens:
        return True
    return all(token in _LAYOUT_TOKENS for token in tokens)


def _emit(node: Tag | NavigableString, out: list[str], page_url: str) -> None:
    if isinstance(node, Comment):
        return
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
        inner: list[str] = []
        for child in node.children:
            _emit(child, inner, page_url)
        label = "".join(inner).strip()
        title_attr = (node.get("title") or "").strip()
        if not label or _is_layout_noise(re.sub(r"<[^>]+>", "", label)):
            label = html.escape(title_attr, quote=False) if title_attr else ""
        if href.startswith("mailto:"):
            if not label:
                label = html.escape(href.replace("mailto:", ""), quote=False)
            out.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
            return
        if label:
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
