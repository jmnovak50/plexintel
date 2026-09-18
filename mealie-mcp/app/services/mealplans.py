from __future__ import annotations

from datetime import date
from typing import Any

from app.auth.principal import Principal
from app.services.connections import ConnectionExecutor


class MealPlanService:
    def __init__(self, executor: ConnectionExecutor) -> None:
        self.executor = executor

    async def get(self, principal: Principal, start_date: date, end_date: date) -> Any:
        if end_date < start_date or (end_date - start_date).days > 366:
            raise ValueError("meal-plan date range must be ordered and at most 366 days")
        return await self.executor.call(
            principal,
            "mealplan.read",
            query={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "perPage": 366},
        )
