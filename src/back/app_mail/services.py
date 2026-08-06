import uuid
from typing import Dict, Any, Optional

from src.core.logger import logger
from src.back.app_mail.config import DB_ALIAS
from src.database.manager import DBManager


class MailTracker:
    """Аналог TaskTracker из app_ecomru. Отвечает за CRUD задач в БД."""

    @classmethod
    async def create_task(cls, data: Dict[str, Any]) -> str:

        logger.debug(f"data = {data}")
        task_id = str(uuid.uuid4())
        db = DBManager()
        await db.execute(
            DB_ALIAS,
            """
            INSERT INTO app_mail.mail_tasks 
            (task_id, to_email, subject, body_preview)
            VALUES ($1, $2, $3, $4)
            """,
            task_id,
            data.get("to", ""),
            data.get("subject", ""),
            data.get("text", "")[:500]
        )
        logger.debug(f"task_id = {task_id}")
        return task_id

    @classmethod
    async def update_status(cls, task_id: str, status: str, error: Optional[str] = None):
        db = DBManager()
        if status == "sent":
            await db.execute(
                DB_ALIAS,
                """
                UPDATE app_mail.mail_tasks 
                    SET 
                         status        = $1
                        ,sent_at       = NOW()
                        ,error_message = NULL 
                WHERE 
                    task_id = $2
                """,
                status, task_id
            )
        else:
            await db.execute(
                DB_ALIAS,
                """
                UPDATE app_mail.mail_tasks 
                    SET status = $1, error_message = $2 
                WHERE task_id = $3
                """,
                status, error, task_id
            )

    @classmethod
    async def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        db = DBManager()
        return await db.fetch_one(
            DB_ALIAS,
            """
            SELECT
                task_id,status
            FROM app_mail.mail_tasks 
            WHERE task_id = $1
            """,
            task_id)
