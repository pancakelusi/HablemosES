# Hablemos 🇪🇸

A weekly Spanish routine delivered by a Telegram bot to a small group: a learner, a practice partner, and the bot.
Built for learners who **understand more than they can say**, so the focus is speaking and recall.

- **Sunday:** verb of the week card + the week's words
- **Mon–Fri mornings:** a 5–10 min read (micro-story, dialogue, fill-in-the-blanks) plus a
  "say it out loud" recall drill (English shown, Spanish hidden)
- **Mon–Fri evenings:** a conversation prompt for the learner and partner, with starter phrases
- **Voice challenges:** prompts to record a short voice note in the group
- **Saturday:** optional quiz (native Telegram quiz polls)

English translations are hidden behind **tap-to-reveal spoilers**, so help comes in steps:
key words first, then one sentence at a time.

## How it works

```
lessons/YYYY-MM-DD.yaml   ← one file per week (named for its Sunday)
vocab/vocab.yaml          ← the vocabulary bank
config.yaml               ← time zone + send times
        │
GitHub Actions (every 30 min) → python -m hablemos send → Telegram
        │
state/sent.json           ← what's already gone out (no double-sends)
```

## One-time setup

1. **Create the bot.** In Telegram, message `@BotFather` → `/newbot` → copy the token.
2. **Make the group.** Create a group with the learner, add the bot, and send any message in it.
   Also send the bot a direct message. That private chat is your test channel.
3. **Find the chat ids:**
   ```bash
   pip install -r requirements.txt
   export TELEGRAM_BOT_TOKEN=xxxx
   python -m hablemos chat-id      # group ids are negative numbers
   ```
4. **Add repo secrets** (Settings → Secrets and variables → Actions):
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (the group), `TELEGRAM_TEST_CHAT_ID` (your DM).
5. **Try it:** Actions → *Send lessons* → *Run workflow* with a date + slot and "test" checked.
   The message lands in your DM so you can see exactly what the group will get.

> 🔒 The bot token only ever lives in GitHub **Secrets**, never in a file in this public repo.
> If it leaks, regenerate it with `/revoke` in @BotFather and update the secret.

## The Saturday ritual

```bash
python -m hablemos close lessons/2026-11-29.yaml   # log the week that just ended
python -m hablemos vocab                            # what to reinforce, what's gone stale
python -m hablemos vocab add perro "dog (m.)" --pos noun
python -m hablemos vocab set querer reinforce

# draft next week's file (Claude can write a first draft from the vocab overview)
python -m hablemos check   lessons/2026-12-06.yaml  # limits, missing vocab, unused words
python -m hablemos preview lessons/2026-12-06.yaml  # read the whole week in the terminal
git add -A && git commit -m "Week of Dec 6" && git push
```

`check` warns if a word you listed for the week never appears in its stories, so reinforcement
words actually get used.

## Lesson file block types

| type | what it sends |
|---|---|
| `verb_card` | verb + conjugation tables + examples + the week's words |
| `story` / `dialogue` | Spanish lines, each with a hidden English line; optional `glosses`, `question` |
| `gap_fill` | sentences with `___`, answers hidden |
| `recall` | English shown, Spanish hidden: say it aloud, then tap (optional `hint`) |
| `voice` | a voice-note challenge for the group, with starters |
| `conversation` | prompt + `starters` + `questions` for the two of you |
| `quiz` | Telegram quiz polls (`answer` is the 0-based index of the right option) |
| `note` | any free text (optional hidden `en`) |

A slot can hold one block or a list of blocks. `**bold**` and `_italic_` work in text.
