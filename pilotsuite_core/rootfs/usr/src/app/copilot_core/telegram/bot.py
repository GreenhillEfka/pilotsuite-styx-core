"""
Telegram Bot for PilotSuite -- lightweight long-polling bot.

Uses raw ``requests`` calls to the Telegram Bot API (no extra dependency).
Messages are forwarded to the PilotSuite chat system and responses sent back.

Config (addon options -> telegram section):
  token:            Bot token from @BotFather
  allowed_chat_ids: List of allowed Telegram chat IDs (empty = allow all)
"""

import logging
import re
import threading
import time

import requests

logger = logging.getLogger(__name__)

# Telegram bot tokens look like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567
_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")


class TelegramBot:
    """Simple Telegram bot that bridges messages to PilotSuite chat."""

    def __init__(self, token: str, allowed_chat_ids: list = None):
        self.token = token
        self.allowed_chat_ids = set(int(c) for c in (allowed_chat_ids or []) if c)
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._running = False
        self._thread = None
        self._chat_handler = None
        self._bot_username: str | None = None
        self._consecutive_errors = 0

    @staticmethod
    def validate_token(token: str) -> bool:
        """Validate Telegram bot token format (does not test API connectivity)."""
        return bool(token and _TOKEN_PATTERN.match(token))

    def verify_token(self) -> bool:
        """Call Telegram getMe to verify the token works. Returns True on success."""
        try:
            resp = requests.get(f"{self._base_url}/getMe", timeout=10)
            data = resp.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                self._bot_username = bot_info.get("username", "unknown")
                logger.info(
                    "Telegram token verified — bot: @%s (id=%s)",
                    self._bot_username,
                    bot_info.get("id"),
                )
                return True
            logger.error("Telegram getMe failed: %s", data.get("description", data))
            return False
        except requests.RequestException as exc:
            logger.error("Telegram getMe network error: %s", exc)
            return False

    def set_chat_handler(self, handler):
        """Set the function(text) -> str that processes chat messages."""
        self._chat_handler = handler

    def start(self):
        """Start long-polling in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._consecutive_errors = 0
        self._thread = threading.Thread(target=self._poll_loop, name="telegram-bot", daemon=True)
        self._thread.start()
        logger.info("Telegram bot started (long-polling)")

    def stop(self):
        """Stop the polling loop and wait for the thread to finish."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    @property
    def running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------

    def _poll_loop(self):
        while self._running:
            try:
                updates = self._get_updates()
                self._consecutive_errors = 0
                for update in updates:
                    self._handle_update(update)
            except requests.ConnectionError:
                self._consecutive_errors += 1
                backoff = min(5 * self._consecutive_errors, 60)
                logger.warning(
                    "Telegram connection lost (attempt %d), retrying in %ds",
                    self._consecutive_errors,
                    backoff,
                )
                time.sleep(backoff)
            except Exception:
                self._consecutive_errors += 1
                logger.exception("Telegram poll error")
                time.sleep(5)

    def _get_updates(self) -> list:
        resp = requests.get(
            f"{self._base_url}/getUpdates",
            params={"offset": self._offset, "timeout": 30},
            timeout=35,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram getUpdates failed: %s", data)
            time.sleep(2)
            return []
        updates = data.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    def _handle_update(self, update: dict):
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")

        if not text or not chat_id:
            return

        # ACL check
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            self._send_message(chat_id, "Zugriff verweigert. Chat-ID nicht freigegeben.")
            return

        logger.info("Telegram msg from %s: %s", chat_id, text[:80])

        if self._chat_handler:
            try:
                response = self._chat_handler(text)
                self._send_message(chat_id, response)
            except Exception:
                logger.exception("Chat handler error for Telegram message")
                self._send_message(chat_id, "Fehler bei der Verarbeitung.")
        else:
            self._send_message(chat_id, "Chat-System nicht verfuegbar.")

    def send_message(self, chat_id: int, text: str):
        """Public API for sending proactive messages (e.g. notifications)."""
        self._send_message(chat_id, text)

    def _send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown"):
        try:
            resp = requests.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                timeout=10,
            )
            if not resp.json().get("ok"):
                # Retry without parse_mode (markdown may have broken)
                requests.post(
                    f"{self._base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                    timeout=10,
                )
        except Exception:
            logger.exception("Failed to send Telegram message to %s", chat_id)
