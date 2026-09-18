from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    method: str
    paths: tuple[str, ...]
    operation_ids: tuple[str, ...]
    required_path_parameters: frozenset[str] = frozenset()


CAPABILITY_SPECS = (
    CapabilitySpec(
        "identity.self",
        "get",
        ("/api/users/self",),
        ("get_logged_in_user_api_users_self_get",),
    ),
    CapabilitySpec(
        "recipe.search",
        "get",
        ("/api/recipes",),
        ("get_all_api_recipes_get",),
    ),
    CapabilitySpec(
        "recipe.get",
        "get",
        ("/api/recipes/{slug}",),
        ("get_one_api_recipes__slug__get",),
        frozenset({"slug"}),
    ),
    CapabilitySpec(
        "mealplan.read",
        "get",
        ("/api/households/mealplans",),
        ("get_all_api_households_mealplans_get",),
    ),
    CapabilitySpec(
        "shopping.list",
        "get",
        ("/api/households/shopping/lists",),
        ("get_all_api_households_shopping_lists_get",),
    ),
    CapabilitySpec(
        "shopping.get",
        "get",
        ("/api/households/shopping/lists/{item_id}",),
        ("get_one_api_households_shopping_lists__item_id__get",),
        frozenset({"item_id"}),
    ),
)

REQUIRED_FOUNDATION_CAPABILITIES = frozenset({"identity.self"})
