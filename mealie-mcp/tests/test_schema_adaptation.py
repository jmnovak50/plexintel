from __future__ import annotations

import json

import pytest
from conftest import FIXTURES

from app.mealie.errors import CapabilityUnavailable, MealieInvalidResponse
from app.mealie.resolver import OperationResolver


def load(name: str):
    return json.loads((FIXTURES / "openapi" / name).read_text())


def test_schema_a_maps_only_curated_capabilities():
    capabilities = OperationResolver().build(load("schema_a.json"))
    assert capabilities.names == {
        "identity.self",
        "recipe.search",
        "recipe.get",
        "mealplan.read",
        "shopping.list",
        "shopping.get",
    }
    assert capabilities.require("recipe.get").path_parameters == {"slug"}


def test_schema_b_accepts_compatible_operation_id_changes_and_ignores_new_endpoint():
    capabilities = OperationResolver().build(load("schema_b.json"))
    assert capabilities.names == {
        "identity.self",
        "recipe.search",
        "recipe.get",
        "mealplan.read",
        "shopping.list",
        "shopping.get",
    }
    assert "new_dangerous_operation" not in capabilities.model_dump_json()


def test_schema_c_marks_removed_or_incompatible_operations_unavailable():
    capabilities = OperationResolver().build(load("schema_c.json"))
    assert "recipe.get" not in capabilities.names
    assert "shopping.get" not in capabilities.names
    with pytest.raises(CapabilityUnavailable):
        capabilities.require("recipe.get")


def test_external_schema_reference_is_rejected():
    document = load("schema_a.json")
    document["paths"]["/api/recipes"]["get"]["parameters"].append(
        {"$ref": "https://attacker.example/schema.json"}
    )
    with pytest.raises(MealieInvalidResponse):
        OperationResolver().build(document)
