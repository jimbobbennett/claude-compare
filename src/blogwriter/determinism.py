"""Hashing, the brief lockfile, and harness version capture.

Small module, but it is what makes a result defensible: every run records the
exact bytes it was given and the exact harness that produced it, so a style
difference can be attributed to the model rather than to drift.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIEFS_DIR = REPO_ROOT / "briefs"
LOCK_PATH = BRIEFS_DIR / "briefs.lock.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class BriefIntegrityError(RuntimeError):
    """A brief is missing, unlocked, or no longer matches its recorded hash.

    Hard failure by design: a changed brief means results are not comparable
    with anything produced earlier, and a silent pass would hide that.
    """


# --- harness versions -------------------------------------------------------


def capture_versions() -> dict[str, str]:
    """Record the harness, so a re-run months later is not mistaken for a
    like-for-like comparison when the CLI or SDK has moved underneath it."""
    try:
        import anthropic

        sdk_version = getattr(anthropic, "__version__", "unknown")
    except Exception:  # pragma: no cover - import failure is reported, not fatal
        sdk_version = "unknown"

    return {
        "anthropic_sdk": sdk_version,
        "python": platform.python_version(),
        "platform": f"{platform.system()}-{platform.machine()}",
    }


# --- brief lockfile ---------------------------------------------------------


@dataclass(frozen=True)
class BriefRecord:
    slug: str
    sha256: str
    research_model: str
    generated_at: str

    def to_json(self) -> dict[str, str]:
        return {
            "sha256": self.sha256,
            "research_model": self.research_model,
            "generated_at": self.generated_at,
        }


def read_lock() -> dict[str, BriefRecord]:
    if not LOCK_PATH.exists():
        return {}
    raw = json.loads(LOCK_PATH.read_text())
    return {
        slug: BriefRecord(slug=slug, **entry)
        for slug, entry in raw.get("briefs", {}).items()
    }


def write_lock(records: dict[str, BriefRecord], versions: dict[str, str]) -> None:
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "lock_version": 1,
        "updated_at": utc_now(),
        "harness": versions,
        "briefs": {slug: rec.to_json() for slug, rec in sorted(records.items())},
    }
    LOCK_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def lock_digest() -> str:
    """One hash covering every locked brief, stamped into each run manifest."""
    records = read_lock()
    if not records:
        return "empty"
    joined = "\n".join(f"{slug}:{rec.sha256}" for slug, rec in sorted(records.items()))
    return sha256_text(joined)


def brief_path(slug: str) -> Path:
    return BRIEFS_DIR / f"{slug}.md"


def load_verified_brief(slug: str) -> tuple[str, str]:
    """Return ``(brief_text, sha256)``, failing hard on any integrity problem."""
    path = brief_path(slug)
    if not path.exists():
        raise BriefIntegrityError(
            f"no brief for {slug!r} at {path}. Run: blogwriter-research"
        )

    records = read_lock()
    if slug not in records:
        raise BriefIntegrityError(
            f"brief {slug!r} exists but is not in {LOCK_PATH.name}. "
            "Regenerate it with: blogwriter-research --refresh-briefs --only " + slug
        )

    actual = sha256_file(path)
    expected = records[slug].sha256
    if actual != expected:
        raise BriefIntegrityError(
            f"brief {slug!r} has changed since it was locked.\n"
            f"  expected {expected}\n  actual   {actual}\n"
            "Results would not be comparable with earlier runs. Either restore the "
            "brief, or accept the new input with: "
            f"blogwriter-research --refresh-briefs --only {slug}"
        )

    return path.read_text(), actual


def print_stderr(msg: str) -> None:
    print(msg, file=sys.stderr)
