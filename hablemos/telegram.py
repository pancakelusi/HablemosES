"""Tiny wrapper around the Telegram Bot API. Each function is one HTTP request."""

import os

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method: str, payload: dict) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    resp = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data["result"]


def send_message(chat_id: str, html: str) -> dict:
    """Send an HTML-formatted message. <tg-spoiler> makes tap-to-reveal text."""
    return _call("sendMessage", {
        "chat_id": chat_id,
        "text": html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def send_quiz(chat_id: str, question: str, options: list[str], answer: int,
              explanation: str = "") -> dict:
    """Native Telegram quiz poll: it grades the answer and shows the explanation."""
    payload = {
        "chat_id": chat_id,
        "question": question,
        "options": [{"text": o} for o in options],
        "type": "quiz",
        "correct_option_id": answer,
        "is_anonymous": False,
    }
    if explanation:
        payload["explanation"] = explanation
    return _call("sendPoll", payload)


def get_updates() -> list:
    """Used once during setup to discover the group chat's id."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    resp = requests.get(API.format(token=token, method="getUpdates"), timeout=30)
    return resp.json().get("result", [])
