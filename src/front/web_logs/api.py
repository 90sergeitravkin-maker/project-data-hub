# src/front/web_logs/api.py
import re
from pathlib import Path
from typing import Optional, List, Dict
from collections import deque
from fastapi import APIRouter, Request, Query, HTTPException, status
from fastapi.responses import HTMLResponse

from src.front.web_logs.config import templates, TAG_NAME, LOG_FILE, MAX_LINES
from src.core.logger import logger

router = APIRouter(tags=[TAG_NAME])

# Паттерн разбора строки лога (формат из core/logger.py)
# 2026-07-02 13:15:12 | INFO     |   30 | main.py | lifespan | message
_LOG_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*"
    r"(?P<level>[A-Z]+)\s*\|\s*(?P<line>\d+)\s*\|\s*"
    r"(?P<file>[^|]+?)\s*\|\s*(?P<func>[^|]+?)\s*\|\s*(?P<msg>.*)$"
)

LEVEL_CLASSES = {
    "DEBUG":    "lvl-debug",
    "INFO":     "lvl-info",
    "WARNING":  "lvl-warn",
    "ERROR":    "lvl-error",
    "CRITICAL": "lvl-crit",
}


def _read_tail(path: Path, n: int) -> List[str]:
    """Эффективное чтение последних N строк (без загрузки всего файла)."""
    if not path.exists():
        return []
    with path.open("rb") as f:
        return [line.decode("utf-8", errors="replace").rstrip("\n")
                for line in deque(f, maxlen=n)]


def _parse_line(raw: str) -> Dict[str, str]:
    m = _LOG_RE.match(raw)
    if not m:
        return {"time": "", "level": "", "line": "", "file": "",
                "func": "", "msg": raw, "raw": raw, "cls": "lvl-raw"}
    d = m.groupdict()
    d["cls"] = LEVEL_CLASSES.get(d["level"].strip(), "lvl-raw")
    d["raw"] = raw
    return d


@router.get("/view", response_class=HTMLResponse, summary="Просмотр логов")
async def view_logs(
    request: Request,
    lines: int = Query(MAX_LINES, ge=10, le=5000, description="Количество строк"),
    level: Optional[str] = Query(None, description="Фильтр: DEBUG|INFO|WARNING|ERROR|CRITICAL"),
    search: Optional[str] = Query(None, description="Поиск по сообщению"),
    auto: int = Query(0, ge=0, le=60, description="Авто-обновление, сек (0=выкл)"),
):
    if not LOG_FILE.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Файл логов не найден: {LOG_FILE}")

    raw_lines = _read_tail(LOG_FILE, lines)
    parsed = [_parse_line(l) for l in raw_lines]

    if level:
        lvl = level.upper()
        parsed = [p for p in parsed if p["level"].strip() == lvl]
    if search:
        s = search.lower()
        parsed = [p for p in parsed if s in p["raw"].lower()]

    return templates.TemplateResponse(
        request=request,
        name="web_logs/view.html",
        context={
            "logs": parsed,
            "total": len(parsed),
            "file": str(LOG_FILE),
            "file_size_kb": round(LOG_FILE.stat().st_size / 1024, 1),
            "lines": lines,
            "level": level or "",
            "search": search or "",
            "auto": auto,
            "levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    )