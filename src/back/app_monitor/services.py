# src/back/app_monitor/download.py
"""
Бизнес-логика мониторинга ресурсов.
Использует psutil (процесс), tracemalloc (аллокации Python),
и DBManager для сохранения истории.
"""
import os
import time
import asyncio
import tracemalloc
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import psutil
from fastapi import HTTPException, status

from core.logger import logger
from src.database.manager import DBManager
from src.back.app_monitor.config import (
    DB_ALIAS, RAM_WARNING_MB, RAM_CRITICAL_MB,
    SNAPSHOT_INTERVAL_SEC, TOP_N_HEAVY, HISTORY_RETENTION_DAYS,
)
from src.back.app_monitor.schemas import (
    ProcessMemoryInfo, AppMemoryStat, AppsMemoryReport,
    SnapshotRecord, HeavyRequestRecord, AlertRecord, TracemallocTop,
    MemoryDiagnostics, DiskUsageItem,
)

# === Глобальное состояние (in-memory счётчики по приложениям) ===
# Структура: {app_name: {"rss_start": int, "peak": int, "requests": int, "total_delta": int}}
_APP_STATS: Dict[str, Dict[str, Any]] = {}
_STATS_LOCK = asyncio.Lock()
_PROCESS = psutil.Process(os.getpid())
_START_TIME = time.monotonic()


class MemoryMonitorService:
    """Основной сервис мониторинга."""

    # ==================== УТИЛИТЫ ====================
    @staticmethod
    def _bytes_to_mb(b: int) -> float:
        return round(b / (1024 * 1024), 2)

    @classmethod
    def get_process_info(cls) -> ProcessMemoryInfo:
        """Текущее состояние процесса FastAPI."""
        try:
            mem = _PROCESS.memory_info()
            mem_pct = _PROCESS.memory_percent()
            cpu_pct = _PROCESS.cpu_percent(interval=0.1)
            threads = _PROCESS.num_threads()
            uptime = time.monotonic() - _START_TIME
            return ProcessMemoryInfo(
                rss_mb=cls._bytes_to_mb(mem.rss),
                vms_mb=cls._bytes_to_mb(mem.vms),
                shared_mb=cls._bytes_to_mb(getattr(mem, "shared", 0)),
                percent=round(mem_pct, 2),
                threads=threads,
                cpu_percent=round(cpu_pct, 2),
                uptime_sec=round(uptime, 1),
            )
        except Exception as e:
            error_location = "src/back/app_monitor, download.py, get_process_info"
            logger.error(f"[MONITOR] Ошибка чтения процесса: {e} | {error_location}")
            raise HTTPException(500, detail=f"Monitor error: {e}")

    # ==================== PER-REQUEST ХУКИ ====================
    @classmethod
    async def on_request_start(cls, app_name: str) -> int:
        """Вызывается в middleware ДО обработки запроса. Возвращает rss_before."""
        try:
            rss = _PROCESS.memory_info().rss
            async with _STATS_LOCK:
                if app_name not in _APP_STATS:
                    _APP_STATS[app_name] = {
                        "rss_start": rss, "peak": rss, "requests": 0,
                        "total_delta": 0, "last_snapshot_rss": rss,
                    }
                stats = _APP_STATS[app_name]
                stats["rss_start"] = rss
                if rss > stats["peak"]:
                    stats["peak"] = rss
            return rss
        except Exception as e:
            logger.debug(f"[MONITOR] on_request_start error: {e}")
            return 0

    @classmethod
    async def on_request_end(
            cls,
            app_name: str,
            method: str,
            path: str,
            status_code: int,
            duration_ms: float,
            rss_before: int,
            save_to_db: bool = True,
    ) -> None:
        """Вызывается в middleware ПОСЛЕ обработки запроса."""
        try:
            rss_after = _PROCESS.memory_info().rss
            delta = rss_after - rss_before
            delta_mb = cls._bytes_to_mb(delta)
            peak_mb = cls._bytes_to_mb(max(rss_before, rss_after))

            async with _STATS_LOCK:
                stats = _APP_STATS.get(app_name)
                if stats:
                    stats["requests"] += 1
                    stats["total_delta"] += max(0, delta)
                    if rss_after > stats["peak"]:
                        stats["peak"] = rss_after

            # Сохраняем в БД только "тяжёлые" запросы (чтобы не засорять БД)
            if save_to_db and delta_mb >= 1.0:
                db = DBManager()
                await db.execute(
                    DB_ALIAS,
                    """
                    INSERT INTO request_memory_stats
                    (app_name, method, path, status_code, duration_ms,
                     rss_before_mb, rss_after_mb, rss_delta_mb, peak_during_mb)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    app_name, method, path, status_code, duration_ms,
                    cls._bytes_to_mb(rss_before), cls._bytes_to_mb(rss_after),
                    delta_mb, peak_mb,
                )

            # Проверка порога алерта
            await cls._check_threshold(app_name, cls._bytes_to_mb(rss_after))

        except Exception as e:
            logger.debug(f"[MONITOR] on_request_end error: {e}")

    # ==================== АЛЕРТЫ ====================
    @classmethod
    async def _check_threshold(cls, app_name: str, rss_mb: float) -> None:
        """Проверяет пороги и пишет алерт в БД + лог."""
        level = None
        threshold = None
        if rss_mb >= RAM_CRITICAL_MB:
            level, threshold = "CRITICAL", RAM_CRITICAL_MB
        elif rss_mb >= RAM_WARNING_MB:
            level, threshold = "WARNING", RAM_WARNING_MB

        if not level:
            return

        try:
            db = DBManager()
            await db.execute(
                DB_ALIAS,
                """
                INSERT INTO memory_alerts (app_name, level, rss_mb, threshold_mb, message)
                VALUES ($1, $2, $3, $4, $5)
                """,
                app_name, level, rss_mb, threshold,
                f"App '{app_name}' consumed {rss_mb:.1f} MB (threshold {threshold} MB)",
            )
            logger.warning(
                f"[MONITOR ALERT] {level}: {app_name} = {rss_mb:.1f} MB "
                f"(threshold {threshold} MB)"
            )
        except Exception as e:
            logger.error(f"[MONITOR] Failed to save alert: {e}")

    # ==================== ПЕРИОДИЧЕСКИЕ СНИМКИ ====================
    @classmethod
    async def capture_snapshot(cls) -> None:
        """Сохраняет снимок по всем приложениям (вызывается из background task)."""
        try:
            process_info = cls.get_process_info()
            async with _STATS_LOCK:
                apps_snapshot = dict(_APP_STATS)

            db = DBManager()
            for app_name, stats in apps_snapshot.items():
                rss_mb = cls._bytes_to_mb(stats.get("peak", 0))
                await db.execute(
                    DB_ALIAS,
                    """
                    INSERT INTO memory_snapshots
                    (app_name, rss_mb, vms_mb, shared_mb, percent,
                     requests_count, peak_rss_mb)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    app_name,
                    cls._bytes_to_mb(stats.get("rss_start", 0)),
                    process_info.vms_mb,
                    process_info.shared_mb,
                    process_info.percent,
                    stats.get("requests", 0),
                    rss_mb,
                )

            # Сбрасываем счётчики запросов (но не peak)
            async with _STATS_LOCK:
                for stats in _APP_STATS.values():
                    stats["requests"] = 0
                    stats["total_delta"] = 0

            # Очистка старой истории
            await cls._cleanup_old_history()

            logger.debug(f"[MONITOR] Snapshot captured for {len(apps_snapshot)} apps")
        except Exception as e:
            logger.error(f"[MONITOR] capture_snapshot error: {e}", exc_info=True)

    @classmethod
    async def _cleanup_old_history(cls) -> None:
        """Удаляет записи старше HISTORY_RETENTION_DAYS."""
        try:
            db = DBManager()
            cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
            for table in ("memory_snapshots", "request_memory_stats", "memory_alerts"):
                await db.execute(
                    DB_ALIAS,
                    f"DELETE FROM {table} WHERE captured_at < $1 "
                    f"OR fired_at < $1" if table == "memory_alerts"
                    else f"DELETE FROM {table} WHERE captured_at < $1",
                    cutoff,
                )
        except Exception as e:
            logger.debug(f"[MONITOR] cleanup error: {e}")

    # ==================== ЧТЕНИЕ ДАННЫХ ====================
    @classmethod
    async def get_apps_report(cls) -> AppsMemoryReport:
        """Сводный отчёт: процесс + статистика по приложениям."""
        process_info = cls.get_process_info()
        async with _STATS_LOCK:
            apps_snapshot = dict(_APP_STATS)

        apps: List[AppMemoryStat] = []
        total_tracked = 0.0
        for app_name, stats in apps_snapshot.items():
            current_mb = cls._bytes_to_mb(stats.get("rss_start", 0))
            peak_mb = cls._bytes_to_mb(stats.get("peak", 0))
            reqs = stats.get("requests", 0)
            total_delta = stats.get("total_delta", 0)
            avg_delta = (cls._bytes_to_mb(total_delta) / reqs) if reqs > 0 else 0.0
            pct = (current_mb / process_info.rss_mb * 100) if process_info.rss_mb > 0 else 0.0
            apps.append(AppMemoryStat(
                app_name=app_name,
                current_rss_mb=current_mb,
                peak_rss_mb=peak_mb,
                requests_count=reqs,
                avg_delta_per_request_mb=round(avg_delta, 3),
                percent_of_total=round(pct, 2),
            ))
            total_tracked += current_mb

        apps.sort(key=lambda a: a.peak_rss_mb, reverse=True)
        return AppsMemoryReport(
            captured_at=datetime.now(timezone.utc),
            process=process_info,
            apps=apps,
            total_tracked_mb=round(total_tracked, 2),
            untracked_mb=round(max(0.0, process_info.rss_mb - total_tracked), 2),
        )

    @classmethod
    async def get_snapshots(cls, app_name: Optional[str], minutes: int, limit: int) -> List[SnapshotRecord]:
        db = DBManager()
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        if app_name:
            rows = await db.fetch_all(
                DB_ALIAS,
                """
                SELECT id, captured_at, app_name, rss_mb, vms_mb, percent,
                       requests_count, peak_rss_mb
                FROM memory_snapshots
                WHERE app_name = $1 AND captured_at >= $2
                ORDER BY captured_at DESC LIMIT $3
                """,
                app_name, since, limit,
            )
        else:
            rows = await db.fetch_all(
                DB_ALIAS,
                """
                SELECT id, captured_at, app_name, rss_mb, vms_mb, percent,
                       requests_count, peak_rss_mb
                FROM memory_snapshots
                WHERE captured_at >= $1
                ORDER BY captured_at DESC LIMIT $2
                """,
                since, limit,
            )
        return [SnapshotRecord.model_validate(r) for r in rows]

    @classmethod
    async def get_heavy_requests(cls, minutes: int, top_n: int, min_delta_mb: float) -> List[HeavyRequestRecord]:
        db = DBManager()
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        rows = await db.fetch_all(
            DB_ALIAS,
            """
            SELECT id, captured_at, app_name, method, path, status_code,
                   duration_ms, rss_delta_mb, peak_during_mb
            FROM request_memory_stats
            WHERE captured_at >= $1 AND rss_delta_mb >= $2
            ORDER BY rss_delta_mb DESC
            LIMIT $3
            """,
            since, min_delta_mb, top_n,
        )
        return [HeavyRequestRecord.model_validate(r) for r in rows]

    @classmethod
    async def get_alerts(cls, limit: int = 50) -> List[AlertRecord]:
        db = DBManager()
        rows = await db.fetch_all(
            DB_ALIAS,
            """
            SELECT id, fired_at, app_name, level, rss_mb, threshold_mb, message
            FROM memory_alerts
            ORDER BY fired_at DESC LIMIT $1
            """,
            limit,
        )
        return [AlertRecord.model_validate(r) for r in rows]

    # ==================== TRACEMALLOC (deep diagnostics) ====================
    @classmethod
    def get_tracemalloc_top(cls, top_n: int = 20) -> tuple[bool, float, List[TracemallocTop]]:
        """Возвращает топ-N файлов по потреблению памяти через tracemalloc."""
        if not tracemalloc.is_tracing():
            return False, 0.0, []
        try:
            snapshot = tracemalloc.take_snapshot()
            stats = snapshot.statistics("lineno")
            total = sum(s.size for s in stats) / (1024 * 1024)
            top: List[TracemallocTop] = []
            for stat in stats[:top_n]:
                frame = stat.traceback[0]
                top.append(TracemallocTop(
                    file=frame.filename,
                    line=frame.lineno,
                    size_mb=round(stat.size / (1024 * 1024), 3),
                    count=stat.count,
                ))
            return True, round(total, 2), top
        except Exception as e:
            logger.error(f"[MONITOR] tracemalloc error: {e}")
            return False, 0.0, []

    @classmethod
    async def get_full_diagnostics(cls) -> MemoryDiagnostics:
        """Полная диагностика: процесс + tracemalloc + приложения."""
        process_info = cls.get_process_info()
        report = await cls.get_apps_report()
        enabled, total_mb, top = cls.get_tracemalloc_top(TOP_N_HEAVY)
        return MemoryDiagnostics(
            process=process_info,
            tracemalloc_enabled=enabled,
            tracemalloc_total_mb=total_mb,
            tracemalloc_top=top,
            apps=report.apps,
        )

    # ==================== BACKGROUND TASK ====================
    @classmethod
    async def snapshot_loop(cls) -> None:
        """Бесконечный цикл снимков. Запускается в lifespan."""
        logger.info(f"[MONITOR] Snapshot loop started (interval={SNAPSHOT_INTERVAL_SEC}s)")
        while True:
            try:
                await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
                await cls.capture_snapshot()
            except asyncio.CancelledError:
                logger.info("[MONITOR] Snapshot loop cancelled")
                break
            except Exception as e:
                logger.error(f"[MONITOR] snapshot_loop error: {e}", exc_info=True)
                await asyncio.sleep(10)


    @classmethod
    def get_disk_usage(cls, paths: List[str]) -> List[DiskUsageItem]:
        import psutil
        result = []
        for path in paths:
            try:
                # Нормализуем путь для Windows
                normalized_path = os.path.normpath(path)
                logger.info(f"[MONITOR] Проверка диска для пути: {normalized_path}")
                if not os.path.exists(normalized_path):
                    logger.warning(f"[MONITOR] Путь не существует: {normalized_path}")
                    continue
                usage = psutil.disk_usage(normalized_path)
                result.append(DiskUsageItem(
                    path=normalized_path,
                    total_gb=round(usage.total / (1024**3), 2),
                    used_gb=round(usage.used / (1024**3), 2),
                    free_gb=round(usage.free / (1024**3), 2),
                    percent=round(usage.percent, 1),
                ))
            except Exception as e:
                logger.warning(f"[MONITOR] Ошибка для пути {path}: {e}")
        return result