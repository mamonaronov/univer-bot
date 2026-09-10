from catalog.html import (
    decode_title,
    extract_file_links,
    html_to_telegram,
    strip_self_and_child_nav,
)


def test_decode_title_entities():
    assert decode_title("AI &#8212; старый") == "AI — старый"


def test_html_to_telegram_basic():
    html = "<h2>Контакты</h2><p>Телефон <b>+7</b></p><ul><li>Отрадное</li></ul>"
    text = html_to_telegram(html, "https://j-univer.ru/contact/")
    assert "<b>Контакты</b>" in text
    assert "<b>+7</b>" in text
    assert "• Отрадное" in text


def test_html_to_telegram_keeps_site_text_without_url():
    html = '<p><a href="/applicants/">Абитуриентам</a></p>'
    text = html_to_telegram(html, "https://j-univer.ru/")
    assert "Абитуриентам" in text
    assert "href=" not in text
    assert "j-univer.ru" not in text


def test_html_to_telegram_keeps_mailto():
    html = '<p><a href="mailto:info@uni21.org">info@uni21.org</a></p>'
    text = html_to_telegram(html, "https://j-univer.ru/")
    assert "info@uni21.org" in text
    assert "mailto:info@uni21.org" in text


def test_extract_pdf_links():
    html = '<a href="/wp-content/uploads/rules.pdf">Правила приёма</a>'
    links = extract_file_links(html, "https://j-univer.ru/applicants/docs/")
    assert links == [
        ("Правила приёма", "https://j-univer.ru/wp-content/uploads/rules.pdf")
    ]


def test_html_to_telegram_skips_flatsome_layout_comments():
    html = """
    <section class="section">
      <div class="bg section-bg"></div><!-- .section-bg -->
      <div class="section-content">
        <h1>Абитуриентам</h1>
        <style>.box-text {padding:0}</style>
        <a class="plain" href="https://j-univer.ru/applicants/celevoe-obuchenie/" title="Целевое обучение">
          <div class="box-image"></div><!-- image --><!-- box-image -->
          <div class="box-text">
            <div class="box-text-inner"><p>Целевое обучение</p></div><!-- box-text-inner -->
          </div><!-- box-text -->
        </a><!-- .image-box .box -->
      </div><!-- .section-content -->
    </section>
    """
    text = html_to_telegram(html, "https://j-univer.ru/applicants/")
    assert "section-bg" not in text
    assert "box-image" not in text
    assert "box-text" not in text
    assert "col-inner" not in text
    assert "image" not in text.lower()
    assert ".page-col" not in text
    assert "<b>Абитуриентам</b>" in text
    assert "Целевое обучение" in text
    assert "href=" not in text


def test_html_to_telegram_file_link_becomes_document_name():
    html = '<p><a href="/wp-content/uploads/rules.pdf">Правила приёма</a></p>'
    text = html_to_telegram(html, "https://j-univer.ru/applicants/docs/")
    assert "Правила приёма" in text
    assert "href=" not in text
    assert ".pdf" not in text


def test_strip_nav_cards_leaves_only_article_text():
    body = (
        "<b>Абитуриентам</b>\n\n"
        "Целевое обучение\n\n"
        "Сроки приёма документов указаны ниже.\n"
    )
    text = strip_self_and_child_nav(
        body,
        "Абитуриентам",
        ["Целевое обучение", "Документация"],
    )
    assert "Целевое обучение" not in text
    assert "Абитуриентам" not in text
    assert "Сроки приёма" in text


def test_html_to_telegram_collapses_empty_bold():
    text = html_to_telegram("<h2><b></b>О НАС<b></b></h2><p>Текст</p>")
    assert text.startswith("О НАС") or "<b>О НАС</b>" in text
    assert "<b></b>" not in text
