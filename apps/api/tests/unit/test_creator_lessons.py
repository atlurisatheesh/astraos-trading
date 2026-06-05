"""Tests for user-provided creator lesson memory."""

from pathlib import Path

from src.knowledge.creator_lessons import (
    CreatorLesson,
    CreatorLessonStore,
    get_creator_lesson_prompt,
    get_creator_lesson_store,
)


def test_creator_lesson_store_search(tmp_path: Path):
    store = CreatorLessonStore(data_dir=tmp_path)
    store.add_lessons(
        [
            CreatorLesson(
                creator="stockvid.telugu",
                title="Liquidity Sweep",
                transcript="Wait for the liquidity sweep, reclaim, and defined stop loss.",
                concepts=["liquidity sweep", "intraday"],
                language="Telugu",
            )
        ],
        "test_lessons",
    )

    results = store.search("liquidity sweep intraday")
    assert len(results) == 1
    assert results[0]["creator"] == "stockvid.telugu"
    assert results[0]["title"] == "Liquidity Sweep"


def test_seed_lessons_are_available():
    lessons = get_creator_lesson_store().search("bullish marubozu", k=3)
    assert any(lesson["creator"] == "stockvid.telugu" for lesson in lessons)


def test_creator_prompt_includes_matching_context():
    prompt = get_creator_lesson_prompt("explain liquidity sweep")
    assert "Creator lesson memory" in prompt
    assert "stockvid.telugu" in prompt
