from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.mealie.capabilities import CAPABILITY_SPECS
from app.mealie.errors import CapabilityUnavailable, MealieInvalidResponse


class OperationDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str
    method: str
    path: str
    operation_id: str | None = None
    query_parameters: frozenset[str] = frozenset()
    path_parameters: frozenset[str] = frozenset()


class CapabilityMap(BaseModel):
    operations: dict[str, OperationDescriptor]

    @property
    def names(self) -> set[str]:
        return set(self.operations)

    def require(self, name: str) -> OperationDescriptor:
        try:
            return self.operations[name]
        except KeyError as exc:
            raise CapabilityUnavailable(f"Mealie capability '{name}' is unavailable") from exc


class OperationResolver:
    def build(self, document: dict[str, Any]) -> CapabilityMap:
        paths = document.get("paths")
        if not isinstance(paths, dict):
            raise MealieInvalidResponse("OpenAPI document has no paths object")
        _validate_refs(document)
        resolved: dict[str, OperationDescriptor] = {}
        for spec in CAPABILITY_SPECS:
            candidates: list[OperationDescriptor] = []
            for path in spec.paths:
                path_item = paths.get(path)
                if not isinstance(path_item, dict):
                    continue
                operation = path_item.get(spec.method)
                if not isinstance(operation, dict):
                    continue
                parameters = []
                for raw in [*path_item.get("parameters", []), *operation.get("parameters", [])]:
                    value = _dereference(raw, document)
                    if isinstance(value, dict):
                        parameters.append(value)
                path_parameters = frozenset(
                    str(item["name"])
                    for item in parameters
                    if item.get("in") == "path" and isinstance(item.get("name"), str)
                )
                if not spec.required_path_parameters.issubset(path_parameters):
                    continue
                operation_id = operation.get("operationId")
                if operation_id is not None and not isinstance(operation_id, str):
                    continue
                candidates.append(
                    OperationDescriptor(
                        capability=spec.name,
                        method=spec.method.upper(),
                        path=path,
                        operation_id=operation_id,
                        query_parameters=frozenset(
                            str(item["name"])
                            for item in parameters
                            if item.get("in") == "query" and isinstance(item.get("name"), str)
                        ),
                        path_parameters=path_parameters,
                    )
                )
            preferred = next(
                (candidate for candidate in candidates if candidate.operation_id in spec.operation_ids),
                candidates[0] if candidates else None,
            )
            if preferred is not None:
                resolved[spec.name] = preferred
        return CapabilityMap(operations=resolved)


def _validate_refs(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _validate_refs(item)
    elif isinstance(node, dict):
        reference = node.get("$ref")
        if reference is not None and (not isinstance(reference, str) or not reference.startswith("#/")):
            raise MealieInvalidResponse("OpenAPI document contains an external reference")
        for value in node.values():
            _validate_refs(value)


def _dereference(value: Any, document: dict[str, Any], depth: int = 0) -> Any:
    if depth > 20 or not isinstance(value, dict):
        return value
    reference = value.get("$ref")
    if not isinstance(reference, str):
        return value
    current: Any = document
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise MealieInvalidResponse("OpenAPI document contains an unresolved reference")
        current = current[part]
    return _dereference(current, document, depth + 1)
