# src/front/web_architecture/services.py
from typing import Dict, Any

from fastapi import FastAPI

from src.database.base import Base


class ArchitectureCollector:
    @classmethod
    def get_app_info(cls, app: FastAPI) -> Dict[str, Any]:
        result = {
            "apps": [],
            "routes": [],
            "models": [],
            "config": {
                "title": app.title,
                "version": app.version,
                "description": app.description,
            },
        }

        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                if route.path.startswith(("/docs", "/redoc", "/openapi.json", "/static")):
                    continue
                result["routes"].append({
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else [],
                    "tags": list(route.tags) if hasattr(route, "tags") and route.tags else [],
                    "name": getattr(route, "name", None),
                    "summary": getattr(route, "summary", "") or "",
                    "description": getattr(route, "description", "") or "",
                })

        for table in Base.metadata.sorted_tables:
            result["models"].append({
                "name": f"{table.schema}.{table.name}" if table.schema else table.name,
                "columns": [{"name": c.name, "type": str(c.type)} for c in table.columns],
                "primary_key": [c.name for c in table.primary_key.columns],
                "foreign_keys": [
                    {"column": fk.parent.name, "ref_table": fk.target_table.name}
                    for fk in table.foreign_keys
                ],
            })

        for tag in app.openapi_tags or []:
            if tag.get("name") not in ("System", None):
                result["apps"].append({
                    "name": tag["name"],
                    "description": tag.get("description", ""),
                    "prefix": f"/api/v1/{tag['name'].lower().replace(' ', '_')}",
                })
        return result
