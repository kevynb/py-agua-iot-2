"""Shared helpers for recording and replaying sanitized HTTP cassettes."""

import json
import os
import re
from pathlib import Path

import vcr

CASSETTE_DIR = Path(__file__).parent / "cassettes"

PLACEHOLDERS = {
    "AGUA_API_URL": "https://api.example.invalid",
    "AGUA_LOGIN_API_URL": "https://login.example.invalid/api/bridge/endpoint/",
    "AGUA_CUSTOMER_CODE": "000000",
    "AGUA_EMAIL": "user@example.invalid",
    "AGUA_PASSWORD": "password-placeholder",
    "AGUA_UNIQUE_ID": "00000000-0000-4000-8000-000000000000",
    "AGUA_BRAND_ID": "1",
    "AGUA_TOKEN": "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJleHAiOjQxMDI0NDQ4MDB9.",
    "AGUA_REFRESH_TOKEN": "refresh-token-placeholder",
}

REAL_CONFIG_ENV_VARS = (
    "AGUA_API_URL",
    "AGUA_CUSTOMER_CODE",
    "AGUA_EMAIL",
    "AGUA_PASSWORD",
    "AGUA_UNIQUE_ID",
)

JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9_\-\.]+")
SENSITIVE_KEY_RE = re.compile(
    r"(^id$|email|password|token|refresh_token|id_|serial|mac|security_code|assistance_code)",
    re.IGNORECASE,
)
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
MAC_RE = re.compile(r"\b[0-9A-F]{12}\b")


def _env_or_placeholder(name):
    return os.getenv(name) or PLACEHOLDERS[name]


def current_test_config():
    """Return config from env vars when present, otherwise stable placeholders."""
    return {
        "api_url": _env_or_placeholder("AGUA_API_URL"),
        "customer_code": _env_or_placeholder("AGUA_CUSTOMER_CODE"),
        "email": _env_or_placeholder("AGUA_EMAIL"),
        "password": _env_or_placeholder("AGUA_PASSWORD"),
        "unique_id": _env_or_placeholder("AGUA_UNIQUE_ID"),
        "login_api_url": os.getenv("AGUA_LOGIN_API_URL"),
        "brand_id": _env_or_placeholder("AGUA_BRAND_ID"),
    }


def has_real_http_config():
    return all(os.getenv(name) for name in REAL_CONFIG_ENV_VARS)


def cassette_exists(name):
    return (CASSETTE_DIR / name).exists()


def _sensitive_replacements():
    replacements = {}

    # Replace all explicit config/env values with placeholders.
    for env_name, placeholder in PLACEHOLDERS.items():
        value = os.getenv(env_name)
        if value:
            replacements[value] = placeholder

    # Replace URL variants used by requests internals.
    api_url = os.getenv("AGUA_API_URL")
    if api_url:
        replacements[api_url.rstrip("/")] = PLACEHOLDERS["AGUA_API_URL"]

    login_url = os.getenv("AGUA_LOGIN_API_URL")
    if login_url:
        replacements[login_url.rstrip("/")] = PLACEHOLDERS["AGUA_LOGIN_API_URL"].rstrip(
            "/"
        )

    return replacements


def _redact_text(value):
    if not value:
        return value

    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
    else:
        text = str(value)

    for sensitive, placeholder in _sensitive_replacements().items():
        text = text.replace(sensitive, placeholder)

    text = JWT_RE.sub(PLACEHOLDERS["AGUA_TOKEN"], text)
    text = UUID_RE.sub("id-placeholder", text)
    text = MAC_RE.sub("mac-placeholder", text)
    return text


def _redact_json_payload(value):
    if not value:
        return value

    raw = _redact_text(value)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return raw

    def scrub(obj, key_hint=""):
        if isinstance(obj, dict):
            cleaned = {}
            for key, val in obj.items():
                lowered = str(key).lower()
                if lowered in ("email", "password", "token", "refresh_token"):
                    env_key = f"AGUA_{lowered.upper()}"
                    cleaned[key] = PLACEHOLDERS.get(env_key, f"{lowered}-placeholder")
                elif lowered in ("phone_id", "id_app", "push_notification_token"):
                    cleaned[key] = PLACEHOLDERS["AGUA_UNIQUE_ID"]
                elif lowered in ("customer_code",):
                    cleaned[key] = PLACEHOLDERS["AGUA_CUSTOMER_CODE"]
                elif SENSITIVE_KEY_RE.search(lowered):
                    cleaned[key] = f"{lowered}-placeholder"
                else:
                    cleaned[key] = scrub(val, lowered)
            return cleaned
        if isinstance(obj, list):
            return [scrub(item, key_hint) for item in obj]
        if isinstance(obj, str):
            return _redact_text(obj)
        return obj

    payload = scrub(payload)

    return json.dumps(payload)


def _redact_header_values(header_value):
    if isinstance(header_value, list):
        return [_redact_text(item) for item in header_value]
    if isinstance(header_value, (bytes, str)):
        return [_redact_text(header_value)]
    return [_redact_text(str(header_value))]


def before_record_request(request):
    request.uri = _redact_text(request.uri)

    for header in ("Authorization", "customer_code", "id_brand"):
        if header in request.headers:
            request.headers[header] = _redact_header_values(request.headers[header])

    request.body = _redact_json_payload(request.body)
    return request


def before_record_response(response):
    headers = response.get("headers", {})
    for header in ("Authorization", "customer_code", "id_brand"):
        if header in headers:
            headers[header] = _redact_header_values(headers[header])

    body = response.get("body", {})
    body_string = body.get("string")
    if body_string:
        body["string"] = _redact_json_payload(body_string).encode("utf-8")

    return response


AGUA_VCR = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("VCR_RECORD_MODE", "none"),
    match_on=["method", "scheme", "host", "port", "path", "query", "body"],
    before_record_request=before_record_request,
    before_record_response=before_record_response,
    decode_compressed_response=True,
)
