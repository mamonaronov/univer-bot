from services.synonyms import expand, normalize


def test_normalize_strips_stopwords():
    words = normalize("как поступить в вуз")
    assert "как" not in words
    assert "поступить" in words


def test_normalize_handles_punctuation():
    assert "расписание" in normalize("Где расписание?")


def test_expand_adds_synonyms():
    words = expand(["сессия"])
    assert "экзамен" in words
    assert "пересдача" in words
    assert "зачёт" in words


def test_expand_no_duplicates():
    words = expand(["поступление", "приём", "прием"])
    assert len(words) == len(set(words))


def test_expand_unknown_word_kept():
    assert expand(["абракадабра"]) == ["абракадабра"]