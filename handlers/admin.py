"""Adminning shaxsiy chatida ishlaydigan handlerlar: javob yuborish (reply),
video-takliflar holatini boshqarish va sotib olingan videolar statistikasi.

Bu bot uchun alohida guruh kerak emas — har bir admin botga o'zi /start
bosgach, murojaat va video-takliflar to'g'ridan-to'g'ri o'sha adminning
shaxsiy chatiga keladi va admin xuddi shu yerda reply qilib javob beradi.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
from config import cfg
from keyboards import balance_withdraw_kb, video_status_kb, withdrawal_confirm_kb
from utils import build_video_header, fmt_price

router = Router(name="admin")
router.message.filter(F.chat.id.in_(cfg.admin_ids))
router.callback_query.filter(F.message.chat.id.in_(cfg.admin_ids))

logger = logging.getLogger(__name__)


class AdminStates(StatesGroup):
    awaiting_price = State()


STATUS_ACTION_LABELS = {
    "bought": "sotib_olindi",
    "reject": "rad_etildi",
    "negotiate": "muzokara",
}

USER_NOTIFICATIONS = {
    "reject": (
        "Video uchun rahmat, ammo hozircha bizga mos kelmadi. Boshqa "
        "voqealar bo'lsa, murojaat qiling."
    ),
    "negotiate": "Videongiz ko'rib chiqilmoqda, admin siz bilan bog'lanadi.",
}

ADMIN_HELP_TEXT = (
    "🛠 <b>Admin panel</b>\n\n"
    "Foydalanuvchilardan kelgan murojaat va video-takliflar shu yerga "
    "tushadi. Javob berish uchun kelgan xabarga (yoki shu foydalanuvchidan "
    "kelgan istalgan xabarga) <b>reply</b> qiling — javobingiz avtomatik "
    "unga yetkaziladi.\n\n"
    "/stats — umumiy statistika\n"
    "/bought — sotib olingan videolar ro'yxati (narxi bilan)"
)


# ---------- boshlanish / yordam ----------

@router.message(CommandStart())
async def admin_start(message: Message) -> None:
    await message.answer(ADMIN_HELP_TEXT)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    stats = await db.get_stats()
    await message.reply(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {stats.total_users}\n"
        f"✉️ Murojaatlar: {stats.total_appeals}\n\n"
        f"🎥 Video takliflar (jami): {stats.total_video_offers}\n"
        f"⏳ Ko'rib chiqilmoqda: {stats.videos_pending}\n"
        f"✅ Sotib olingan videolar: <b>{stats.videos_bought} ta</b>\n"
        f"❌ Rad etilgan videolar: {stats.videos_rejected}\n\n"
        f"💰 Videolarga sarflangan jami summa: <b>{fmt_price(stats.total_spent)} so'm</b>\n"
        f"💳 Foydalanuvchilarda qolgan (hali yechilmagan) balans: "
        f"<b>{fmt_price(stats.outstanding_balance)} so'm</b>\n\n"
        "Batafsil ro'yxat uchun /bought yozing."
    )


@router.message(Command("bought"))
async def cmd_bought(message: Message) -> None:
    rows = await db.list_bought_videos(limit=20)
    if not rows:
        await message.reply("Hozircha sotib olingan video yo'q.")
        return

    lines = ["🎥 <b>Sotib olingan videolar</b> (oxirgi 20 tasi):\n"]
    total = 0
    for row in rows:
        price = row["price"] or 0
        total += price
        uname = f"@{row['username']}" if row["username"] else "username yo'q"
        name = row["full_name"] or "Noma'lum"
        date = (row["created_at"] or "")[:10]
        lines.append(f"#{row['ticket_id']} — {name} ({uname}) — {fmt_price(price)} so'm — {date}")

    lines.append(f"\n💰 Jami (shu ro'yxatda): <b>{fmt_price(total)} so'm</b>")
    await message.reply("\n".join(lines))


# ---------- narx kiritish (FSM) ----------

@router.message(StateFilter(AdminStates.awaiting_price))
async def receive_price(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")

    raw = (message.text or "").strip().lower()
    if raw in ("bekor", "bekor qilish", "/cancel", "cancel"):
        await state.clear()
        await message.answer("Bekor qilindi.")
        return

    cleaned = raw.replace(" ", "").replace("so'm", "").replace("som", "").replace(",", "")
    if not cleaned.isdigit():
        await message.answer(
            "Iltimos, faqat summani raqamda yuboring (masalan: 25000), yoki "
            "\"bekor\" deb yozing."
        )
        return  # holat saqlanib qoladi, admin qayta urinishi mumkin

    price = int(cleaned)
    await state.clear()

    if not ticket_id:
        await message.answer("⚠️ Xatolik: ticket topilmadi.")
        return

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await message.answer("⚠️ Xatolik: ticket topilmadi.")
        return

    await db.set_ticket_status(ticket_id, "sotib_olindi")
    await db.set_ticket_price(ticket_id, price)
    new_balance = await db.add_to_balance(ticket["user_tg_id"], price)

    await _refresh_header(bot, ticket_id)

    try:
        await bot.send_message(
            ticket["user_tg_id"],
            "🎉 Tabriklaymiz! Videongiz <b>sotib olindi</b> "
            f"(<b>{fmt_price(price)} so'm</b>).\n\n"
            f"💰 Joriy balansingiz: <b>{fmt_price(new_balance)} so'm</b>.\n"
            "Kelajakda yana video yuborsangiz, balansingizga qo'shilib "
            "boradi. Xohlasangiz hoziroq yechib olishingiz mumkin 👇",
            reply_markup=balance_withdraw_kb(),
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        pass

    await message.answer(
        f"✅ Qayd etildi: #{ticket_id} — {fmt_price(price)} so'm. Foydalanuvchi "
        f"balansi: {fmt_price(new_balance)} so'm."
    )


async def _refresh_header(bot: Bot, ticket_id: int) -> None:
    """Ticketning header xabarini (narx/holat bilan) yangilaydi."""
    ticket = await db.get_ticket(ticket_id)
    if not ticket or not ticket["header_chat_id"] or not ticket["header_message_id"]:
        return
    user = await db.get_user(ticket["user_tg_id"])
    header = build_video_header(
        ticket_id,
        user["full_name"] if user else "Noma'lum",
        user["username"] if user else None,
        ticket["user_tg_id"],
        ticket["phone"] or "-",
        ticket["status"],
        cfg.min_video_price,
        cfg.max_video_price,
        price=ticket["price"],
    )
    try:
        await bot.edit_message_text(
            chat_id=ticket["header_chat_id"],
            message_id=ticket["header_message_id"],
            text=header,
            reply_markup=video_status_kb(ticket_id),
        )
    except TelegramBadRequest:
        pass


# ---------- foydalanuvchiga javob (reply) ----------

@router.message(F.reply_to_message)
async def handle_admin_reply(message: Message, bot: Bot) -> None:
    ticket_id = await db.find_ticket_by_admin_message(
        message.chat.id, message.reply_to_message.message_id
    )
    if not ticket_id:
        await message.reply(
            "⚠️ Bu xabar biror ticketga bog'liq emas — javob yuborilmadi."
        )
        return

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        return

    try:
        await bot.copy_message(
            chat_id=ticket["user_tg_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except TelegramForbiddenError:
        await message.reply(
            "⚠️ Yuborib bo'lmadi — foydalanuvchi botni bloklagan bo'lishi mumkin."
        )
        return
    except TelegramBadRequest as exc:
        logger.error("Javobni yuborib bo'lmadi: %s", exc)
        await message.reply("⚠️ Yuborishda xatolik yuz berdi.")
        return

    # Adminning javobiga ham reply qilish mumkin bo'lishi uchun (suhbat davom etishi)
    await db.link_admin_message(ticket_id, message.chat.id, message.message_id)

    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id, message_id=message.message_id, reaction=[{"type": "emoji", "emoji": "👍"}]
        )
    except Exception:  # noqa: BLE001 - reaction ixtiyoriy, hech qanday sabab bilan asosiy oqimni buzmasligi kerak
        pass


# ---------- video holati tugmalari ----------

@router.callback_query(F.data.startswith("vst:"))
async def handle_video_status(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    try:
        _, ticket_id_raw, action = callback.data.split(":")
        ticket_id = int(ticket_id_raw)
    except ValueError:
        await callback.answer("Noto'g'ri buyruq.")
        return

    if action not in STATUS_ACTION_LABELS:
        await callback.answer("Noma'lum amal.")
        return

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket topilmadi.", show_alert=True)
        return

    if action == "bought":
        await state.set_state(AdminStates.awaiting_price)
        await state.update_data(ticket_id=ticket_id)
        await callback.message.answer(
            "💰 Necha so'mga sotib oldingiz? Summani raqamda yuboring "
            "(masalan: 25000). Bekor qilish uchun \"bekor\" deb yozing."
        )
        await callback.answer()
        return

    status = STATUS_ACTION_LABELS[action]
    await db.set_ticket_status(ticket_id, status)
    await _refresh_header(bot, ticket_id)

    notification = USER_NOTIFICATIONS.get(action)
    if notification:
        try:
            await bot.send_message(ticket["user_tg_id"], notification)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass

    await callback.answer("Holat yangilandi ✅")


# ---------- balansni yechib olish: admin "to'ladim" deb tasdiqlaydi ----------

@router.callback_query(F.data.startswith("wd:"))
async def handle_withdrawal_paid(callback: CallbackQuery, bot: Bot) -> None:
    try:
        _, wd_id_raw, action = callback.data.split(":")
        withdrawal_id = int(wd_id_raw)
    except ValueError:
        await callback.answer("Noto'g'ri buyruq.")
        return

    if action != "paid":
        return  # "confirm" harakati foydalanuvchi tomonida, handlers/user.py da ishlanadi

    withdrawal = await db.get_withdrawal(withdrawal_id)
    if not withdrawal:
        await callback.answer("So'rov topilmadi.", show_alert=True)
        return

    if withdrawal["status"] != "so_ralgan":
        await callback.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    await db.set_withdrawal_status(withdrawal_id, "admin_tolladi")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(
        f"⏳ #{withdrawal_id}: to'lov yuborilgan deb belgilandi. Foydalanuvchi "
        "tasdiqlashini kutmoqda."
    )
    await callback.answer("Belgilandi ✅")

    try:
        await bot.send_message(
            withdrawal["user_tg_id"],
            f"💳 Admin sizga <b>{fmt_price(withdrawal['amount'])} so'm</b> yubordi.\n\n"
            "Pul hisobingizga (kartangizga) tushdimi? Tasdiqlang 👇",
            reply_markup=withdrawal_confirm_kb(withdrawal_id),
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        await callback.message.answer(
            "⚠️ Foydalanuvchiga xabar yuborib bo'lmadi (botni bloklagan bo'lishi mumkin)."
        )


# ---------- boshqa hollarda yo'l-yo'riq ----------

@router.message()
async def admin_fallback(message: Message) -> None:
    """Admin biror xabarga reply qilmasdan erkin matn yozsa, yo'l-yo'riq beramiz.

    Bu handler har doim ishlaydi (filtrsiz), shuning uchun admin uchun bu
    faylning oxirida turishi shart — aks holda ustidagi handlerlar ishlamay
    qoladi.
    """
    await message.answer(ADMIN_HELP_TEXT)
