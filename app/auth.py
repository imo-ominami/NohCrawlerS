import base64
import hashlib
import hmac
import os
import secrets
import time


_PASSWORD_ITERATIONS = 310_000
_SESSION_TTL_SECONDS = 60 * 60 * 24 * 14
_CSRF_TTL_SECONDS = 60 * 60 * 24 * 14
_SESSION_SECRET = os.getenv("SESSION_SECRET", "development-only-change-this-session-secret").encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        expected = decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), decode(salt_text), int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + _SESSION_TTL_SECONDS}"
    signature = hmac.new(_SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def read_session_token(token: str) -> int | None:
    try:
        user_id_text, expiry_text, signature = token.split(":", 2)
        payload = f"{user_id_text}:{expiry_text}"
        expected = hmac.new(_SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected) or int(expiry_text) < int(time.time()):
            return None
        return int(user_id_text)
    except (ValueError, TypeError):
        return None


def create_csrf_token() -> str:
    nonce = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + _CSRF_TTL_SECONDS
    payload = f"{nonce}.{expires_at}"
    signature = hmac.new(_SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_csrf_token(token: str) -> bool:
    try:
        nonce, expiry_text, signature = token.rsplit(".", 2)
        payload = f"{nonce}.{expiry_text}"
        expected = hmac.new(_SESSION_SECRET, payload.encode("ascii"), hashlib.sha256).hexdigest()
        return (
            bool(nonce)
            and int(expiry_text) >= int(time.time())
            and hmac.compare_digest(signature, expected)
        )
    except (ValueError, TypeError, UnicodeEncodeError):
        return False
