from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import current_rest_principal
from app.auth.principal import Principal
from app.mealie.errors import MealieError, MealieNotFound
from app.services.connections import (
    ConnectionCreate,
    ConnectionService,
    ConnectionView,
    CredentialUpdate,
    ValidationResult,
)

router = APIRouter(prefix="/api/v1/mealie-connections", tags=["mealie-connections"])
RestPrincipal = Annotated[Principal, Depends(current_rest_principal)]


def _service(request: Request) -> ConnectionService:
    return request.app.state.connection_service


ConnectionServiceDependency = Annotated[ConnectionService, Depends(_service)]


@router.post("", response_model=ValidationResult, status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreate,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> ValidationResult:
    try:
        return await service.create(principal, body)
    except (MealieError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[ConnectionView])
async def list_connections(
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> list[ConnectionView]:
    return await service.list(principal)


@router.get("/{connection_id}", response_model=ConnectionView)
async def get_connection(
    connection_id: uuid.UUID,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> ConnectionView:
    try:
        return ConnectionView.model_validate(await service.get(principal, connection_id))
    except MealieNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{connection_id}/validate", response_model=ValidationResult)
async def validate_connection(
    connection_id: uuid.UUID,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> ValidationResult:
    try:
        return await service.validate(principal, connection_id)
    except MealieNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MealieError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{connection_id}/credential", response_model=ValidationResult)
async def replace_credential(
    connection_id: uuid.UUID,
    body: CredentialUpdate,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> ValidationResult:
    try:
        return await service.replace_credential(principal, connection_id, body)
    except MealieNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MealieError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> Response:
    try:
        await service.delete(principal, connection_id)
    except MealieNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{connection_id}/capabilities", response_model=dict[str, list[str]])
async def get_capabilities(
    connection_id: uuid.UUID,
    principal: RestPrincipal,
    service: ConnectionServiceDependency,
) -> dict[str, list[str]]:
    try:
        return {"capabilities": await service.capability_names(principal, connection_id)}
    except MealieNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
