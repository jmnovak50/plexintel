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
    assert capabilities.require("recipe.search").parameter_map["page_size"] == "perPage"


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


def test_schema_d_adapts_route_movement_and_parameter_rename():
    capabilities = OperationResolver().build(load("schema_d.json"))
    search = capabilities.require("recipe.search")
    recipe = capabilities.require("recipe.get")
    assert search.parameter_map["page_size"] == "pageSize"
    assert recipe.path == "/api/recipes/item/{recipeSlug}"
    assert recipe.parameter_map["slug"] == "recipeSlug"
    assert "experimental" not in capabilities.model_dump_json()


def test_ambiguous_route_movement_is_refused():
    document = load("schema_d.json")
    original = document["paths"]["/api/recipes/item/{recipeSlug}"]
    document["paths"]["/api/recipes/view/{recipeSlug}"] = original
    capabilities = OperationResolver().build(document)
    assert "recipe.get" not in capabilities.names


@pytest.mark.parametrize(
    ("mutation", "capability"),
    [
        (
            lambda operation: operation["responses"]["200"]["content"]["application/json"].update(
                {"schema": {"type": "string"}}
            ),
            "recipe.search",
        ),
        (
            lambda operation: operation["parameters"][2]["schema"].update({"type": "string"}),
            "recipe.search",
        ),
    ],
)
def test_incompatible_schema_is_refused(mutation, capability):
    document = load("schema_d.json")
    mutation(document["paths"]["/api/recipes"]["get"])
    assert capability not in OperationResolver().build(document).names


def test_whole_document_validation_allows_unrelated_recursive_reference_graph():
    document = load("schema_a.json")
    document["components"]["schemas"]["CycleA"] = {"$ref": "#/components/schemas/CycleB"}
    document["components"]["schemas"]["CycleB"] = {"$ref": "#/components/schemas/CycleA"}
    capabilities = OperationResolver().build(document)
    assert "recipe.get" in capabilities.names


def test_recursive_recipe_models_are_accepted_and_curated_capabilities_still_resolve():
    capabilities = OperationResolver().build(load("schema_recursive.json"))
    assert capabilities.names == {"identity.self", "recipe.search", "recipe.get"}
    assert capabilities.require("recipe.get").path == "/api/recipes/{slug}"


def test_semantic_root_reference_cycle_fails_safely():
    document = load("schema_a.json")
    document["components"]["schemas"]["CycleA"] = {"$ref": "#/components/schemas/CycleB"}
    document["components"]["schemas"]["CycleB"] = {"$ref": "#/components/schemas/CycleA"}
    document["paths"]["/api/recipes/{slug}"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/CycleA"}
    with pytest.raises(MealieInvalidResponse, match="cycle"):
        OperationResolver().build(document)


def test_semantic_composition_expansion_cycle_fails_safely():
    document = load("schema_a.json")
    document["components"]["schemas"]["LoopA"] = {
        "type": "object",
        "allOf": [{"$ref": "#/components/schemas/LoopB"}],
    }
    document["components"]["schemas"]["LoopB"] = {
        "type": "object",
        "allOf": [{"$ref": "#/components/schemas/LoopA"}],
    }
    document["paths"]["/api/recipes/{slug}"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/LoopA"}
    with pytest.raises(MealieInvalidResponse, match="cycle"):
        OperationResolver().build(document)


def test_semantic_reference_depth_limit_is_enforced():
    document = load("schema_a.json")
    schemas = document["components"]["schemas"]
    for index in range(22):
        schemas[f"Depth{index}"] = {"$ref": f"#/components/schemas/Depth{index + 1}"}
    schemas["Depth22"] = {"type": "object", "properties": {"id": {"type": "string"}}}
    document["paths"]["/api/users/self"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/Depth0"}
    with pytest.raises(MealieInvalidResponse, match="depth"):
        OperationResolver().build(document)


@pytest.mark.parametrize(
    "reference",
    [
        "#/components/schemas/DoesNotExist",
        "#/components/schemas/Bad~2Pointer",
        "#/components/schemas/Bad%ZZPointer",
        123,
        None,
    ],
)
def test_invalid_local_reference_is_rejected(reference):
    document = load("schema_a.json")
    document["components"]["schemas"]["Broken"] = {"$ref": reference}
    with pytest.raises(MealieInvalidResponse):
        OperationResolver().build(document)
