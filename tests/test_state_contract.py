from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

import server


ROOT = Path(__file__).resolve().parents[1]
DYNAMIC_SCHEMA_PATH = ROOT / "docs" / "state_schema.json"
STATIC_SCHEMA_PATH = ROOT / "docs" / "state_static_schema.json"


def test_state_endpoint_has_versioning_and_identity_fields() -> None:
    first = server.get_state()
    second = server.get_state()

    assert first["schema_version"] == "1.1.0"
    assert isinstance(first["state_version"], int)
    assert second["state_version"] == first["state_version"] + 1

    assert all("agent_id" in agent for agent in first["agents"])
    assert all("village_uid" in village for village in first["villages"])


def test_static_state_endpoint_shape() -> None:
    payload = server.get_static_state()
    assert payload["schema_version"] == "1.1.0"
    assert payload["static_state_version"] == 1
    assert isinstance(payload["width"], int)
    assert isinstance(payload["height"], int)
    assert isinstance(payload["tiles"], list)


def test_state_payload_validates_against_dynamic_schema() -> None:
    payload = server.get_state()
    schema = json.loads(DYNAMIC_SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=payload, schema=schema)


def test_static_payload_validates_against_static_schema() -> None:
    payload = server.get_static_state()
    schema = json.loads(STATIC_SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=payload, schema=schema)


def test_dynamic_payload_contains_required_dynamic_fields_without_static_map_fields() -> None:
    payload = server.get_state()
    expected_dynamic_fields = {
        "schema_version",
        "state_version",
        "tick",
        "food",
        "wood",
        "stone",
        "farms",
        "farms_count",
        "structures",
        "roads",
        "storage_buildings",
        "villages",
        "civ_stats",
        "agents",
        "population",
        "players",
        "npcs",
        "avg_hunger",
        "food_count",
        "wood_count",
        "stone_count",
        "houses_count",
        "villages_count",
        "leaders_count",
        "llm_interactions",
    }
    assert expected_dynamic_fields.issubset(set(payload.keys()))
    assert "width" not in payload
    assert "height" not in payload
    assert "tiles" not in payload
