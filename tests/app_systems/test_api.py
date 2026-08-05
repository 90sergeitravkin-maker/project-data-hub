# tests/app_systems/test_api.py
"""
Тесты API app_systems с учётом статической авторизации по токену.
Все защищённые эндпоинты требуют заголовок Authorization: Bearer <token>.
"""
import os
import pytest
from fastapi.testclient import TestClient
from src.app_systems.config import APP_TOKEN

# Берём первый валидный токен из конфига. Fallback для CI/сред без .env
_TEST_TOKEN = APP_TOKEN[0] if APP_TOKEN else "test_token_fallback"
AUTH_HEADERS = {"Authorization": f"Bearer {_TEST_TOKEN}"}


class TestAppSystemsAPI:
    """Тесты контрактов, валидации и обработки ошибок API app_systems."""

    # ==================== GET /available-folders ====================
    def test_folders_success_default_root(self, api_client: TestClient, mock_services: dict):
        """Успешный запрос без параметров (корневая директория)."""
        mock_services["folders"].return_value = (True, {
            "folders": ["ds_2024", "ds_2025"],
            "files": ["readme.md", "config.yaml"],
            "total": 4,
            "page": 1,
            "page_size": 50,
            "has_next": False,
            "has_prev": False,
            "excluded": 3,
            "current_path": "",
            "applied_pattern": None,
            "error": None
        })
        resp = api_client.get("/api/v1/systems/available-folders", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["folders"] == ["ds_2024", "ds_2025"]
        assert data["files"] == ["readme.md", "config.yaml"]
        assert data["total"] == 4
        assert data["current_path"] == ""

    def test_folders_with_path_and_pattern(self, api_client: TestClient, mock_services: dict):
        """Фильтрация содержимого конкретной папки по regex."""
        mock_services["folders"].return_value = (True, {
            "folders": ["2025-01-01", "2025-02-01"],
            "files": [],
            "total": 2,
            "page": 1,
            "page_size": 50,
            "has_next": False,
            "has_prev": False,
            "excluded": 0,
            "current_path": "comtrade.json/raw",
            "applied_pattern": r"^\d{4}-\d{2}-\d{2}$",
            "error": None
        })
        resp = api_client.get(
            "/api/v1/systems/available-folders",
            params={
                "folder_path": "comtrade.json/raw",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["folders"]) == 2
        assert data["applied_pattern"] == r"^\d{4}-\d{2}-\d{2}$"
        assert data["current_path"] == "comtrade.json/raw"

    def test_folders_service_error(self, api_client: TestClient, mock_services: dict):
        """Ошибка сервиса (путь не существует / недоступен)."""
        mock_services["folders"].return_value = (False, {"error": "Директория не найдена: invalid/path"})
        resp = api_client.get("/api/v1/systems/available-folders?folder_path=invalid/path", headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "Директория не найдена: invalid/path"

    def test_folders_invalid_regex(self, api_client: TestClient, mock_services: dict):
        """Сервис возвращает ошибку при невалидном regex."""
        mock_services["folders"].return_value = (False, {
            "error": "Невалидный regex: bad regex [position 0]: nothing to repeat"
        })
        resp = api_client.get("/api/v1/systems/available-folders?pattern=[invalid", headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "Невалидный regex" in resp.json()["detail"]["error"]

    # ==================== POST /check-data ====================
    def test_check_data_mixed_result(self, api_client: TestClient, mock_services: dict):
        """Смешанный результат проверки (найденные, отсутствующие, пустые)."""
        # Сервис возвращает простые списки
        mock_services["check"].return_value = (True, {
            "found": ["valid"], "missing": ["lost_1", "lost_2"], "empty": ["empty"]
        })
        # Мок сканирования дат
        mock_services["get_max_dates_for_folders"].return_value = {"valid": "2026-03-18"}

        resp = api_client.post(
            "/api/v1/systems/check-data",
            json={"folders": ["valid", "lost_1", "lost_2", "empty"]},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "не найдено: 2" in data["message"]
        assert "пустые: 1" in data["message"]
        assert data["total_checked"] == 4
        #  Ожидаем список словарей
        assert data["found"] == [{"valid": "2026-03-18"}]

    def test_check_data_empty_request(self, api_client: TestClient, mock_services: dict):
        """Пустой запрос не падает, возвращает нулевые счётчики."""
        mock_services["check"].return_value = (True, {"found": [], "missing": [], "empty": []})
        resp = api_client.post("/api/v1/systems/check-data", json={"folders": None}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total_checked"] == 0

    # ==================== POST /extract-schema ====================
    def test_extract_schema_success(self, api_client: TestClient, mock_services: dict):
        """Успешное извлечение схемы из parquet."""
        mock_services["extract"].return_value = (True, {
            "schema": {
                "id": {"type": "BIGINT", "null": False},
                "name": {"type": "VARCHAR", "null": True}
            },
            "file_type": "parquet", "field_count": 2
        })
        resp = api_client.post(
            "/api/v1/systems/extract-schema",
            json={"file_path": "data/export.parquet"},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "schema" in data
        assert data["schema"]["id"]["type"] == "BIGINT"
        assert data["schema"]["name"]["null"] is True
        assert data["file_type"] == "parquet"

    def test_extract_schema_validation_422(self, api_client: TestClient):
        """FastAPI автоматически возвращает 422 при нарушении Pydantic-схемы запроса."""
        resp = api_client.post(
            "/api/v1/systems/extract-schema",
            json={"wrong_field": "data.csv"},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 422
        errors = resp.json()["detail"]
        assert any(e["loc"] == ["body", "file_path"] for e in errors)

    def test_extract_schema_service_error(self, api_client: TestClient, mock_services: dict):
        """Ошибка сервиса НЕ ломает API: возвращается 200 с success=False."""
        mock_services["extract"].return_value = (False, {
            "error": "Файл не найден: data/missing.parquet", "file_type": "unknown"
        })
        resp = api_client.post(
            "/api/v1/systems/extract-schema",
            json={"file_path": "data/missing.parquet"},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "missing.parquet" in data["error"]
        assert data["file_type"] == "unknown"

    # ==================== POST /upload-file ====================
    def test_upload_file_success(self, api_client: TestClient, mock_services: dict):
        """Успешная загрузка файла (сервис замокан)."""
        mock_services["upload"].return_value = (True, {
            "file_path": "/data/test.parquet",
            "file_size": 1024,
            "stored_in": "minio",
            "checksum": "a1b2c3d4"
        })

        resp = api_client.post(
            "/api/v1/systems/upload-file",
            data={
                "file_path": "test.parquet",
                "overwrite": "false",
                "metadata": '{"source": "test"}'
            },
            files={"file": ("test.parquet", b"fake_content", "application/octet-stream")},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["stored_in"] == "minio"
        assert data["file_size"] == 1024

    # ==================== АВТОРИЗАЦИЯ ====================
    def test_auth_unauthorized(self, api_client: TestClient, mock_services: dict):
        """Запрос без токена должен возвращать 401."""
        resp = api_client.get("/api/v1/systems/available-folders")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Неверный токен"

    def test_auth_invalid_token(self, api_client: TestClient):
        """Запрос с неверным токеном должен возвращать 401."""
        resp = api_client.get(
            "/api/v1/systems/available-folders",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert resp.status_code == 401