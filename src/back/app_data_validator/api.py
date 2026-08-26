# src/back/app_data_validator/api.py

from fastapi import APIRouter, HTTPException, status, Body
from src.back.app_data_validator.config import TAG_NAME
from src.back.app_data_validator.schemas import ValidationResponse
from src.back.app_data_validator.services import ValidationService

router = APIRouter(tags=[TAG_NAME])


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Валидация файла данных",
    operation_id="validate_file_data",
)
async def validate_file(file_path: str = Body(..., description="Путь к файлу или директории")):
    """
    Валидирует файл или директорию.
    Имя источника автоматически извлекается из начала пути.
    Поддерживает как абсолютные, так и относительные пути.
    """
    result = ValidationService.validate_file(file_path)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )

    return ValidationResponse(**result)
