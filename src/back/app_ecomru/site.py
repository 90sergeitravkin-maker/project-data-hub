# src/back/app_ecomru/site.py
"""
Модуль для работы с API сайта подрядчика (ecomru_api).

Требования:
1. authorization_token - токен авторизации (берётся из переменных окружения)
2. Доступ в интернет
3. Установленные зависимости: requests, python-dotenv
"""

import time
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from typing import List

from src.core.logger import logger
from src.back.app_ecomru.config import EXTERNAL_API_KEY

# Отключаем предупреждения о небезопасных HTTPS-запросах
urllib3.disable_warnings(InsecureRequestWarning)


class SiteApi:
    """Класс для взаимодействия с API сайта подрядчика.

    Атрибуты:
        headers (Dict): Заголовки для HTTP-запросов
        base_url (str): Базовый URL API
        swagger (str): URL документации API
        entities (Optional[str]): Текущая выбранная сущность
    """

    def __init__(self):
        """Инициализация класса SiteApi."""
        self.headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {EXTERNAL_API_KEY}',
        }
        self.base_url = 'https://appche3.ecomru.ru:4448/'
        self.swagger = 'https://appche3.ecomru.ru:4448/docs#/'
        self.entities = None
        self._session = requests.Session()  # Используем сессию для повторного использования соединения

    from typing import Optional, Dict, Any

    def _handle_request(self,
                        url: str,
                        params: Optional[Dict] = None,
                        max_attempts: int = 5,
                        retry_delay: float = 5.0,
                        timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает GET-запросы к API с повторными попытками при ошибках.

        Args:
            url: URL для запроса
            params: Дополнительные параметры запроса
            max_attempts: Максимальное количество попыток (по умолчанию 5)
            retry_delay: Задержка между попытками в секундах (по умолчанию 5)
            timeout: Таймаут запроса в секундах (по умолчанию 30)

        Returns:
            Ответ API в формате JSON или None в случае ошибки

        Raises:
            ConnectionError: Если не удалось установить соединение
        """
        params = params or {}
        if self.entities:
            params['entity'] = self.entities

        attempt = 0
        start_time = time.time()
        last_error = None

        while attempt < max_attempts:
            attempt += 1
            try:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Превышено максимальное время ожидания ({timeout} сек)")

                logger.info(f"Попытка {attempt}/{max_attempts}: GET {url} с параметрами {params}")

                response = self._session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    verify=False,
                    timeout=timeout
                )
                logger.info(f'HTTP status code: {response.status_code}')

                # ДОБАВЬТЕ ЭТУ ПРОВЕРКУ
                if response.status_code != 200:
                    response.raise_for_status()

                # ДОБАВЬТЕ ЛОГИРОВАНИЕ ОТВЕТА ДЛЯ ДИАГНОСТИКИ
                logger.info(f'Response content: {response.text[:500]}...')  # Логируем первые 500 символов

                # Пробуем распарсить JSON
                try:
                    result = response.json()
                    logger.info(f'Successfully parsed JSON response')
                    return result
                except ValueError as json_err:
                    logger.error(f'Failed to parse JSON: {json_err}')
                    logger.error(f'Response text: {response.text}')
                    # Если это не JSON, но статус 200, возможно это пустой ответ или другой формат
                    return None

            except requests.exceptions.HTTPError as http_err:
                logger.error(f'HTTP error occurred: {http_err}')
                if 'response' in locals():
                    logger.error(f'Response text: {response.text}')
                last_error = http_err

            if attempt < max_attempts:
                logger.info(f"Повтор через {retry_delay} сек...")
                time.sleep(retry_delay)

        logger.error(f"Не удалось получить ответ после {max_attempts} попыток. Последняя ошибка: {last_error}")
        return None

    def entities_v1(self) -> List[Dict[str, Any]]:
        """Получает список доступных источников данных.

        Returns:
            Список доступных сущностей

        Raises:
            ConnectionError: Если сервер не ответил
        """
        url = f'{self.base_url}api/v1/entities'
        result = self._handle_request(url)
        if result:
            return result
        raise ConnectionError("Сервер не ответил на запрос списка сущностей")

    def periods_v1(self) -> List[Dict[str, Any]]:
        """Получает список периодов для текущей сущности.

        Returns:
            Список периодов

        Raises:
            ValueError: Если сущность не выбрана
            ConnectionError: Если сервер не ответил
        """
        if not self.entities:
            raise ValueError("Атрибут entities не установлен. Сначала выберите сущность")

        url = f'{self.base_url}api/v1/periods'
        result = self._handle_request(url)
        if result:
            logger.info(result)
            return result
        raise ConnectionError("Сервер не ответил на запрос периодов")

    def metadata_v1(self) -> List[Dict[str, Any]]:
        """Получает метаданные для текущей сущности.

        Returns:
            Метаданные сущности

        Raises:
            ValueError: Если сущность не выбрана
            ConnectionError: Если сервер не ответил
        """
        if not self.entities:
            raise ValueError("Атрибут entities не установлен. Сначала выберите сущность")

        url = f'{self.base_url}api/v1/metadata'
        result = self._handle_request(url)
        if result:
            logger.info(result)
            return result
        raise ConnectionError("Сервер не ответил на запрос метаданных")

    def updates_v1(self, entities: str) -> List[Dict[str, Any]]:
        """Получает обновления для указанной сущности.

        Args:
            entities: Идентификатор сущности

        Returns:
            Список обновлений

        Raises:
            ConnectionError: Если сервер не ответил
        """
        self.entities = entities
        url = f'{self.base_url}api/v1/updates'
        result = self._handle_request(url)
        return result

    def close(self):
        """Закрывает сессию соединений."""
        self._session.close()

    def __enter__(self):
        """Поддержка контекстного менеджера."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Гарантированное закрытие сессии при выходе из контекста."""
        self.close()
