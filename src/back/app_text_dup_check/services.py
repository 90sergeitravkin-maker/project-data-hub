# src/back/app_text_dup_check/download.py
import re
import math
import asyncpg

from typing import Dict, Any, List
from difflib import SequenceMatcher
from collections import Counter
from fastapi import HTTPException

from src.core.logger import logger
from src.database.manager import DBManager
from src.back.app_text_dup_check.config import DB_ALIAS
from src.back.app_text_dup_check.schemas import MatchResult


class TextService:

    # ================== БАЗОВЫЕ МЕТОДЫ ==================
    @classmethod
    async def save_text(cls, text_content: str, code: str, alias: str = DB_ALIAS) -> int:
        db = DBManager()
        query = """
        INSERT INTO app_text_dup_check.texts (content, code)
        VALUES ($1, $2)
        RETURNING id
        """
        try:
            row = await db.fetch_one(alias, query, text_content, code)
            return row["id"] if row else 0
        except Exception as e:
            logger.error(f"[TextService] Ошибка сохранения текста: {e}")
            raise

    @classmethod
    async def check_similarity(cls, text_content: str, limit: int = 5, alias: str = DB_ALIAS) -> Dict[str, Any]:
        db = DBManager()
        try:
            query = """SELECT content, code FROM app_text_dup_check.texts"""
            rows = await db.fetch_all(alias, query)
            if not rows:
                return cls._empty_result()

            texts = [r["content"] for r in rows]
            codes = [r["code"] for r in rows]

            return {
                "pg_trgm": await cls._calc_pg_trgm(db, alias, text_content, limit),
                "sequence": cls._calc_sequence(text_content, texts, codes, limit),
                "jaccard": cls._calc_jaccard(text_content, texts, codes, limit),
                "cosine": cls._calc_cosine(text_content, texts, codes, limit),
            }
        except asyncpg.exceptions.UndefinedTableError:
            logger.error(f"[TextService] Таблица 'texts' не найдена в БД '{alias}'")
            raise HTTPException(500, detail="Таблица данных не инициализирована")
        except asyncpg.exceptions.UndefinedFunctionError:
            logger.error(f"[TextService] Функция 'similarity' недоступна. Установите расширение pg_trgm")
            raise HTTPException(500, detail="Требуется расширение PostgreSQL: pg_trgm")
        except Exception as e:
            logger.error(f"[TextService] Ошибка check_similarity: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(500, detail=f"Внутренняя ошибка: {type(e).__name__}")

    # ================== ПУСТЫЙ РЕЗУЛЬТАТ ==================

    @staticmethod
    def _empty_result() -> Dict[str, List[MatchResult]]:
        return {
            "pg_trgm": [],
            "sequence": [],
            "jaccard": [],
            "cosine": [],
        }

    # ================== 1. pg_trgm (PostgreSQL similarity) ==================

    @classmethod
    async def _calc_pg_trgm(cls, db: DBManager, alias: str, text: str, limit: int) -> List[MatchResult]:
        """
        Использует встроенную функцию similarity() из расширения pg_trgm.
        Возвращает коэффициент 0..1, умножаем на 100 для процента.
        """
        query = """
        SELECT content, code, similarity(content, $1) AS s
        FROM app_text_dup_check.texts
        WHERE content % $1 OR similarity(content, $1) > 0.1
        ORDER BY s DESC
        LIMIT $2
        """
        try:
            rows = await db.fetch_all(alias, query, text, limit)
        except asyncpg.exceptions.UndefinedFunctionError:
            logger.warning("[TextService] pg_trgm недоступен, возвращаем пустой список")
            return []
        except Exception as e:
            logger.warning(f"[TextService] pg_trgm ошибка: {e}")
            return []

        return [
            MatchResult(
                percentage=round(float(r["s"]) * 100, 2),
                matched_text=r["content"],
                matched_code=r["code"],
            )
            for r in rows if r.get("s") is not None
        ]

    # ================== 2. Sequence (Longest Common Subsequence) ==================

    @staticmethod
    def _calc_sequence(text: str, texts: List[str], codes: List[str], limit: int) -> List[MatchResult]:
        """
        Сравнение через difflib.SequenceMatcher — отношение длины LCS к длине большей строки.
        """
        results = []
        for t, c in zip(texts, codes):
            ratio = SequenceMatcher(None, text, t).ratio()  # 0..1
            results.append((ratio * 100, t, c))
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            MatchResult(percentage=round(p, 2), matched_text=t, matched_code=c)
            for p, t, c in results[:limit]
        ]

    # ================== 3. Jaccard (по словам) ==================

    @staticmethod
    def _tokenize(s: str) -> List[str]:
        """Простая токенизация: приводим к lower, разбиваем по не-буквам/цифрам."""
        return re.findall(r'[\wа-яА-ЯёЁ]+', s.lower())

    @classmethod
    def _calc_jaccard(cls, text: str, texts: List[str], codes: List[str], limit: int) -> List[MatchResult]:
        """
        Jaccard similarity = |A ∩ B| / |A ∪ B| на множествах слов.
        """
        a = set(cls._tokenize(text))
        if not a:
            return []
        results = []
        for t, c in zip(texts, codes):
            b = set(cls._tokenize(t))
            if not b:
                results.append((0.0, t, c))
                continue
            inter = len(a & b)
            union = len(a | b)
            j = (inter / union) if union else 0.0
            results.append((j * 100, t, c))
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            MatchResult(percentage=round(p, 2), matched_text=t, matched_code=c)
            for p, t, c in results[:limit]
        ]

    # ================== 4. Cosine (по TF-векторам слов) ==================

    @staticmethod
    def _cosine_sim(vec_a: Counter, vec_b: Counter) -> float:
        """Косинусное сходство между двумя Counter'ами (частоты слов)."""
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0
        dot = sum(vec_a[w] * vec_b[w] for w in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @classmethod
    def _calc_cosine(cls, text: str, texts: List[str], codes: List[str], limit: int) -> List[MatchResult]:
        """
        Косинусное сходство на векторах частот слов (TF).
        """
        tokens_a = Counter(cls._tokenize(text))
        if not tokens_a:
            return []
        results = []
        for t, c in zip(texts, codes):
            tokens_b = Counter(cls._tokenize(t))
            sim = cls._cosine_sim(tokens_a, tokens_b)
            results.append((sim * 100, t, c))
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            MatchResult(percentage=round(p, 2), matched_text=t, matched_code=c)
            for p, t, c in results[:limit]
        ]
