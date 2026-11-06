from urllib.parse import urlsplit

from fastapi import HTTPException


def bounded_text(value: str, field: str, max_length: int, required: bool = False) -> str:
    value = value.strip()
    if (required and not value) or len(value) > max_length:
        raise HTTPException(status_code=422, detail=f"{field}の入力を確認してください。")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise HTTPException(status_code=422, detail=f"{field}に使用できない文字が含まれています。")
    return value


def checkbox_value(value: str | None, field: str) -> bool:
    if value in {None, ""}:
        return False
    if value in {"1", "on"}:
        return True
    raise HTTPException(status_code=422, detail=f"{field}の指定が正しくありません。")


def validate_http_url(value: str, field: str = "URL", max_length: int = 2048) -> str:
    value = bounded_text(value, field, max_length, required=True)
    if any(character.isspace() for character in value):
        raise HTTPException(status_code=422, detail=f"{field}の形式が正しくありません。")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{field}の形式が正しくありません。") from error
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port == 0
    ):
        raise HTTPException(status_code=422, detail=f"{field}はhttpまたはhttpsのURLを指定してください。")
    return value


def is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except (AttributeError, ValueError):
        return False
