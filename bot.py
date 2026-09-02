"""Namanganliklar.uz — admin bilan aloqa boti.

Ishga tushirish: `python bot.py`
Talab qilinadigan muhit o'zgaruvchilari uchun .env.example fayliga qarang.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import cfg
from handlers import admin, user


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    await db.init_db(cfg.db_path)
    logger.info("Ma'lumotlar bazasi tayyor: %s", cfg.db_path)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # MemoryStorage: admin "necha so'mga sotib oldingiz?" javobini kutayotgan
    # holatni saqlaydi. Jarayon qayta ishga tushsa (masalan Railway qayta
    # deploy qilganda) bu holat tozalanadi — admin shunchaki tugmani qayta
    # bosishi kifoya, ma'lumot yo'qolmaydi.
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot ishga tushdi (polling). Admin ID(lar): %s", cfg.admin_ids)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
