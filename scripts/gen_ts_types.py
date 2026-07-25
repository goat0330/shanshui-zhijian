"""
Generate TypeScript types from Workbench API OpenAPI JSON.
Outputs to frontend/src/shared/api/generated/types.ts
"""

import json
from pathlib import Path


def to_ts_type(schema: dict) -> str:
    """Convert JSON Schema to TypeScript type string."""
    if "$ref" in schema:
        ref = schema["$ref"]
        name = ref.split("/")[-1]
        return name
    if schema.get("type") == "array":
        items = schema.get("items", {})
        return f"{to_ts_type(items)}[]"
    if schema.get("type") == "object":
        if "additionalProperties" in schema:
            return f"Record<string, {to_ts_type(schema['additionalProperties'])}>"
        return "Record<string, unknown>"
    type_map = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
    }
    base = type_map.get(schema.get("type", ""), "unknown")
    if "enum" in schema:
        return " | ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in schema["enum"])
    if schema.get("nullable"):
        return f"{base} | null"
    return base


def ts_type_name(schema_name: str) -> str:
    """Convert OpenAPI schema name to TS interface name."""
    return schema_name  # Keep as-is, PascalCase expected


def generate_types(openapi_path: Path, output_path: Path) -> int:
    with open(openapi_path, encoding="utf-8") as f:
        spec = json.load(f)

    schemas = spec.get("components", {}).get("schemas", {})
    lines = [
        "// ══════════════════════════════════════════════════════",
        "//  Auto-generated TypeScript types from Workbench API",
        "//  Source: openapi.json",
        f"//  Generated: {__import__('datetime').datetime.now().isoformat()}",
        "// ══════════════════════════════════════════════════════",
        "",
    ]

    count = 0
    for schema_name, schema in schemas.items():
        name = ts_type_name(schema_name)
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        lines.append(f"export interface {name} {{")
        for prop_name, prop_schema in props.items():
            ts_type = to_ts_type(prop_schema)
            optional = "" if prop_name in required else "?"
            desc = prop_schema.get("description", "")
            desc_comment = f"  // {desc}" if desc else ""
            lines.append(f"  {prop_name}{optional}: {ts_type};{desc_comment}")
        lines.append("}")
        lines.append("")
        count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return count


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    openapi_path = root / "frontend" / "openapi.json"
    output_path = root / "frontend" / "src" / "shared" / "api" / "generated" / "types.ts"
    count = generate_types(openapi_path, output_path)
    print(f"Generated {count} TypeScript interfaces -> {output_path}")
