import json
import os
import time

import pytest

from py_agua_iot import API_PATH_DEVICE_REGISTERS_MAP, Device, Error, agua_iot


def _build_client(tmp_path, enabled=True, ttl=15552000):
    client = agua_iot.__new__(agua_iot)
    client.api_url = "https://api.example.invalid"
    client.customer_code = "700700"
    client.brand_id = "1"
    client.register_map_cache_enabled = enabled
    client.register_map_cache_ttl_seconds = ttl
    client.register_map_cache_dir = str(tmp_path)
    client._register_map_cache_cleaned = False
    return client


def _registers_response(register_map_id="map-1"):
    return {
        "device_registers_map": {
            "registers_map": [
                {
                    "id": register_map_id,
                    "registers": [
                        {
                            "reg_key": "status_get",
                            "reg_type": "GET",
                            "offset": 34,
                            "formula": "#",
                            "formula_inverse": "#",
                            "format_string": "{0}",
                            "set_min": 0,
                            "set_max": 255,
                            "mask": 255,
                            "enc_val": [
                                {"lang": "ENG", "description": "ON", "value": 1},
                                {"lang": "ENG", "description": "OFF", "value": 0},
                            ],
                        }
                    ],
                }
            ]
        }
    }


def _build_device(client):
    return Device(
        id="id-placeholder",
        id_device="device-1",
        id_product="product-1",
        product_serial="serial-placeholder",
        name="test-device",
        is_online=True,
        name_product="test-product",
        id_registers_map="map-1",
        agua_iot=client,
    )


def _build_device_with_register_map_id(client, register_map_id):
    return Device(
        id="id-placeholder",
        id_device="device-1",
        id_product="product-1",
        product_serial="serial-placeholder",
        name="test-device",
        is_online=True,
        name_product="test-product",
        id_registers_map=register_map_id,
        agua_iot=client,
    )


def test_register_map_cache_disabled_calls_network_every_time(tmp_path):
    client = _build_client(tmp_path, enabled=False)
    device = _build_device(client)
    called_urls = []

    def fake_handle_webcall(method, url, payload):
        called_urls.append(url)
        return _registers_response()

    client.handle_webcall = fake_handle_webcall

    device._Device__update_device_registers_mapping()
    device._Device__update_device_registers_mapping()

    assert called_urls == [
        "https://api.example.invalid" + API_PATH_DEVICE_REGISTERS_MAP,
        "https://api.example.invalid" + API_PATH_DEVICE_REGISTERS_MAP,
    ]


def test_register_map_cache_miss_then_hit_avoids_second_network_call(tmp_path):
    client = _build_client(tmp_path, enabled=True)
    device = _build_device(client)
    call_count = {"count": 0}

    def fake_handle_webcall(method, url, payload):
        call_count["count"] += 1
        return _registers_response()

    client.handle_webcall = fake_handle_webcall

    device._Device__update_device_registers_mapping()
    device._Device__update_device_registers_mapping()

    assert call_count["count"] == 1


def test_register_map_cache_expired_forces_refresh(tmp_path):
    client = _build_client(tmp_path, enabled=True, ttl=1)
    device = _build_device(client)
    call_count = {"count": 0}

    def fake_handle_webcall(method, url, payload):
        call_count["count"] += 1
        return _registers_response()

    client.handle_webcall = fake_handle_webcall

    device._Device__update_device_registers_mapping()
    cache_path = client._register_map_cache_path("device-1")
    with open(cache_path, "r", encoding="utf-8") as cache_file:
        cache_data = json.load(cache_file)
    cache_data["created_at_epoch"] = time.time() - 2
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        json.dump(cache_data, cache_file)

    device._Device__update_device_registers_mapping()

    assert call_count["count"] == 2


def test_register_map_cache_corrupt_file_falls_back_to_network(tmp_path):
    client = _build_client(tmp_path, enabled=True)
    cache_path = client._register_map_cache_path("device-1")
    os.makedirs(tmp_path, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        cache_file.write("{invalid json")

    device = _build_device(client)
    call_count = {"count": 0}

    def fake_handle_webcall(method, url, payload):
        call_count["count"] += 1
        return _registers_response()

    client.handle_webcall = fake_handle_webcall
    device._Device__update_device_registers_mapping()

    assert call_count["count"] == 1
    with open(cache_path, "r", encoding="utf-8") as cache_file:
        recovered = json.load(cache_file)
    assert recovered["register_map_dict"]["status_get"]["offset"] == 34


def test_register_map_cache_key_uses_device_id_normalization(tmp_path):
    client = _build_client(tmp_path, enabled=True)

    path_a = client._register_map_cache_path("aa:bb:cc:dd:ee:ff")
    path_b = client._register_map_cache_path("AABBCCDDEEFF")

    assert path_a == path_b


def test_register_map_cache_expired_and_network_failure_fails_hard(tmp_path):
    client = _build_client(tmp_path, enabled=True, ttl=1)
    device = _build_device(client)

    def success_then_fail(method, url, payload):
        if not hasattr(success_then_fail, "called"):
            success_then_fail.called = True
            return _registers_response()
        return False

    client.handle_webcall = success_then_fail

    device._Device__update_device_registers_mapping()
    cache_path = client._register_map_cache_path("device-1")
    with open(cache_path, "r", encoding="utf-8") as cache_file:
        cache_data = json.load(cache_file)
    cache_data["created_at_epoch"] = time.time() - 2
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        json.dump(cache_data, cache_file)

    with pytest.raises(Error, match="Error while fetching registers map"):
        device._Device__update_device_registers_mapping()


def test_register_map_cache_single_map_fallback_when_id_differs(tmp_path):
    client = _build_client(tmp_path, enabled=True)
    device = _build_device_with_register_map_id(client, "map-does-not-match")

    def fake_handle_webcall(method, url, payload):
        return _registers_response(register_map_id="map-from-server")

    client.handle_webcall = fake_handle_webcall

    device._Device__update_device_registers_mapping()
    assert device._Device__register_map_dict["status_get"]["offset"] == 34


def test_register_map_cache_stores_security_code_in_meta(tmp_path):
    client = _build_client(tmp_path, enabled=True)
    device = _build_device(client)
    device.security_code = "12345678"

    def fake_handle_webcall(method, url, payload):
        return _registers_response()

    client.handle_webcall = fake_handle_webcall
    device._Device__update_device_registers_mapping()

    cache_path = client._register_map_cache_path("device-1")
    with open(cache_path, "r", encoding="utf-8") as cache_file:
        cache_data = json.load(cache_file)
    assert cache_data["meta"]["security_code"] == "12345678"


def test_load_cached_security_from_meta(tmp_path):
    client = _build_client(tmp_path, enabled=True)
    cache_path = client._register_map_cache_path("AABBCCDDEEFF")
    os.makedirs(tmp_path, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        json.dump(
            {
                "created_at_epoch": time.time(),
                "register_map_dict": {"status_get": {"offset": 34}},
                "meta": {"device_id": "AABBCCDDEEFF", "security_code": "12345678"},
            },
            cache_file,
        )

    assert client._load_cached_security("AABBCCDDEEFF") == "12345678"
