"""Поиск по каталогу: он и есть интерфейс сервера.

Агент не видит сто тридцать функций, он задаёт вопрос словами. Если первый
ответ мимо, дальше не спасает ни каталог, ни документация. Поэтому тут
проверяются не внутренности ранжирования, а обещание: на живой вопрос сверху
стоит тот метод, который человек и имел в виду.
"""
from pathlib import Path

import pytest

from schema_mcp_core.entities import EntityIndex
from schema_mcp_core.registry import Catalog, EndpointSpec
from schema_mcp_core.text import concepts, stem, wants_write


def spec(operation_id, summary="", section="general", safety="read", path="/x",
         keywords=()):
    return EndpointSpec(operation_id=operation_id, method="GET", host="api.example",
                        path=path, section=section, safety=safety, summary=summary,
                        keywords=list(keywords))


@pytest.mark.parametrize("forms", [
    ("вакансии", "вакансий", "вакансия", "вакансиями"),
    ("документы", "документов", "документ"),
    ("реклама", "рекламы", "рекламе"),
    ("коды", "кодов", "код"),
    ("подпись", "подписи", "подписать"),
    ("vacancies", "vacancy"),
])
def test_word_forms_collapse_to_one_stem(forms):
    """Падежи одного слова обязаны сойтись, иначе «поиск вакансий» и «поиск
    вакансии» дают разные ответы на один вопрос."""
    assert len({stem(w) for w in forms}) == 1, [stem(w) for w in forms]


def test_stem_keeps_short_roots():
    """«Реклама» не должна срезаться до «рекл»: на огрызке перестаёт работать
    словарь переводов, а с ним и весь поиск по русскому слову."""
    assert stem("рекламы") == "реклам"
    assert stem("кодов") == "код"


def test_translation_reaches_english_catalog():
    """Каталоги английские, вопросы русские. Без перевода запрос не находит
    ничего: в имени метода стоит vacancy, а спрашивают «вакансию»."""
    groups = concepts(["вакансию"])
    assert any("vacancy" in g for g in groups)


def test_noun_is_not_a_command():
    """«Документы на подпись» это просьба показать, а не подписать. Намерение
    считается по целому слову: у «подпись» и «подписать» основа общая."""
    assert wants_write(["документы", "на", "подпись"]) is False
    assert wants_write(["подпиши", "документ"]) is True


def test_query_coverage_beats_repetition():
    """Метод, попавший в оба слова запроса, стоит выше метода, трижды
    попавшего в одно. Без этого ранжирование вырождалось в случайный порядок
    среди двадцати одинаково «подходящих» методов."""
    c = Catalog([
        spec("srv_orders_stats", summary="Статистика заказов", section="orders"),
        spec("srv_stats_stats", summary="Статистика статистики статистика",
             section="stats"),
    ])
    top = c.search("статистика заказов", limit=1)[0]
    assert top.operation_id == "srv_orders_stats"


def test_action_query_prefers_writing_method():
    """На «опубликуй вакансию» список опубликованных вакансий совпадает со
    словами запроса лучше, чем метод публикации. Побеждать должен всё равно
    метод публикации."""
    c = Catalog([
        spec("srv_get_published", summary="Просмотр списка опубликованных вакансий",
             section="vacancies"),
        spec("srv_publish", summary="Публикация вакансии", section="vacancies",
             safety="write", path="/vacancies"),
    ])
    top = c.search("опубликовать вакансию", limit=1)[0]
    assert top.operation_id == "srv_publish"


def test_section_synonym_routes_to_its_entity(tmp_path):
    """Раздел, названный в вопросе своим именем, перевешивает случайные
    совпадения слов в чужих разделах."""
    (tmp_path / "entities.yaml").write_text(
        "entities:\n"
        "  - key: auth\n    title_ru: Аутентификация\n    title_en: Auth\n"
        "    match: [auth]\n    synonyms: [войти, вход, логин]\n",
        encoding="utf-8")
    idx = EntityIndex.load(tmp_path / "entities.yaml")
    c = Catalog([
        spec("srv_accounts", summary="Список аккаунтов", section="auth"),
        spec("srv_system_info", summary="Информация о системе", section="misc"),
    ], entities=idx)
    top = c.search("войти в систему", limit=1)[0]
    assert top.operation_id == "srv_accounts"


def test_first_entity_wins_a_shared_synonym(tmp_path):
    """Два раздела упоминают «документы». Вопрос про документы обязан вести в
    раздел документов, а не в полку файлов, которая просто так называется."""
    (tmp_path / "entities.yaml").write_text(
        "entities:\n"
        "  - key: documents\n    title_ru: Документы\n    title_en: Documents\n"
        "    match: [documents]\n    synonyms: [документы]\n"
        "  - key: shelf\n    title_ru: Полка документов\n    title_en: Shelf\n"
        "    match: [shelf]\n    synonyms: [полка, документов]\n",
        encoding="utf-8")
    idx = EntityIndex.load(tmp_path / "entities.yaml")
    _, keys = idx.expand("входящие документы")
    assert keys == {"documents"}


def test_empty_query_returns_nothing():
    c = Catalog([spec("srv_a", summary="что-то")])
    assert c.search("   ") == []
