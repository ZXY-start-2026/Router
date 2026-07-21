from app.services.title import make_title


def test_empty_title_uses_default() -> None:
    assert make_title("  \n ") == "新会话"


def test_title_is_single_line() -> None:
    assert make_title(" 第一行\n  第二行 ") == "第一行 第二行"


def test_title_adds_ellipsis_after_thirty_characters() -> None:
    content = "测" * 31
    assert make_title(content) == f"{'测' * 30}…"


def test_title_keeps_exactly_thirty_characters() -> None:
    content = "A" * 30
    assert make_title(content) == content

