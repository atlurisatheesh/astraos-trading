"""Import user-provided creator lesson JSON into the local knowledge store.

Expected JSON:
{
  "lessons": [
    {
      "creator": "stockvid.telugu",
      "title": "Liquidity Sweep",
      "transcript": "Caption or transcript text...",
      "concepts": ["liquidity sweep", "intraday"]
    }
  ]
}
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.knowledge.creator_lessons import CreatorLesson, get_creator_lesson_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Import creator lesson captions/transcripts")
    parser.add_argument("json_file", help="Path to a JSON file with a lessons array")
    parser.add_argument("--name", default="", help="Output dataset name")
    args = parser.parse_args()

    source = Path(args.json_file)
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else payload.get("lessons", [])
    lessons = [CreatorLesson.from_dict(record) for record in records]

    dataset_name = args.name or source.stem
    path = get_creator_lesson_store().add_lessons(lessons, dataset_name)
    print(f"Imported {len(lessons)} creator lessons into {path}")


if __name__ == "__main__":
    main()
