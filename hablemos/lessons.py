"""Loading config, weekly lesson files, the vocab bank, and send state."""

import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"
LESSONS = ROOT / "lessons"
VOCAB = ROOT / "vocab" / "vocab.yaml"
STATE = ROOT / "state" / "sent.json"

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
STATUSES = ["new", "learning", "reinforce", "known"]


# ---------- config & time ----------

def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def now_local(cfg: dict) -> datetime:
    return datetime.now(ZoneInfo(cfg["timezone"]))


def week_start(d: date) -> date:
    """Weeks run Sunday → Saturday. Returns that week's Sunday."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def day_key(d: date) -> str:
    return DAY_KEYS[d.weekday()]


# ---------- lessons ----------

def lesson_path(d: date) -> Path:
    return LESSONS / f"{week_start(d).isoformat()}.yaml"


def load_week(path: Path) -> dict:
    week = yaml.safe_load(path.read_text())
    vocab = load_vocab()
    words = week.get("words") or {}
    listed = (words.get("new") or []) + (words.get("reinforce") or [])
    week["_vocab_words"] = [(w, vocab.get(w, {}).get("en", "?")) for w in listed]
    return week


def blocks_for(week: dict, dkey: str, slot: str) -> list[dict]:
    entry = (week.get("days") or {}).get(dkey, {}).get(slot)
    if entry is None:
        return []
    return entry if isinstance(entry, list) else [entry]


def all_blocks(week: dict):
    """Yields (day, slot, block) for every block in the week, in order."""
    for dkey in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        for slot in (week.get("days") or {}).get(dkey, {}):
            for block in blocks_for(week, dkey, slot):
                yield dkey, slot, block


def week_text(week: dict) -> str:
    """All Spanish text in the week, lowercased — used for vocab coverage checks."""
    chunks = []

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key in ("es", "answer", "question", "options"):
            chunks.append(node)

    walk(week.get("days"))
    return " ".join(chunks).lower()


def word_used(word: str, text: str, forms: list[str] | None = None) -> bool:
    for w in [word] + list(forms or []):
        if re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", text):
            return True
    return False


# ---------- vocab bank ----------

def load_vocab() -> dict:
    if not VOCAB.exists():
        return {}
    return yaml.safe_load(VOCAB.read_text()) or {}


def save_vocab(vocab: dict) -> None:
    # Keep the explanatory comment block at the top of the file.
    header = ""
    if VOCAB.exists():
        lines = VOCAB.read_text().splitlines(keepends=True)
        header = "".join(l for l in lines[:next((i for i, l in enumerate(lines)
                                                   if l.strip() and not l.startswith("#")),
                                                  len(lines))])
    ordered = dict(sorted(vocab.items(), key=lambda kv: kv[0]))
    body = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, width=100)
    VOCAB.write_text(header + body)


# ---------- send state (prevents double-sends) ----------

def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    keep = dict(sorted(state.items())[-120:])  # last ~2 months
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(keep, indent=2) + "\n")


def due_slots(cfg: dict, now: datetime, state: dict) -> list[str]:
    """Slots whose time has passed today, inside the send window, not yet sent.

    The window makes this robust to GitHub's cron running late, and to
    daylight-saving changes, since times are computed in local time.
    """
    window = timedelta(hours=cfg.get("send_window_hours", 3))
    due = []
    for slot, hhmm in cfg["slots"].items():
        h, m = map(int, hhmm.split(":"))
        at = datetime.combine(now.date(), time(h, m), tzinfo=now.tzinfo)
        key = f"{now.date().isoformat()}:{slot}"
        if at <= now < at + window and key not in state:
            due.append(slot)
    return due
