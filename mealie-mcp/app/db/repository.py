from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.principal import Principal
from app.db.models import MealieConnection


class ConnectionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, value: MealieConnection) -> MealieConnection:
        async with self._sessions.begin() as session:
            if value.is_default:
                await session.execute(
                    update(MealieConnection)
                    .where(
                        MealieConnection.tenant_id == value.tenant_id,
                        MealieConnection.user_id == value.user_id,
                    )
                    .values(is_default=False)
                )
            session.add(value)
            await session.flush()
            await session.refresh(value)
        return value

    async def save(self, value: MealieConnection) -> MealieConnection:
        async with self._sessions.begin() as session:
            merged = await session.merge(value)
            await session.flush()
            await session.refresh(merged)
        return merged

    async def list_for(self, principal: Principal) -> Sequence[MealieConnection]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(MealieConnection)
                .where(
                    MealieConnection.tenant_id == principal.tenant_id,
                    MealieConnection.user_id == principal.user_id,
                )
                .order_by(MealieConnection.created_at)
            )
            return result.all()

    async def get_for(self, principal: Principal, connection_id: uuid.UUID) -> MealieConnection | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(MealieConnection).where(
                    MealieConnection.id == connection_id,
                    MealieConnection.tenant_id == principal.tenant_id,
                    MealieConnection.user_id == principal.user_id,
                )
            )

    async def default_for(self, principal: Principal) -> MealieConnection | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(MealieConnection).where(
                    MealieConnection.tenant_id == principal.tenant_id,
                    MealieConnection.user_id == principal.user_id,
                    MealieConnection.is_default.is_(True),
                )
            )

    async def delete_for(self, principal: Principal, connection_id: uuid.UUID) -> bool:
        async with self._sessions.begin() as session:
            result = await session.execute(
                delete(MealieConnection).where(
                    MealieConnection.id == connection_id,
                    MealieConnection.tenant_id == principal.tenant_id,
                    MealieConnection.user_id == principal.user_id,
                )
            )
            return bool(result.rowcount)
