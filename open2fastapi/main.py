from dataclasses import dataclass
import json
import re
from typing import Any
from pathlib import Path
import logging

log = logging.getLogger(__name__)


def load(openapi: Path) -> Any:
    with open(openapi) as data:
        return json.load(data)


@dataclass
class Config:
    project_dir: Path
    name: str


def render_class(name: str, schema: dict) -> str:
    buffer = [f"class {name}(BaseModel):"]
    required = schema.get("required", [])
    for pname, prop in schema.get("properties", []).items():
        type = ""
        match prop.get("type"):
            case "integer":
                type = "int"
            case "string":
                type = "str"
            case "array":
                desc = prop.get("items", {})
                subtype = desc.get("type", desc.get("$ref", "").split("/")[-1])
                type = f"List[{subtype}]"

            case "boolean":
                type = "bool"
            case x:
                log.warning("couldnt determine type for %s from %s", pname, x)
        type = f"{type} | None" if pname not in required else type
        buffer.append(f"    {pname}: {type}")
    return "\n".join(buffer) + "\n\n"


def write_code(code: str, where: Path):
    with open(where, "a") as output:
        output.write(code)


def create_models(openapi: dict, config: Config):
    if not config.project_dir.exists():
        config.project_dir.mkdir()

    model_file = config.project_dir / f"{config.name}_models.py"

    for name, schema in openapi.get("components", {}).get("schemas", {}).items():
        match schema.get("type"):
            case "object":
                _class = render_class(name, schema)
                write_code(_class, model_file)
            case x:
                log.warning("Got unknown component type: %s", x)


def create_routes(openapi: dict, config: Config):
    if not config.project_dir.exists():
        config.project_dir.mkdir()

    routes_file = config.project_dir / f"{config.name}_api.py"

    buffer = ["router = fastapi.create_router()"]
    for path, schema in openapi.get("paths", {}).items():
        for verb, subschema in schema.items():
            params = [f"{p}: str" for p in re.findall("{(\w+)}", path)]
            request_body = (
                subschema.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref", "")
                .split("/")[-1]
            )
            if request_body:
                params.append(f"{request_body.lower()}: {request_body}")

            response_body = (
                subschema.get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref", "")
                .split("/")[-1]
            )

            route_def = f"def {subschema.get('operationId')}({', '.join(params)})"
            route_def = (
                f"{route_def} -> {response_body}:" if response_body else f"{route_def}:"
            )

            buffer.append(f'@router.{verb}("{path}")')
            buffer.append(route_def)
            buffer.append("    pass")
            buffer.append("\n")

    write_code("\n".join(buffer), routes_file)


if __name__ == "__main__":
    data = load(Path("data/openapi.json"))
    config = Config(Path("out"), "test")
    create_models(data, config)
    create_routes(data, config)
