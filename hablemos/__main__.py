"""HablemosES command line.

    python -m hablemos send               # scheduled run (GitHub Actions calls this)
    python -m hablemos send --dry-run     # print what would go out right now
    python -m hablemos send --date 2026-12-01 --slot evening --test
                                          # send one slot to your private test chat
    python -m hablemos preview lessons/2026-11-29.yaml [--day mon]
    python -m hablemos check   lessons/2026-11-29.yaml
    python -m hablemos vocab                          # Saturday overview
    python -m hablemos vocab add perro "dog" --pos noun
    python -m hablemos vocab set perro reinforce
    python -m hablemos close lessons/2026-11-29.yaml  # log a finished week
    python -m hablemos chat-id                        # setup helper
"""

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from . import lessons as L
from . import render as R


def _plain(html: str) -> str:
    """Terminal-friendly version of a message: spoilers shown as [[...]]."""
    out = html.replace("<tg-spoiler>", "[[").replace("</tg-spoiler>", "]]")
    out = re.sub(r"</?(b|i)>", "", out)
    return out.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _print_items(items):
    for kind, item in items:
        if kind == "text":
            print(_plain(item))
        else:
            print(f"[QUIZ] {item['question']}")
            for i, o in enumerate(item["options"]):
                print(f"   {'✔' if i == item['answer'] else ' '} {o}")
            if item["explanation"]:
                print(f"   💡 {item['explanation']}")
        print("-" * 48)


def _deliver(items, chat_id):
    from . import telegram as T
    for kind, item in items:
        if kind == "text":
            T.send_message(chat_id, item)
        else:
            T.send_quiz(chat_id, item["question"], item["options"], item["answer"],
                        item["explanation"])


def _items_for(week, dkey, slot):
    items = []
    for block in L.blocks_for(week, dkey, slot):
        items += R.render(block, week)
    return items


# ---------- commands ----------

def cmd_send(a):
    cfg = L.load_config()
    now = L.now_local(cfg)
    day = date.fromisoformat(a.date) if a.date else now.date()
    state = L.load_state()

    slots = [a.slot] if a.slot else L.due_slots(cfg, now, state)
    if not slots:
        print(f"{now:%a %H:%M} — nothing due.")
        return

    path = L.lesson_path(day)
    if not path.exists():
        print(f"⚠️  No lesson file for this week: {path.name}")
        return
    week = L.load_week(path)

    chat_id = os.environ.get("TELEGRAM_TEST_CHAT_ID" if a.test else "TELEGRAM_CHAT_ID")
    for slot in slots:
        items = _items_for(week, L.day_key(day), slot)
        print(f"== {day} {L.day_key(day)} {slot}: {len(items)} item(s)")
        if a.dry_run or not items:
            _print_items(items)
        else:
            _deliver(items, chat_id)
        # Manual/test sends don't mark the slot as done.
        if not (a.dry_run or a.test or a.slot):
            state[f"{day.isoformat()}:{slot}"] = now.isoformat(timespec="minutes")
    L.save_state(state)


def cmd_preview(a):
    week = L.load_week(Path(a.file))
    for dkey, slot, block in L.all_blocks(week):
        if a.day and dkey != a.day:
            continue
        print(f"\n######## {dkey.upper()} · {slot} · {block['type']}")
        _print_items(R.render(block, week))


def cmd_check(a):
    path = Path(a.file)
    week = L.load_week(path)
    vocab = L.load_vocab()
    errors, warnings = [], []

    if str(week.get("week_of")) != path.stem:
        errors.append(f"week_of ({week.get('week_of')}) doesn't match file name ({path.stem})")
    if date.fromisoformat(path.stem).weekday() != 6:
        errors.append("file name must be a Sunday's date")

    for dkey, slot, block in L.all_blocks(week):
        try:
            for p in R.problems(R.render(block, week)):
                errors.append(f"{dkey}/{slot}: {p}")
        except Exception as e:  # noqa: BLE001 — report any malformed block
            errors.append(f"{dkey}/{slot}: can't render ({type(e).__name__}: {e})")

    text = L.week_text(week)
    verb = week["verb"]
    verb_forms = [f for forms in verb["tenses"].values() for f in forms]
    if not L.word_used(verb["infinitive"], text, verb_forms):
        warnings.append(f"verb '{verb['infinitive']}' never appears in the week's Spanish")

    words = week.get("words") or {}
    for group in ("new", "reinforce"):
        for w in words.get(group) or []:
            if w not in vocab:
                errors.append(f"'{w}' ({group}) is not in vocab.yaml — add it with `vocab add`")
            elif not L.word_used(w, text, vocab[w].get("forms")):
                warnings.append(f"'{w}' ({group}) isn't used in any story/dialogue "
                                f"(or only in a form not listed under `forms`)")

    for e in errors:
        print(f"❌ {e}")
    for w in warnings:
        print(f"⚠️  {w}")
    if not errors and not warnings:
        print("✅ Looks good.")
    sys.exit(1 if errors else 0)


def cmd_vocab(a):
    vocab = L.load_vocab()
    if a.action == "add":
        if a.word in vocab:
            sys.exit(f"'{a.word}' already exists.")
        vocab[a.word] = {"en": a.en, "pos": a.pos, "status": "new", "times_seen": 0}
        L.save_vocab(vocab)
        print(f"Added {a.word} — {a.en}")
        return
    if a.action == "set":
        if a.word not in vocab or a.en not in L.STATUSES:
            sys.exit(f"Usage: vocab set WORD {{{'|'.join(L.STATUSES)}}}")
        vocab[a.word]["status"] = a.en
        L.save_vocab(vocab)
        print(f"{a.word} → {a.en}")
        return

    # Overview for Saturday prep
    by = {s: [] for s in L.STATUSES}
    for w, info in vocab.items():
        by.setdefault(info.get("status", "new"), []).append(w)
    print(f"📚 {len(vocab)} words — " + ", ".join(f"{s}: {len(by[s])}" for s in L.STATUSES))
    print("\n🔁 Marked to reinforce:", ", ".join(sorted(by["reinforce"])) or "—")

    cutoff = (date.today() - timedelta(weeks=3)).isoformat()
    stale = sorted(w for w, i in vocab.items()
                   if i.get("status") in ("learning", "reinforce")
                   and str(i.get("last_seen", "")) < cutoff)
    print("⏳ Learning but not seen in 3+ weeks:", ", ".join(stale) or "—")
    print("🆕 Added but never used yet:", ", ".join(sorted(by["new"])) or "—")


def cmd_close(a):
    """Log a finished week: bump counts, set last_seen, promote new → learning."""
    week = L.load_week(Path(a.file))
    vocab = L.load_vocab()
    text = L.week_text(week)
    wk = str(week["week_of"])
    verb = week["verb"]["infinitive"]
    touched = []
    for w, info in vocab.items():
        forms = info.get("forms") or []
        if w == verb:
            forms = forms + [f for fs in week["verb"]["tenses"].values() for f in fs]
        if L.word_used(w, text, forms):
            info["times_seen"] = info.get("times_seen", 0) + 1
            info["last_seen"] = wk
            info.setdefault("first_week", wk)
            if info.get("status") == "new":
                info["status"] = "learning"
            touched.append(w)
    L.save_vocab(vocab)
    print(f"Logged week {wk}: {len(touched)} words seen → {', '.join(sorted(touched))}")


def cmd_chat_id(a):
    from . import telegram as T
    seen = {}
    for u in T.get_updates():
        msg = u.get("message") or u.get("my_chat_member") or {}
        chat = msg.get("chat", {})
        if chat:
            seen[chat["id"]] = chat.get("title") or chat.get("first_name")
    if not seen:
        print("No chats yet — send a message in the group (and to the bot directly), then retry.")
    for cid, name in seen.items():
        print(f"{cid}\t{name}")


def main():
    p = argparse.ArgumentParser(prog="hablemos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--test", action="store_true", help="send to TELEGRAM_TEST_CHAT_ID")
    s.add_argument("--date", help="YYYY-MM-DD (default: today)")
    s.add_argument("--slot", help="force a slot, e.g. morning / evening")
    s.set_defaults(fn=cmd_send)

    s = sub.add_parser("preview")
    s.add_argument("file")
    s.add_argument("--day", choices=L.DAY_KEYS)
    s.set_defaults(fn=cmd_preview)

    s = sub.add_parser("check")
    s.add_argument("file")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("vocab")
    s.add_argument("action", nargs="?", choices=["add", "set"])
    s.add_argument("word", nargs="?")
    s.add_argument("en", nargs="?", help="English meaning (add) or status (set)")
    s.add_argument("--pos", default="")
    s.set_defaults(fn=cmd_vocab)

    s = sub.add_parser("close")
    s.add_argument("file")
    s.set_defaults(fn=cmd_close)

    s = sub.add_parser("chat-id")
    s.set_defaults(fn=cmd_chat_id)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
