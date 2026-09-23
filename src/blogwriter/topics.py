"""The topic set.

Two axes are recorded per topic, because either could confound a style
measurement:

- **genre** -- claudisms surface unevenly across registers, so a set that is
  all technical explainers would over- or under-state the effect.
- **domain** -- an AI-only set cannot separate "this model's voice" from "how
  anything writes about dense technical material". Spanning travel, cooking,
  games and books gives the constructions room to appear (or not).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .determinism import REPO_ROOT

DEFAULT_TOPICS_PATH = REPO_ROOT / "topics.yaml"


@dataclass(frozen=True)
class Topic:
    slug: str
    topic: str
    genre: str
    domain: str = "unspecified"


def load_topics(path: Path | None = None) -> list[Topic]:
    path = path or DEFAULT_TOPICS_PATH
    if not path.exists():
        raise FileNotFoundError(f"topics file not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    entries = raw.get("topics") or []
    if not entries:
        raise ValueError(f"no topics defined in {path}")

    topics: list[Topic] = []
    seen: set[str] = set()
    for entry in entries:
        slug = str(entry["slug"]).strip()
        if slug in seen:
            raise ValueError(f"duplicate topic slug: {slug}")
        seen.add(slug)
        topics.append(
            Topic(
                slug=slug,
                topic=str(entry["topic"]).strip(),
                genre=str(entry.get("genre", "unspecified")).strip(),
                domain=str(entry.get("domain", "unspecified")).strip(),
            )
        )
    return topics


def find_topic(topics: list[Topic], slug: str) -> Topic:
    for topic in topics:
        if topic.slug == slug:
            return topic
    raise KeyError(
        f"unknown topic slug {slug!r}. Known slugs: {', '.join(t.slug for t in topics)}"
    )
