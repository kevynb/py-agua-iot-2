import os
import re
from pathlib import Path

import pytest

from tests.integration.vcr_harness import CASSETTE_DIR

JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9_\-\.]+")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
MAC_RE = re.compile(r"\b[0-9A-F]{12}\b")
URL_HOST_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")

SENSITIVE_ENV_VARS = (
    "AGUA_API_URL",
    "AGUA_LOGIN_API_URL",
    "AGUA_CUSTOMER_CODE",
    "AGUA_EMAIL",
    "AGUA_PASSWORD",
    "AGUA_UNIQUE_ID",
)


@pytest.mark.integration
def test_cassettes_do_not_contain_sensitive_values():
    cassette_files = sorted(Path(CASSETTE_DIR).glob("*.yaml"))
    if not cassette_files:
        pytest.skip("No cassettes recorded yet.")

    for cassette_file in cassette_files:
        content = cassette_file.read_text(encoding="utf-8")

        for env_name in SENSITIVE_ENV_VARS:
            sensitive_value = os.getenv(env_name)
            if sensitive_value:
                assert sensitive_value not in content, (
                    f"{cassette_file.name} leaked raw value from {env_name}"
                )

        assert JWT_RE.search(content) is None, (
            f"{cassette_file.name} appears to contain a raw JWT"
        )
        for host in URL_HOST_RE.findall(content):
            assert host.endswith(".example.invalid"), (
                f"{cassette_file.name} contains a non-placeholder upstream hostname: {host}"
            )

        for email in EMAIL_RE.findall(content):
            assert email.endswith("@example.invalid"), (
                f"{cassette_file.name} contains non-placeholder email: {email}"
            )

        for found_uuid in UUID_RE.findall(content):
            assert found_uuid == "00000000-0000-4000-8000-000000000000", (
                f"{cassette_file.name} contains non-placeholder UUID: {found_uuid}"
            )

        for found_mac in MAC_RE.findall(content):
            assert found_mac == "000000000000", (
                f"{cassette_file.name} appears to contain a MAC-like identifier: {found_mac}"
            )
