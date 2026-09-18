from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterSpec:
    semantic_name: str
    aliases: tuple[str, ...]
    location: str
    schema_types: frozenset[str]
    required_for_match: bool = False
    always_supplied: bool = False


@dataclass(frozen=True)
class ResponseSpec:
    schema_types: frozenset[str]
    required_properties: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    method: str
    paths: tuple[str, ...]
    operation_ids: tuple[str, ...]
    allowed_tags: tuple[str, ...]
    path_keywords: tuple[str, ...]
    parameters: tuple[ParameterSpec, ...]
    response: ResponseSpec


PAGE = ParameterSpec(
    "page",
    ("page", "pageNumber", "page_number"),
    "query",
    frozenset({"integer"}),
    required_for_match=True,
    always_supplied=True,
)
PAGE_SIZE = ParameterSpec(
    "page_size",
    ("perPage", "pageSize", "page_size", "limit"),
    "query",
    frozenset({"integer"}),
    required_for_match=True,
    always_supplied=True,
)
SEARCH = ParameterSpec("search", ("search", "query", "q"), "query", frozenset({"string"}))
CATEGORIES = ParameterSpec(
    "categories",
    ("categories", "categoryIds", "category_ids"),
    "query",
    frozenset({"array"}),
)
TAGS = ParameterSpec("tags", ("tags", "tagIds", "tag_ids"), "query", frozenset({"array"}))
SLUG = ParameterSpec(
    "slug",
    ("slug", "recipeSlug", "recipe_slug"),
    "path",
    frozenset({"string"}),
    required_for_match=True,
    always_supplied=True,
)
START_DATE = ParameterSpec(
    "start_date",
    ("start_date", "startDate", "fromDate", "from_date"),
    "query",
    frozenset({"string"}),
    required_for_match=True,
    always_supplied=True,
)
END_DATE = ParameterSpec(
    "end_date",
    ("end_date", "endDate", "toDate", "to_date"),
    "query",
    frozenset({"string"}),
    required_for_match=True,
    always_supplied=True,
)
SHOPPING_LIST_ID = ParameterSpec(
    "shopping_list_id",
    ("item_id", "shoppingListId", "shopping_list_id", "list_id"),
    "path",
    frozenset({"string"}),
    required_for_match=True,
    always_supplied=True,
)


CAPABILITY_SPECS = (
    CapabilitySpec(
        "identity.self",
        "get",
        ("/api/users/self",),
        ("get_logged_in_user_api_users_self_get",),
        ("Users", "User"),
        ("users", "self"),
        (),
        ResponseSpec(frozenset({"object"}), frozenset({"id"})),
    ),
    CapabilitySpec(
        "recipe.search",
        "get",
        ("/api/recipes",),
        ("get_all_api_recipes_get",),
        ("Recipe: CRUD", "Recipes", "Recipe"),
        ("recipes",),
        (PAGE, PAGE_SIZE, SEARCH, CATEGORIES, TAGS),
        ResponseSpec(frozenset({"object"}), frozenset({"items"})),
    ),
    CapabilitySpec(
        "recipe.get",
        "get",
        ("/api/recipes/{slug}",),
        ("get_one_api_recipes__slug__get",),
        ("Recipe: CRUD", "Recipes", "Recipe"),
        ("recipes",),
        (SLUG,),
        ResponseSpec(frozenset({"object"})),
    ),
    CapabilitySpec(
        "mealplan.read",
        "get",
        ("/api/households/mealplans",),
        ("get_all_api_households_mealplans_get",),
        ("Household: Mealplans", "Mealplans", "Meal Plans"),
        ("mealplans",),
        (START_DATE, END_DATE, PAGE_SIZE),
        ResponseSpec(frozenset({"array", "object"})),
    ),
    CapabilitySpec(
        "shopping.list",
        "get",
        ("/api/households/shopping/lists",),
        ("get_all_api_households_shopping_lists_get",),
        ("Household: Shopping Lists", "Shopping Lists", "Shopping"),
        ("shopping", "lists"),
        (PAGE, PAGE_SIZE),
        ResponseSpec(frozenset({"object"}), frozenset({"items"})),
    ),
    CapabilitySpec(
        "shopping.get",
        "get",
        ("/api/households/shopping/lists/{item_id}",),
        ("get_one_api_households_shopping_lists__item_id__get",),
        ("Household: Shopping Lists", "Shopping Lists", "Shopping"),
        ("shopping", "lists"),
        (SHOPPING_LIST_ID,),
        ResponseSpec(frozenset({"object"}), frozenset({"id"})),
    ),
)

REQUIRED_FOUNDATION_CAPABILITIES = frozenset({"identity.self"})
