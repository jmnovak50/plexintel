from __future__ import annotations

from typing import Any

from app.auth.principal import Principal
from app.services.connections import ConnectionExecutor


class RecipeService:
    def __init__(self, executor: ConnectionExecutor) -> None:
        self.executor = executor

    async def search(
        self,
        principal: Principal,
        *,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        return await self.executor.call(
            principal,
            "recipe.search",
            query={
                "search": search,
                "page": max(1, page),
                "perPage": min(max(1, per_page), 50),
                "categories": categories,
                "tags": tags,
            },
        )

    async def get(self, principal: Principal, slug: str) -> Any:
        return await self.executor.call(principal, "recipe.get", path_values={"slug": slug})
