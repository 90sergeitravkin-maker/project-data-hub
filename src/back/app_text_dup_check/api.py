# src/back/app_text_dup_check/api.py
from fastapi import APIRouter, HTTPException, Query
from src.core.logger import logger
from src.back.app_text_dup_check.schemas import SimilarityResponse, TextSaveRequest
from src.back.app_text_dup_check.services import TextService
from src.back.app_text_dup_check.config import TAG_NAME

router = APIRouter(tags=[TAG_NAME])


@router.post("/save", summary="Записать текст в базу")
async def save_text_endpoint(data: TextSaveRequest):
    logger.debug(f"data={data}")
    try:
        text_id = await TextService.save_text(data.text, data.code)
        return {"id": text_id, "message": "Текст успешно сохранен"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[TEXT_DUP_CHECK] Ошибка сохранения: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/check", response_model=SimilarityResponse, summary="Проверить на дубликаты")
async def check_text_endpoint(
        text: str = Query(..., description="Текст для проверки"),
        limit: int = Query(5, ge=1, le=50, description="Количество лучших совпадений (1-50)")
):
    logger.debug(f"data={text}, limit={limit}")
    try:
        result = await TextService.check_similarity(text, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
