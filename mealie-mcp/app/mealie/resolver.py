from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field

from app.mealie.capabilities import CAPABILITY_SPECS, CapabilitySpec, ParameterSpec
from app.mealie.errors import CapabilityUnavailable, MealieInvalidResponse

_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_MAX_REF_DEPTH = 20
_MINIMUM_SCORE = 100
_AMBIGUITY_MARGIN = 15


class OperationDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str
    method: str
    path: str
    operation_id: str | None = None
    query_parameters: frozenset[str] = frozenset()
    path_parameters: frozenset[str] = frozenset()
    parameter_map: dict[str, str] = Field(default_factory=dict)


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


@dataclass(frozen=True)
class _Candidate:
    score: int
    descriptor: OperationDescriptor


class OperationResolver:
    def build(self, document: dict[str, Any]) -> CapabilityMap:
        paths = document.get("paths")
        if not isinstance(paths, dict):
            raise MealieInvalidResponse("OpenAPI document has no paths object")
        _validate_refs(document)

        resolved: dict[str, OperationDescriptor] = {}
        for spec in CAPABILITY_SPECS:
            candidates: list[_Candidate] = []
            for path, path_item in paths.items():
                if not isinstance(path, str) or not isinstance(path_item, dict):
                    continue
                operation = path_item.get(spec.method)
                if not isinstance(operation, dict):
                    continue
                candidate = _evaluate_candidate(spec, path, path_item, operation, document)
                if candidate is not None:
                    candidates.append(candidate)

            candidates.sort(key=lambda item: (-item.score, item.descriptor.path))
            if not candidates or candidates[0].score < _MINIMUM_SCORE:
                continue
            if len(candidates) > 1 and candidates[0].score - candidates[1].score < _AMBIGUITY_MARGIN:
                continue
            resolved[spec.name] = candidates[0].descriptor
        return CapabilityMap(operations=resolved)


def _evaluate_candidate(
    spec: CapabilitySpec,
    path: str,
    path_item: dict[str, Any],
    operation: dict[str, Any],
    document: dict[str, Any],
) -> _Candidate | None:
    operation_id = operation.get("operationId")
    if operation_id is not None and not isinstance(operation_id, str):
        return None
    tags = operation.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        return None

    exact_path = path in spec.paths
    known_operation = operation_id in spec.operation_ids
    allowed_tags = {_normalize(value) for value in spec.allowed_tags}
    matching_tag = any(_normalize(tag) in allowed_tags for tag in tags)
    path_lower = path.casefold()
    matching_path = all(keyword.casefold() in path_lower for keyword in spec.path_keywords)

    # Route movement is accepted only when independent operation metadata and path
    # semantics agree. An arbitrary new endpoint never becomes a curated tool.
    if not exact_path and not (matching_path and (known_operation or matching_tag)):
        return None

    parameters = _collect_parameters(path_item, operation, document)
    if parameters is None:
        return None
    parameter_map = _match_parameters(spec.parameters, parameters, document)
    if parameter_map is None:
        return None

    path_parameters = {
        parameter["name"]
        for parameter in parameters
        if parameter.get("in") == "path" and isinstance(parameter.get("name"), str)
    }
    query_parameters = {
        parameter["name"]
        for parameter in parameters
        if parameter.get("in") == "query" and isinstance(parameter.get("name"), str)
    }
    placeholders = set(_PATH_PARAMETER.findall(path))
    residual_path = _PATH_PARAMETER.sub("", path)
    if "{" in residual_path or "}" in residual_path or placeholders != path_parameters:
        return None

    mapped_names = set(parameter_map.values())
    for parameter in parameters:
        name = parameter.get("name")
        location = parameter.get("in")
        if (
            parameter.get("required") is True
            and location in {"path", "query", "header", "cookie"}
            and isinstance(name, str)
            and name not in mapped_names
        ):
            return None

    if operation.get("requestBody") is not None:
        return None

    if not _response_is_compatible(spec, operation, document):
        return None

    score = 20  # compatible response schema
    score += 100 if exact_path else 0
    score += 80 if known_operation else 0
    score += 35 if matching_tag else 0
    score += 15 if matching_path else 0
    for parameter_spec in spec.parameters:
        if parameter_spec.semantic_name in parameter_map:
            score += 12 if parameter_spec.required_for_match else 3

    return _Candidate(
        score,
        OperationDescriptor(
            capability=spec.name,
            method=spec.method.upper(),
            path=path,
            operation_id=operation_id,
            query_parameters=frozenset(query_parameters),
            path_parameters=frozenset(path_parameters),
            parameter_map=parameter_map,
        ),
    )


def _collect_parameters(
    path_item: dict[str, Any], operation: dict[str, Any], document: dict[str, Any]
) -> list[dict[str, Any]] | None:
    collected: dict[tuple[str, str], dict[str, Any]] = {}
    for owner in (path_item, operation):
        raw_parameters = owner.get("parameters", [])
        if not isinstance(raw_parameters, list):
            return None
        for raw in raw_parameters:
            value = _dereference(raw, document)
            if not isinstance(value, dict):
                return None
            name = value.get("name")
            location = value.get("in")
            schema = value.get("schema")
            if (
                not isinstance(name, str)
                or location not in {"path", "query", "header", "cookie"}
                or not isinstance(schema, dict)
            ):
                return None
            if location == "path" and value.get("required") is not True:
                return None
            collected[(location, name)] = value
    return list(collected.values())


def _match_parameters(
    specifications: tuple[ParameterSpec, ...],
    parameters: list[dict[str, Any]],
    document: dict[str, Any],
) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for specification in specifications:
        matches = [
            parameter
            for parameter in parameters
            if parameter.get("in") == specification.location
            and parameter.get("name") in specification.aliases
        ]
        if len(matches) > 1:
            return None
        if not matches:
            if specification.required_for_match or specification.always_supplied:
                return None
            continue
        parameter = matches[0]
        schema = _dereference(parameter["schema"], document)
        if not isinstance(schema, dict):
            return None
        schema_types = _schema_types(schema, document)
        if not schema_types or schema_types.isdisjoint(specification.schema_types):
            return None
        result[specification.semantic_name] = parameter["name"]
    return result


def _response_is_compatible(
    spec: CapabilitySpec, operation: dict[str, Any], document: dict[str, Any]
) -> bool:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return False
    success = next(
        (
            value
            for status, value in sorted(responses.items(), key=lambda item: str(item[0]))
            if str(status).startswith("2")
        ),
        responses.get("default"),
    )
    success = _dereference(success, document)
    if not isinstance(success, dict):
        return False
    content = success.get("content")
    if not isinstance(content, dict):
        return False
    media = content.get("application/json") or content.get("application/problem+json")
    if not isinstance(media, dict):
        return False
    schema = _dereference(media.get("schema"), document)
    if not isinstance(schema, dict):
        return False
    schema_types = _schema_types(schema, document)
    if not schema_types or schema_types.isdisjoint(spec.response.schema_types):
        return False
    if spec.response.required_properties:
        properties = _schema_properties(schema, document)
        if not spec.response.required_properties.issubset(properties):
            return False
    return True


def _schema_types(
    schema: dict[str, Any],
    document: dict[str, Any],
    *,
    depth: int = 0,
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    schema, seen = _semantic_schema(schema, document, depth=depth, seen=seen)
    if not isinstance(schema, dict):
        return set()
    value = schema.get("type")
    result = {value} if isinstance(value, str) else set()
    if isinstance(value, list):
        result.update(item for item in value if isinstance(item, str))
    if "properties" in schema:
        result.add("object")
    if "items" in schema:
        result.add("array")
    for keyword in ("anyOf", "oneOf"):
        branches = schema.get(keyword)
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, dict):
                    result.update(_schema_types(branch, document, depth=depth + 1, seen=seen))
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        branch_types = []
        for branch in all_of:
            if isinstance(branch, dict):
                types = _schema_types(branch, document, depth=depth + 1, seen=seen)
                if types:
                    branch_types.append(types)
        if branch_types:
            compatible = set.intersection(*branch_types)
            result = result.intersection(compatible) if result else compatible
    return result - {"null"}


def _schema_properties(
    schema: dict[str, Any],
    document: dict[str, Any],
    *,
    depth: int = 0,
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    schema, seen = _semantic_schema(schema, document, depth=depth, seen=seen)
    if not isinstance(schema, dict):
        return set()
    result: set[str] = set()
    properties = schema.get("properties")
    if isinstance(properties, dict):
        result.update(str(name) for name in properties)
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, dict):
                    result.update(_schema_properties(branch, document, depth=depth + 1, seen=seen))
    return result


def _semantic_schema(
    schema: dict[str, Any],
    document: dict[str, Any],
    *,
    depth: int,
    seen: frozenset[str],
) -> tuple[Any, frozenset[str]]:
    if depth >= _MAX_REF_DEPTH:
        raise MealieInvalidResponse("OpenAPI reference depth limit exceeded")
    if "$ref" not in schema:
        return schema, seen
    reference = schema["$ref"]
    if not isinstance(reference, str):
        raise MealieInvalidResponse("OpenAPI document contains a malformed reference")
    if reference in seen:
        raise MealieInvalidResponse("OpenAPI document contains a reference cycle")
    return (
        _dereference(schema, document, depth=depth, seen=seen),
        seen | {reference},
    )


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _validate_refs(
    node: Any,
    document: dict[str, Any] | None = None,
) -> None:
    if document is None:
        if not isinstance(node, dict):
            raise MealieInvalidResponse("OpenAPI document is malformed")
        document = node
    if isinstance(node, list):
        for item in node:
            _validate_refs(item, document)
    elif isinstance(node, dict):
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str):
                raise MealieInvalidResponse("OpenAPI document contains a malformed reference")
            if not reference.startswith("#/"):
                raise MealieInvalidResponse("OpenAPI document contains an external reference")
            # Validate the literal reference without expanding its target. Recursive
            # component graphs are legal OpenAPI and every target is inspected in
            # its ordinary location during this whole-document walk.
            _resolve_pointer(reference, document)
        for key, child in node.items():
            if key != "$ref":
                _validate_refs(child, document)


def _dereference(
    value: Any,
    document: dict[str, Any],
    *,
    depth: int = 0,
    seen: frozenset[str] = frozenset(),
) -> Any:
    if not isinstance(value, dict):
        return value
    if "$ref" not in value:
        return value
    reference = value["$ref"]
    if not isinstance(reference, str):
        raise MealieInvalidResponse("OpenAPI document contains a malformed reference")
    if not reference.startswith("#/"):
        raise MealieInvalidResponse("OpenAPI document contains an external reference")
    if depth >= _MAX_REF_DEPTH:
        raise MealieInvalidResponse("OpenAPI reference depth limit exceeded")
    if reference in seen:
        raise MealieInvalidResponse("OpenAPI document contains a reference cycle")

    current = _resolve_pointer(reference, document)
    resolved = _dereference(current, document, depth=depth + 1, seen=seen | {reference})
    if not isinstance(resolved, dict):
        return resolved
    siblings = {key: item for key, item in value.items() if key != "$ref"}
    return {**resolved, **siblings}


def _parse_pointer(reference: str) -> list[str]:
    if not reference.startswith("#/"):
        raise MealieInvalidResponse("OpenAPI document contains a malformed reference")
    parts: list[str] = []
    for raw_part in reference[2:].split("/"):
        if _INVALID_PERCENT_ESCAPE.search(raw_part):
            raise MealieInvalidResponse("OpenAPI document contains a malformed JSON pointer")
        decoded = unquote(raw_part)
        index = 0
        while index < len(decoded):
            if decoded[index] == "~":
                if index + 1 >= len(decoded) or decoded[index + 1] not in {"0", "1"}:
                    raise MealieInvalidResponse("OpenAPI document contains a malformed JSON pointer")
                index += 2
            else:
                index += 1
        parts.append(decoded.replace("~1", "/").replace("~0", "~"))
    return parts


def _resolve_pointer(reference: str, document: dict[str, Any]) -> Any:
    current: Any = document
    for part in _parse_pointer(reference):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise MealieInvalidResponse("OpenAPI document contains an unresolved reference")
    return current
