from app.middleware.exceptions import _code_from_status


def test_code_from_status_401_is_unauthenticated() -> None:
    assert _code_from_status(401) == "UNAUTHENTICATED"


def test_code_from_status_403_is_forbidden() -> None:
    assert _code_from_status(403) == "FORBIDDEN"


