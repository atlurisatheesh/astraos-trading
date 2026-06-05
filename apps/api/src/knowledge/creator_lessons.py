"""Creator lesson knowledge base for short-form trading education.

This module intentionally does not scrape social platforms. It loads captions,
transcripts, or notes that the user explicitly provides and makes them available
to the analyst agent as a lightweight local knowledge source.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "creator_lessons"


@dataclass
class CreatorLesson:
    """A single educational lesson from a creator post or reel."""

    creator: str
    title: str
    transcript: str
    concepts: list[str] = field(default_factory=list)
    language: str = ""
    source_url: str = ""
    source_type: str = "instagram"
    source_note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreatorLesson":
        concepts = data.get("concepts") or []
        if isinstance(concepts, str):
            concepts = [c.strip() for c in concepts.split(",") if c.strip()]
        return cls(
            creator=str(data.get("creator", "")).strip(),
            title=str(data.get("title", "")).strip(),
            transcript=str(data.get("transcript", "")).strip(),
            concepts=[str(c).strip() for c in concepts if str(c).strip()],
            language=str(data.get("language", "")).strip(),
            source_url=str(data.get("source_url", "")).strip(),
            source_type=str(data.get("source_type", "instagram")).strip(),
            source_note=str(data.get("source_note", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "creator": self.creator,
            "title": self.title,
            "transcript": self.transcript,
            "concepts": self.concepts,
            "language": self.language,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "source_note": self.source_note,
        }


class CreatorLessonStore:
    """Loads and searches local creator lesson JSON files."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self._lessons: list[CreatorLesson] | None = None

    def load(self, force: bool = False) -> list[CreatorLesson]:
        if self._lessons is not None and not force:
            return self._lessons

        self.data_dir.mkdir(parents=True, exist_ok=True)
        lessons: list[CreatorLesson] = []

        for path in sorted(self.data_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                records = raw if isinstance(raw, list) else raw.get("lessons", [])
                for record in records:
                    lesson = CreatorLesson.from_dict(record)
                    if lesson.creator and lesson.title and lesson.transcript:
                        lessons.append(lesson)
            except Exception as exc:
                logger.warning("Creator lesson file skipped", path=str(path), error=str(exc))

        self._lessons = lessons
        return lessons

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Simple lexical search that works without embedding dependencies."""
        query_terms = {
            token.strip().lower()
            for token in query.replace("/", " ").replace("-", " ").split()
            if len(token.strip()) >= 3
        }
        if not query_terms:
            return []

        scored: list[tuple[int, CreatorLesson]] = []
        for lesson in self.load():
            haystack = " ".join(
                [lesson.creator, lesson.title, lesson.transcript, " ".join(lesson.concepts)]
            ).lower()
            score = sum(1 for term in query_terms if term in haystack)
            if score:
                scored.append((score, lesson))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"score": score, **lesson.to_dict()}
            for score, lesson in scored[:k]
        ]

    def add_lessons(self, lessons: list[CreatorLesson], filename: str) -> Path:
        """Persist lessons into a JSON file and refresh the in-memory cache."""
        safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in ("_", "-")).strip()
        if not safe_name:
            safe_name = "creator_lessons"
        path = self.data_dir / f"{safe_name}.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"lessons": [lesson.to_dict() for lesson in lessons]}, indent=2),
            encoding="utf-8",
        )
        self.load(force=True)
        return path


_store: CreatorLessonStore | None = None


def get_creator_lesson_store() -> CreatorLessonStore:
    global _store
    if _store is None:
        _store = CreatorLessonStore()
    return _store


def get_creator_lesson_prompt(query: str, k: int = 3) -> str:
    """Return compact prompt context for matching creator lessons."""
    lessons = get_creator_lesson_store().search(query, k=k)
    if not lessons:
        return ""

    lines = [
        "Creator lesson memory from user-provided captions/transcripts:",
    ]
    for lesson in lessons:
        concepts = ", ".join(lesson.get("concepts", []))
        lines.append(
            f"- {lesson['creator']} | {lesson['title']} | Concepts: {concepts}. "
            f"Lesson: {lesson['transcript'][:700]}"
        )
    lines.append(
        "Use these as educational context only. Do not copy creator wording verbatim, "
        "do not imply guaranteed profit, and always keep risk controls first."
    )
    return "\n".join(lines)
