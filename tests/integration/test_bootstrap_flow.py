import pytest

from py_agua_iot import agua_iot
from tests.integration.vcr_harness import (
    AGUA_VCR,
    cassette_exists,
    current_test_config,
    has_real_http_config,
)

CASSETTE_NAME = "bootstrap_flow.yaml"


@pytest.mark.integration
def test_bootstrap_flow_from_cassette_or_live_recording(tmp_path):
    # Replay-only mode needs a previously recorded cassette.
    if not has_real_http_config() and not cassette_exists(CASSETTE_NAME):
        pytest.skip(
            "No cassette found. Provide AGUA_* credentials to record it once."
        )

    cfg = current_test_config()
    with AGUA_VCR.use_cassette(CASSETTE_NAME):
        client = agua_iot(
            cfg["api_url"],
            cfg["customer_code"],
            cfg["email"],
            cfg["password"],
            cfg["unique_id"],
            login_api_url=cfg["login_api_url"],
            brand_id=cfg["brand_id"],
            register_map_cache_enabled=True,
            register_map_cache_dir=str(tmp_path),
        )

    assert isinstance(client.devices, list)
    assert client.token is not None

    if client.devices:
        first = client.devices[0]
        assert first.id_device is not None
        assert first.id_product is not None
