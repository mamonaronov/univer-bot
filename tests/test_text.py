from catalog.text import chunk_text, format_page


def test_chunk_short():
    assert chunk_text("hello") == ["hello"]


def test_chunk_splits_paragraphs():
    first = "a" * 2000
    second = "b" * 2000
    chunks = chunk_text(f"{first}\n\n{second}", limit=2500)
    assert len(chunks) == 2
    assert chunks[0] == first
    assert chunks[1] == second


def test_format_page_pagination():
    text = format_page("Раздел", "текст", 1, 3)
    assert "стр. 2/3" in text
    assert "<b>Раздел</b>" in text
