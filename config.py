"""
Bot sozlamalari. Barcha qiymatlar muhit o'zgaruvchilaridan (environment variables)
o'qiladi — bu Railway kabi hosting xizmatlari uchun standart usul.

Lokal ishga tushirish uchun: loyiha papkasida `.env` fayl yarating
(.env.example asosida) — python-dotenv uni avtomatik o'qiydi.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    admin_ids: list[int]
    channel_username: str
    require_subscription: bool
    db_path: str
    min_video_price: int
    max_video_price: int


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "ha")


def _parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise RuntimeError(
                f"ADMIN_IDS ichida noto'g'ri qiymat: '{part}'. Faqat Telegram "
                "foydalanuvchi ID'lari (sonlar), vergul bilan ajratilgan bo'lishi kerak."
            ) from exc
    return ids


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Railway'da Variables bo'limiga yoki "
            "lokal .env fayliga BOT_TOKEN qo'shing (BotFather'dan olinadi)."
        )

    admin_ids_raw = os.getenv("ADMIN_IDS")
    if not admin_ids_raw:
        raise RuntimeError(
            "ADMIN_IDS topilmadi. O'zingizning (yoki adminlaringizning) "
            "Telegram foydalanuvchi ID'sini Variables bo'limiga qo'shing "
            "(masalan: 123456789 yoki 123456789,987654321 — bir nechta admin "
            "uchun vergul bilan). ID'ni @userinfobot orqali bilib olishingiz mumkin."
        )
    admin_ids = _parse_admin_ids(admin_ids_raw)
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS bo'sh bo'lmasligi kerak.")

    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        channel_username=os.getenv("CHANNEL_USERNAME", ""),
        require_subscription=_get_bool("REQUIRE_SUBSCRIPTION", True),
        db_path=os.getenv("DB_PATH", "bot.db"),
        min_video_price=int(os.getenv("MIN_VIDEO_PRICE", "10000")),
        max_video_price=int(os.getenv("MAX_VIDEO_PRICE", "30000")),
    )


cfg = load_config()
