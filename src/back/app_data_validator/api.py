# src/back/app_data_validator/api.py
from fastapi import APIRouter, HTTPException, status
from src.back.app_data_validator.config import TAG_NAME
from src.back.app_data_validator.schemas import ValidationRequest, ValidationResponse
from src.back.app_data_validator.services import ValidationService

router = APIRouter(tags=[TAG_NAME])


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Валидация файла данных",
    operation_id="validate_file_data",  # <-- Убирает варнинг о дублировании
)
async def validate_file(request: ValidationRequest):
    """
    Валидирует файл по правилам указанного источника.
    Поддерживает как абсолютные, так и относительные пути (относительно BASE_DATA_DIR).
    """
    result = ValidationService.validate_file(request.file_path, request.source_name)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return ValidationResponse(**result)
