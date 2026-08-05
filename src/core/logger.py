# src/back/config/logger.py
"""
Настройка логирования с выравниванием, фильтрацией секретов и относительными путями.
(Без использования colorlog)
"""
import re
import sys
import logging

from pathlib import Path
from logging.handlers import RotatingFileHandler


def mask_sensitive(value: str | None, visible_chars: int = 4) -> str:
    if not value:
        return "None"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    half = visible_chars // 2
    return value[:half] + "*" * (len(value) - visible_chars) + value[-half:]


class SensitiveDataFilter(logging.Filter):
    SENSITIVE_EXACT_NAMES = {
        'api_key', 'apikey', 'secret_key', 'password', 'token',
        'auth_token', 'access_token', 'private_key', 'client_secret'
    }
    SENSITIVE_PATTERNS = [
        r'((?:api_?key|token|password|secret|auth)\s*[:=]\s*)[\'"]?([a-zA-Z0-9_\-]{16,})[\'"]?',
        r'(Bearer\s+)([a-zA-Z0-9_\-\.]{20,})',
        r'([?&](?:api_?key|token|secret)=)([a-zA-Z0-9_\-]{16,})',
    ]
    _env_values: set[str] = set()
    _env_values_loaded: bool = False

    def __init__(self, strict_mode: bool = True, load_env_values: bool = True):
        super().__init__()
        self.strict_mode = strict_mode
        if load_env_values and not self._env_values_loaded:
            self._load_env_values()
            self._env_values_loaded = True

    @classmethod
    def _load_env_values(cls, min_length: int = 8):
        import os
        cls._env_values.clear()
        for key, value in os.environ.items():
            if (not value or len(value) < min_length or
                    key.startswith('_') or
                    key in ('PATH', 'PWD', 'HOME', 'USER', 'SHELL', 'TERM', 'LANG')):
                continue
            cls._env_values.add(value)
            from urllib.parse import quote
            encoded = quote(value, safe='')
            if encoded != value:
                cls._env_values.add(encoded)
            if len(value) > 50:
                import hashlib
                cls._env_values.add(hashlib.sha256(value.encode()).hexdigest()[:16])

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._mask_message(record.msg)
        if record.args:
            if isinstance(record.args, (list, tuple)):
                record.args = tuple(self._safe_mask_arg(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self._safe_mask_arg(v) for k, v in record.args.items()}
        return True

    def _mask_message(self, message: str) -> str:
        result = message
        for pattern in self.SENSITIVE_PATTERNS:
            def selective_mask(match: re.Match) -> str:
                prefix = match.group(1)
                value = match.group(2)
                if self._is_safe_value(value):
                    return match.group(0)
                return f"{prefix}***"

            result = re.sub(pattern, selective_mask, result, flags=re.IGNORECASE)
        for var_name in self.SENSITIVE_EXACT_NAMES:
            pattern = re.compile(rf'\b{re.escape(var_name)}\s*[:=]\s*[\'"]?([^\s\'",\}}\]]+)[\'"]?', re.IGNORECASE)
            result = pattern.sub(
                lambda m: m.group(0).split('=')[0] + '=***' if '=' in m.group(0)
                else m.group(0).split(':')[0] + ': ***', result
            )
        for env_value in self._env_values:
            if env_value and len(env_value) >= 4 and env_value in result:
                if not self._is_safe_value(env_value):
                    result = result.replace(env_value, '***')
        return result

    def _is_safe_value(self, value: str) -> bool:
        if not value or len(value) < (16 if self.strict_mode else 8):
            return True
        if value.startswith(('http://', 'https://', 'ftp://', '/', '\\', 'file://')):
            return True
        if '.' in value and len(value.split('.')[-1]) <= 4:
            return True
        if value.isdigit() or value.replace('.', '').replace('-', '').isdigit():
            return True
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', value, re.I):
            return True
        if re.match(r'^\d{4}-\d{2}-\d{2}', value):
            return True
        return False

    def _safe_mask_arg(self, arg) -> str:
        if not isinstance(arg, str):
            return arg
        if arg in self._env_values and not self._is_safe_value(arg):
            return '***'
        if len(arg) >= 20 and not self._is_safe_value(arg):
            return mask_sensitive(arg, visible_chars=4)
        return arg


def config_logging(
        level=logging.INFO,
        log_file: str | Path | None = 'logs/app.log',
        mask_sensitive_data: bool = True,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        log_base_path: str | Path | None = None
) -> None:
    log_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(lineno)4d | %(filename)s | %(funcName)s | %(message)s'

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        root_logger.handlers.clear()

    # Используем стандартный Formatter вместо colorlog
    console_formatter = logging.Formatter(
        fmt=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level)
    if mask_sensitive_data:
        console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)

    if log_file:
        base_dir = Path(log_base_path) if log_base_path else Path(__file__).resolve().parents[2]
        log_path = base_dir / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
            delay=True
        )
        file_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt='%Y-%m-%d %H:%M:%S'))
        file_handler.setLevel(level)
        if mask_sensitive_data:
            file_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(file_handler)

    # === ПОДАВЛЯЕМ ШУМНЫЕ БИБЛИОТЕКИ ===
    for noisy_logger in (
            "kafka",
            "kafka.conn",
            "kafka.coordinator",
            "kafka.consumer",
            "kafka.producer",
            "kafka.protocol",
            "aiokafka",
            "aiokafka.conn",
            "aiokafka.consumer",
            "aiokafka.producer",
            "aiokafka.helpers",
            "urllib3",
            "asyncio",
            "websockets",
            "httpx",
            "httpcore",
            "aiohttp",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)
