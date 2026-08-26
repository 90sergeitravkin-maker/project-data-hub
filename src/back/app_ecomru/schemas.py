# src/back/app_ecomru/schemas.py  (новый файл)
"""Схемы для pipeline-отчётов."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class DownloadResult(BaseModel):
    """Результат этапа скачивания."""
    status: str = Field(..., description="completed | error")
    files_downloaded: int = 0
    files_failed: int = 0
    total_size_bytes: int = 0
    duration_sec: float = 0.0
    file_paths: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """Результат этапа обработки (разбиение)."""
    status: str = Field(..., description="completed | skipped | error")
    split_performed: bool = False
    split_column: Optional[str] = None
    unique_values: int = 0
    total_rows: int = 0
    output_files_count: int = 0
    output_dir: Optional[str] = None
    checksum_result: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class PipelineReport(BaseModel):
    """Полный отчёт pipeline для Airflow."""
    task_id: str
    entity: str
    period: str
    updated_at: str
    pipeline_status: str = Field(..., description="completed | partial | failed")

    # Этапы
    download: DownloadResult
    processing: ProcessingResult

    # Метаданные
    started_at: str
    finished_at: str
    duration_sec: float = 0.0

    # Для Airflow
    report_version: int = 1
    source_topic: str = "ecomru-report"