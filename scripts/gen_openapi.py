"""Generate OpenAPI JSON from Workbench API"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.workbench_api.main import app

openapi = app.openapi()
output_path = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(openapi, f, ensure_ascii=False, indent=2)

paths = len(openapi.get("paths", {}))
schemas = len(openapi.get("components", {}).get("schemas", {}))
print(f"OpenAPI generated: {paths} paths, {schemas} schemas -> {output_path}")
