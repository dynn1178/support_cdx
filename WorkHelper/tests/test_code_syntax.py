import pytest

pytest.importorskip("PyQt6.QtGui")

from ui.code_syntax import (  # noqa: E402
    PLAIN_LANGUAGE,
    detect_language,
    language_extension,
    language_label,
    normalize_language,
    sorted_languages,
)

SAMPLES = {
    "sql": "WITH base AS (\n  SELECT DISTINCT a.id FROM MSHT a JOIN wctt b ON a.id = b.id\n  GROUP BY a.id\n)",
    "python": "import os\n\n\ndef main():\n    print('hi')\n",
    "javascript": "const total = 1;\nfunction sum() { console.log(total); }\n",
    "json": '{"name": "test", "items": [1, 2, 3]}',
    "html": '<html><body><div class="x">hi</div></body></html>',
    "shell": "#!/bin/bash\necho hello\n",
    "go": "package main\n\nfunc main() { fmt.Println(1) }",
    "csharp": "using System;\nnamespace A { class B { static void Main() { Console.WriteLine(1); } } }",
}


@pytest.mark.parametrize("language,text", SAMPLES.items())
def test_detect_language(language, text):
    assert detect_language(text) == language


def test_detect_plain_text_for_prose():
    assert detect_language("오늘 회의 내용 정리\n1. 안건\n2. 결론") == PLAIN_LANGUAGE
    assert detect_language("") == PLAIN_LANGUAGE


def test_normalize_language_keeps_legacy_values():
    assert normalize_language("other") == PLAIN_LANGUAGE  # 구버전 데이터
    assert normalize_language(None) == PLAIN_LANGUAGE
    assert normalize_language("SQL") == "sql"
    assert normalize_language("py") == "python"


def test_extension_per_language():
    assert language_extension("sql") == "sql"
    assert language_extension("python") == "py"
    assert language_extension("other") == "txt"
    assert language_label("sql") == "SQL"


def test_plain_text_is_listed_first():
    languages = sorted_languages()
    assert languages[0].id == PLAIN_LANGUAGE
    assert len({spec.id for spec in languages}) == len(languages)
