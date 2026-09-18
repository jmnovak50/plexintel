from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from app.auth.authentik import AuthentikIdentityProvider
from app.auth.dependencies import current_mcp_principal
from app.config import Settings
from app.mealie.errors import MealieError
from app.services.mealplans import MealPlanService
from app.services.recipes import RecipeService
from app.services.shopping import ShoppingService

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def create_mcp_server(
    settings: Settings,
    identity: AuthentikIdentityProvider,
    recipes: RecipeService,
    mealplans: MealPlanService,
    shopping: ShoppingService,
) -> MCPServer:
    server = MCPServer(
        "Mealie MCP",
        version="0.1.0",
        instructions=(
            "Use these curated tools to read the authenticated user's own Mealie connection. "
            "Each user's Mealie permissions are enforced by their separately stored Mealie token. "
            "Never ask for or accept a Mealie token in tool arguments. Search recipes before choosing "
            "a slug. Use bounded date ranges for meal plans and list shopping lists before requesting "
            "one by ID. A capability-unavailable error means this Mealie version does not support that "
            "operation; do not try to construct raw Mealie API calls."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.oidc_issuer)),
            resource_server_url=AnyHttpUrl(str(settings.mcp_public_url)),
            required_scopes=settings.oidc_required_scopes,
            # Our provider validates Authentik's configured audience. Authentik does not
            # emit the MCP resource URL as a resource-indicator claim.
            validate_token_resource=False,
        ),
        token_verifier=identity,
    )

    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def search_recipes(
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search accessible Mealie recipes and return bounded paginated summaries.

        Category and tag filters use Mealie slugs or IDs. Call without filters for general text search.
        """
        return await _tool_call(
            recipes.search,
            current_mcp_principal(identity),
            search=search,
            page=page,
            per_page=per_page,
            categories=categories,
            tags=tags,
        )

    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def get_recipe(slug: str) -> dict[str, Any]:
        """Get full cooking details for one accessible recipe using its exact Mealie slug."""
        return await _tool_call(recipes.get, current_mcp_principal(identity), slug)

    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def get_meal_plan(start_date: date, end_date: date) -> dict[str, Any]:
        """Get meal-plan entries in an inclusive date range of at most 366 days."""
        return await _tool_call(mealplans.get, current_mcp_principal(identity), start_date, end_date)

    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def get_shopping_lists(page: int = 1, per_page: int = 20) -> dict[str, Any]:
        """List accessible Mealie shopping lists with bounded pagination."""
        return await _tool_call(shopping.list, current_mcp_principal(identity), page, per_page)

    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def get_shopping_list(shopping_list_id: str) -> dict[str, Any]:
        """Get one accessible shopping list, including its items, by exact list ID."""
        return await _tool_call(shopping.get, current_mcp_principal(identity), shopping_list_id)

    return server


async def _tool_call(function, *args, **kwargs) -> dict[str, Any]:
    try:
        value = await function(*args, **kwargs)
        if not isinstance(value, dict):
            return {"items": value}
        return value
    except (MealieError, ValueError) as exc:
        raise ToolError(f"{type(exc).__name__}: {exc}. Do not automatically retry this call.") from exc
