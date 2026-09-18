from __future__ import annotations

from typing import Any

from app.auth.principal import Principal
from app.services.connections import ConnectionExecutor


class ShoppingService:
    def __init__(self, executor: ConnectionExecutor) -> None:
        self.executor = executor

    async def list(self, principal: Principal, page: int = 1, per_page: int = 20) -> Any:
        return await self.executor.call(
            principal,
            "shopping.list",
            query={"page": max(1, page), "perPage": min(max(1, per_page), 50)},
        )

    async def get(self, principal: Principal, shopping_list_id: str) -> Any:
        return await self.executor.call(
            principal,
            "shopping.get",
            path_values={"item_id": shopping_list_id},
        )
