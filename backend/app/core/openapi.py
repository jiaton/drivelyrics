"""The OpenAPI document is the API contract the frontend's types are generated from
(scripts/export_openapi.py → frontend npm run gen:api). FastAPI only lists models used
by ordinary request/response bodies; payloads sent over Server-Sent Events are listed
here as well, so their types are generated like everything else's."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel


def with_stream_schemas(app: FastAPI, models: list[type[BaseModel]]) -> Callable[[], dict[str, Any]]:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in models:
            body = model.model_json_schema(ref_template="#/components/schemas/{model}", mode="serialization")
            for name, sub in body.pop("$defs", {}).items():
                components.setdefault(name, sub)
            components.setdefault(model.__name__, body)
        app.openapi_schema = schema
        return schema

    return openapi
