"""Turns lesson YAML blocks into Telegram-ready messages.

Every renderer returns a list of outgoing items:
    ("text", "<html string>")
    ("quiz", {"question": ..., "options": [...], "answer": 0, "explanation": ...})

Translations use Telegram spoilers (<tg-spoiler>): the English is hidden
until tapped, so the learner can reveal help in increments:
    1. read the Spanish
    2. tap a key-word gloss
    3. tap a single sentence's translation
"""

import html
import re

TELEGRAM_TEXT_LIMIT = 4096
PRONOUNS = ["yo", "tú", "él/ella/usted", "nosotros", "ellos/ustedes"]
TENSE_LABELS = {
    "presente": "Presente",
    "preterito": "Pretérito (pasado)",
    "imperfecto": "Imperfecto",
    "futuro": "Futuro",
    "condicional": "Condicional",
    "ir_a": "Ir a + infinitivo",
}


def fmt(text: str) -> str:
    """Escape HTML, then allow **bold** and _italic_ in lesson files."""
    out = html.escape(str(text).strip(), quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", out)
    return out


def spoiler(text: str) -> str:
    return f"<tg-spoiler>{fmt(text)}</tg-spoiler>"


def _header(emoji: str, title: str) -> str:
    return f"{emoji} <b>{fmt(title)}</b>"


def _glosses(glosses: dict) -> list[str]:
    if not glosses:
        return []
    lines = ["", "🔍 <i>Palabras clave</i> (toca para ver)"]
    lines += [f"• <b>{fmt(es)}</b> — {spoiler(en)}" for es, en in glosses.items()]
    return lines


# ---------- block renderers ----------

def verb_card(block: dict, week: dict) -> list:
    v = week["verb"]
    lines = [
        _header("📌", f"Verbo de la semana: {v['infinitive']}"),
        f"<i>{fmt(v['meaning'])}</i>",
    ]
    if v.get("notes"):
        lines += ["", fmt(v["notes"])]
    for tense in block.get("tenses") or list(v["tenses"]):
        forms = v["tenses"][tense]
        lines += ["", f"<b>{TENSE_LABELS.get(tense, tense)}</b>"]
        lines += [f"{p} → <b>{fmt(f)}</b>" for p, f in zip(PRONOUNS, forms)]
    if v.get("examples"):
        lines += ["", "<i>Ejemplos</i>"]
        lines += [f"• {fmt(e['es'])}\n   {spoiler(e['en'])}" for e in v["examples"]]
    words = week.get("_vocab_words", [])
    if words:
        lines += ["", "🧺 <i>Palabras de la semana</i>"]
        lines += [f"• <b>{fmt(w)}</b> — {spoiler(en)}" for w, en in words]
    return [("text", "\n".join(lines))]


def story(block: dict, week: dict) -> list:
    """Micro-story or dialogue. Each line: {es, en} plus optional speaker."""
    emoji = "💬" if block["type"] == "dialogue" else "📖"
    lines = [_header(emoji, block.get("title", "Historia"))]
    if block.get("intro"):
        lines.append(f"<i>{fmt(block['intro'])}</i>")
    lines += _glosses(block.get("glosses"))
    lines.append("")
    for ln in block["lines"]:
        speaker = f"<b>{fmt(ln['speaker'])}:</b> " if ln.get("speaker") else ""
        lines.append(f"{speaker}{fmt(ln['es'])}")
        lines.append(f"   ↳ {spoiler(ln['en'])}")
    if block.get("question"):
        lines += ["", f"❓ {fmt(block['question']['es'])}", f"   ↳ {spoiler(block['question']['en'])}"]
    return [("text", "\n".join(lines))]


def gap_fill(block: dict, week: dict) -> list:
    lines = [_header("✏️", block.get("title", "Completa las frases")),
             "<i>Piensa la respuesta, luego toca para comprobar.</i>", ""]
    for i, item in enumerate(block["items"], 1):
        lines.append(f"{i}. {fmt(item['es'])}")
        reveal = item["answer"] + (f" — {item['en']}" if item.get("en") else "")
        lines.append(f"   ↳ {spoiler(reveal)}")
    return [("text", "\n".join(lines))]


def recall(block: dict, week: dict) -> list:
    """Active recall: English shown, Spanish hidden. Say it out loud, then tap."""
    lines = [_header("🧠", block.get("title", "Dilo en voz alta")),
             "<i>Lee el inglés, dilo en español en voz alta, luego toca para comprobar.</i>", ""]
    for i, item in enumerate(block["items"], 1):
        hint = f"  <i>(pista: {fmt(item['hint'])}…)</i>" if item.get("hint") else ""
        lines.append(f"{i}. {fmt(item['en'])}{hint}")
        lines.append(f"   ↳ {spoiler(item['es'])}")
    return [("text", "\n".join(lines))]


CONVO_STYLE = {
    # type: (emoji, default title, closing line)
    "conversation": ("🗣️", "Charla de hoy", "¡A hablar! 🇪🇸"),
    "voice": ("🎙️", "Reto de voz",
              "Graba una nota de voz aquí en el grupo (30–60 segundos). ¡Sin miedo a los errores!"),
}


def conversation(block: dict, week: dict) -> list:
    emoji, default_title, closing = CONVO_STYLE[block["type"]]
    lines = [_header(emoji, block.get("title", default_title)),
             fmt(block["prompt"]["es"]),
             f"↳ {spoiler(block['prompt']['en'])}"]
    if block.get("starters"):
        lines += ["", "<i>Para empezar:</i>"]
        lines += [f"• {fmt(s['es'])}  {spoiler(s['en'])}" for s in block["starters"]]
    if block.get("questions"):
        lines += ["", "<i>Preguntas:</i>"]
        lines += [f"• {fmt(q['es'])}  {spoiler(q['en'])}" for q in block["questions"]]
    lines += ["", block.get("closing", closing)]
    return [("text", "\n".join(lines))]


def note(block: dict, week: dict) -> list:
    text = fmt(block["text"])
    if block.get("en"):
        text += f"\n\n↳ {spoiler(block['en'])}"
    return [("text", text)]


def quiz(block: dict, week: dict) -> list:
    intro = block.get("intro", "Quiz del sábado — opcional, ¡pero divertido! 🎉")
    items = [("text", _header("🎯", intro))]
    for q in block["questions"]:
        items.append(("quiz", {
            "question": q["question"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": q.get("explanation", ""),
        }))
    return items


RENDERERS = {
    "verb_card": verb_card,
    "story": story,
    "dialogue": story,
    "gap_fill": gap_fill,
    "recall": recall,
    "conversation": conversation,
    "voice": conversation,
    "note": note,
    "quiz": quiz,
}


def render(block: dict, week: dict) -> list:
    kind = block.get("type")
    if kind not in RENDERERS:
        raise ValueError(f"Unknown block type: {kind!r}")
    return RENDERERS[kind](block, week)


def problems(items: list) -> list[str]:
    """Check Telegram's limits so a bad lesson fails on Saturday, not Tuesday."""
    errs = []
    for kind, item in items:
        if kind == "text" and len(item) > TELEGRAM_TEXT_LIMIT:
            errs.append(f"message is {len(item)} chars (limit {TELEGRAM_TEXT_LIMIT})")
        if kind == "quiz":
            q = item["question"]
            if len(q) > 300:
                errs.append(f"quiz question over 300 chars: {q[:40]}…")
            if not 2 <= len(item["options"]) <= 10:
                errs.append(f"quiz needs 2–10 options: {q[:40]}…")
            if any(len(o) > 100 for o in item["options"]):
                errs.append(f"quiz option over 100 chars: {q[:40]}…")
            if not 0 <= item["answer"] < len(item["options"]):
                errs.append(f"quiz answer index out of range: {q[:40]}…")
            if len(item["explanation"]) > 200:
                errs.append(f"quiz explanation over 200 chars: {q[:40]}…")
    return errs
