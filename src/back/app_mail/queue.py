import asyncio
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Any

from core.logger import logger
from src.back.app_mail.config import (
    FROM_EMAIL, 
    APP_PASSWORD, 
    SMTP_PORT, 
    SMTP_SERVER,
    SMTP_USE_TLS,
    SMTP_USE_AUTH
)
from src.back.app_mail.services import MailTracker


class MailTaskObj:
    """Объект задачи для очереди"""
    def __init__(self, task_id: str, data: Dict[str, Any]):
        self.task_id = task_id
        self.data = data


class MailQueue:
    """Асинхронная очередь отправки писем"""
    
    def __init__(self, workers: int = 2):
        self.queue: asyncio.Queue[MailTaskObj] = asyncio.Queue()
        self.workers_count = workers
        self.worker_tasks = []
        self.is_running = False

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.worker_tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers_count)]
        logger.info(f"[MAIL_QUEUE] Очередь запущена (воркеров: {self.workers_count})")

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        # Ждем пока все задачи из очереди будут выполнены
        await self.queue.join()
        # Останавливаем задачи воркеров
        for t in self.worker_tasks:
            t.cancel()
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        logger.info("[MAIL_QUEUE] Очередь остановлена")

    def add_task(self, task_id: str, data: Dict[str, Any]) -> str:
        self.queue.put_nowait(MailTaskObj(task_id, data))
        return task_id

    async def _worker(self, wid: int):
        while self.is_running:
            task = None
            try:
                # Получаем задачу с таймаутом, чтобы можно было корректно остановиться
                try:
                    task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                logger.info(f"[MAIL_QUEUE] Воркер #{wid} обрабатывает задачу {task.task_id}")
                
                # ОSбновляем статус в БД
                await MailTracker.update_status(task.task_id, "sending")

                # Формируем письмо
                msg = MIMEText(task.data.get("text", ""), 'plain', 'utf-8')
                msg['From'] = FROM_EMAIL
                msg['To'] = task.data.get("to", "")
                msg['Subject'] = task.data.get("subject", "")
                # Отправка
                server = None
                try:
                    # Подключение к серверу
                    if SMTP_USE_TLS:
                        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                        server.starttls()
                    else:
                        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)

                    # Аутентификация
                    if SMTP_USE_AUTH:
                        if not FROM_EMAIL or not APP_PASSWORD:
                            raise ValueError("Для аутентификации требуются FROM_EMAIL и APP_PASSWORD")
                        server.login(FROM_EMAIL, APP_PASSWORD)

                    # Отправка в отдельном потоке, чтобы не блокировать event loop
                    await asyncio.to_thread(server.send_message, msg)

                    await MailTracker.update_status(task.task_id, "sent")
                    logger.info(f"[MAIL_QUEUE] ✅ Задача {task.task_id} выполнена (отправлено)")

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"[MAIL_QUEUE] ❌ Ошибка отправки {task.task_id}: {error_msg}")
                    await MailTracker.update_status(task.task_id, "failed", error_msg)
                finally:
                    if server:
                        try:
                            server.quit()
                        except Exception:
                            pass

            except Exception as e:
                if task:
                    logger.error(f"[MAIL_QUEUE] Критическая ошибка воркера для {task.task_id}: {e}")
                    await MailTracker.update_status(task.task_id, "failed", str(e))
                else:
                    logger.error(f"[MAIL_QUEUE] Ошибка воркера #{wid} без контекста задачи: {e}")
            finally:
                if task:
                    self.queue.task_done()

# Глобальный экземпляр очереди
mail_queue = MailQueue(workers=3)