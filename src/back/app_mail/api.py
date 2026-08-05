import uuid
from fastapi import APIRouter, HTTPException, status
from core.logger import logger
from src.back.app_mail.config import TAG_NAME
from src.back.app_mail.schemas import MailCreateRequest, TaskResponse, TaskStatusResponse
from src.back.app_mail.services import MailTracker
from src.back.app_mail.queue import mail_queue

router = APIRouter(tags=[TAG_NAME])

async def init_queue() -> None:
    if not mail_queue.is_running:
        await mail_queue.start()
        logger.info("[MAIL_API] Очередь инициализирована")


async def shutdown_queue() -> None:
    if mail_queue.is_running:
        await mail_queue.stop()
        logger.info("[MAIL_API] Очередь остановлена")


@router.post("/send", response_model=TaskResponse, summary="Постановка задачи на отправку", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_mail(request: MailCreateRequest):
    await init_queue()
    data = {"to": request.to, "subject": request.subject, "text": request.text}
    task_id = await MailTracker.create_task(data)
    mail_queue.add_task(task_id, data)
    return TaskResponse(task_id=task_id, status="queued")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse, summary="Проверка статуса задачи")
async def check_status(task_id: str):
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(400, detail="Некорректный формат task_id")

    task = await MailTracker.get_task(task_id)
    if not task:
        raise HTTPException(404, detail="Задача не найдена")
    return task