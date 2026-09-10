from catalog.html import decode_title, extract_file_links, html_to_telegram


def test_decode_title_entities():
    assert decode_title("AI &#8212; старый") == "AI — старый"


def test_html_to_telegram_basic():
    html = "<h2>Контакты</h2><p>Телефон <b>+7</b></p><ul><li>Отрадное</li></ul>"
    text = html_to_telegram(html, "https://j-univer.ru/contact/")
    assert "<b>Контакты</b>" in text
    assert "<b>+7</b>" in text
    assert "• Отрадное" in text


def test_html_to_telegram_link():
    html = '<p><a href="/applicants/">Абитуриентам</a></p>'
    text = html_to_telegram(html, "https://j-univer.ru/")
    assert 'href="https://j-univer.ru/applicants/"' in text
    assert "Абитуриентам" in text


def test_extract_pdf_links():
    html = '<a href="/wp-content/uploads/rules.pdf">Правила приёма</a>'
    links = extract_file_links(html, "https://j-univer.ru/applicants/docs/")
    assert links == [
        ("Правила приёма", "https://j-univer.ru/wp-content/uploads/rules.pdf")
    ]
