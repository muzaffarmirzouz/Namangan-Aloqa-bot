"""Oddiy foydalanuvchilar (kanal a'zolari) bilan ishlaydigan handlerlar.

Adminlarning o'zi (cfg.admin_ids ichidagilar) bu routerga tushmaydi — ular
handlers/admin.py da alohida ishlanadi, shunda admin botga /start bossa
mijozlar menyusini emas, balki admin panelni ko'radi.
"""

import asyncio
import html
import logging
from typing import Awaitable, Callable, List

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

import database as db
from config import cfg
from keyboards import (
    BTN_APPEAL,
    BTN_BALANCE,
    BTN_CANCEL,
    BTN_DONE,
    BTN_SELL_VIDEO,
    balance_withdraw_kb,
    card_request_kb,
    main_menu_kb,
    phone_request_kb,
    subscribe_kb,
    video_status_kb,
    video_upload_kb,
    withdrawal_admin_kb,
)
from utils import build_appeal_header, build_video_header

router = Router(name="user")
router.message.filter(F.chat.type == "private", ~F.from_user.id.in_(cfg.admin_ids))

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "Bu — <b>Namanganliklar.uz</b> kanali admin bilan aloqa boti.\n\n"
    "✉️ <b>Oddiy murojaat</b> — savol, taklif, shikoyat yoki biror voqea haqida "
    "xabar bermoqchi bo'lsangiz shu tugmani bosing. Adminlar ko'rib chiqib javob "
    "qaytaradi.\n\n"
    "🎥 <b>Video sotaman</b> — hech qayerda chiqmagan, o'zingiz suratga olgan "
    "shov-shuvli/tezkor video (avariya, baxtsiz hodisa va h.k.) bo'lsa, shu "
    "tugma orqali yuboring.\n\n"
    "💰 <b>Balansim</b> — sotib olingan videolaringiz uchun to'langan summani "
    "shu yerdan kuzatib borasiz."
)


def _fmt_price(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# Bu turdagi xabarlarga (rasm/video/hujjat va h.k.) caption qo'shish mumkin —
# shu orqali kimdan kelganini pastda ko'rsatamiz.
CAPTIONABLE_TYPES = {
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.DOCUMENT,
    ContentType.AUDIO,
    ContentType.ANIMATION,
    ContentType.VOICE,
}


def _build_sender_caption(message: Message, ticket_id: int, phone: str | None) -> str:
    uname = f"@{message.from_user.username}" if message.from_user.username else "username yo'q"
    phone_line = f"\n📱 {phone}" if phone else ""
    return (
        f"👤 {message.from_user.full_name} ({uname})\n"
        f"🆔 {message.from_user.id}{phone_line}\n"
        f"🎫 Ticket #{ticket_id}"
    )


VIDEO_INTRO_TEXT = (
    "🎥 <b>Video sotish</b>\n\n"
    "❗️<b>Diqqat: hali video yubormang</b> — avval pastdagi "
    "\"📱 Raqamimni yuborish\" tugmasini bosing. Telefon raqamingizni "
    "yubormasdan turib yuborilgan video <b>qabul qilinmaydi</b>.\n\n"
    "Hali hech qayerda chiqmagan videongiz bo'lsa, biz undan sotib olishimiz "
    "mumkin.\n\n"
    "⚠️ <b>Muhim eslatmalar:</b>\n"
    "📹 Video <b>tiniq, sifatli</b> bo'lishi va undagi ma'lumotlar (joy, vaqt, "
    "voqea) <b>aniq</b> bo'lishi shart.\n"
    "💰 To'lov video <b>kanalga chiqqandan (e'lon qilingandan) keyin</b> "
    "amalga oshiriladi.\n"
    "⚖️ Noto'g'ri yoki yolg'on ma'lumot bergan bo'lsangiz, javobgarlik "
    "to'liq <b>o'zingizga</b> yuklanadi.\n"
    "🔒 Sizning shaxsingiz <b>sir saqlanishi kafolatlanadi</b> — ismingiz va "
    "ma'lumotlaringiz hech qachon oshkor qilinmaydi.\n\n"
    f"💵 Narx holatiga qarab <b>{_fmt_price(cfg.min_video_price)}–"
    f"{_fmt_price(cfg.max_video_price)} so'm</b> oralig'ida belgilanadi "
    f"(eng kami {_fmt_price(cfg.min_video_price)} so'm).\n\n"
    "👇 Davom etish uchun pastdagi tugma orqali telefon raqamingizni yuboring:"
)


async def _is_subscribed(bot: Bot, user_id: int) -> bool:
    if not cfg.require_subscription or not cfg.channel_username:
        return True
    try:
        member = await bot.get_chat_member(chat_id=f"@{cfg.channel_username.lstrip('@')}", user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception as exc:  # noqa: BLE001 - bu tekshiruv HECH QACHON /start'ni "jim" qoldirmasligi kerak
        # Masalan bot kanalga admin qilib qo'shilmagan bo'lsa, Telegram turli xil
        # xato qaytarishi mumkin (nafaqat TelegramBadRequest) — avval faqat
        # TelegramBadRequest ushlanardi, boshqa xato turi butun /start
        # funksiyasini "jim-jim" qulatib, foydalanuvchiga hech qanday javob
        # yubormay qo'yardi. Endi qanday xato bo'lishidan qat'i nazar,
        # sozlamada muammo bo'lsa foydalanuvchini bloklab qo'ymaymiz.
        logger.warning("Obunani tekshirib bo'lmadi: %s", exc)
        return True


async def _send_to_one_admin(
    admin_id: int, sender: Callable[[int], Awaitable[Message]]
) -> Message | None:
    """Bitta adminga xabar yuborishga urinadi, flood-control (429/RetryAfter)
    holatida ko'rsatilgan vaqtcha kutib qayta uradi (video/media kabi katta
    xabarlarni bir nechta chatga ketma-ket yuborganda Telegram shuni talab
    qilib qolishi mumkin — shu sabab ba'zi adminlarga yetib bormasligi
    mumkin edi, chunki bu holat ilgari umuman ushlanmagan edi)."""
    for attempt in range(3):
        try:
            return await sender(admin_id)
        except TelegramRetryAfter as exc:
            logger.warning(
                "Admin %s ga yuborishda flood-control: %s soniya kutib, qayta "
                "urinilmoqda (%s-urinish)",
                admin_id,
                exc.retry_after,
                attempt + 1,
            )
            await asyncio.sleep(exc.retry_after + 0.5)
            continue
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.warning(
                "Admin %s ga yuborib bo'lmadi (botni ishga tushirmagan/bloklagan "
                "bo'lishi mumkin): %s",
                admin_id,
                exc,
            )
            return None
        except Exception as exc:  # kutilmagan xato — logga yozib, keyingi adminga o'tamiz
            logger.exception("Admin %s ga yuborishda kutilmagan xatolik: %s", admin_id, exc)
            return None
    logger.error("Admin %s ga uch urinishdan keyin ham yuborib bo'lmadi (flood-control).", admin_id)
    return None


async def _send_to_admins(
    ticket_id: int, sender: Callable[[int], Awaitable[Message]]
) -> List[Message]:
    """Ticketga tegishli xabarni har bir adminning shaxsiy chatiga yuboradi.

    `sender(admin_id)` — bitta adminga xabar yuboruvchi async funksiya
    (masalan `bot.send_message` yoki `bot.copy_message` chaqirig'i).
    Muvaffaqiyatli yetkazilgan har bir xabar ticketga bog'lanadi (shu orqali
    o'sha admin keyinchalik shu xabarga reply qilib javob bera oladi).
    Admin botni hali ishga tushirmagan yoki bloklagan bo'lsa, shunchaki
    o'tkazib yuboriladi.
    """
    sent_messages: List[Message] = []
    for admin_id in cfg.admin_ids:
        sent = await _send_to_one_admin(admin_id, sender)
        if sent is None:
            continue
        # Eslatma: `bot.copy_message()` Telegram API darajasida faqat
        # `MessageId` obyektini qaytaradi (unda `.chat` maydoni yo'q,
        # faqat `.message_id`) — `sent.chat.id` o'rniga allaqachon ma'lum
        # bo'lgan `admin_id`dan foydalanamiz. Aynan shu joyda oldin
        # AttributeError chiqib, sikl birinchi admindan keyin to'xtab
        # qolar, videoni faqat birinchi adminga yetkazib ulgurar edi.
        await db.link_admin_message(ticket_id, admin_id, sent.message_id)
        sent_messages.append(sent)
    return sent_messages


async def _broadcast_to_admins(sender: Callable[[int], Awaitable[Message]]) -> List[Message]:
    """`_send_to_admins`ga o'xshaydi, lekin ticketga bog'lamaydi — masalan
    balansni yechib olish so'rovlari uchun (bu alohida reply-suhbat emas,
    tugma orqali boshqariladi)."""
    sent_messages: List[Message] = []
    for admin_id in cfg.admin_ids:
        sent = await _send_to_one_admin(admin_id, sender)
        if sent is None:
            continue
        sent_messages.append(sent)
    return sent_messages


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    await db.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )

    if not await _is_subscribed(bot, message.from_user.id):
        await message.answer(
            "Botdan foydalanish uchun avval kanalimizga obuna bo'ling, so'ng "
            "\"✅ Tekshirish\" tugmasini bosing.",
            reply_markup=subscribe_kb(cfg.channel_username),
        )
        return

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    if await _is_subscribed(bot, callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
        await callback.answer("Rahmat!")
    else:
        await callback.answer("Hali kanalga obuna bo'lmagansiz.", show_alert=True)


@router.message(F.text == BTN_CANCEL)
async def cancel_flow(message: Message) -> None:
    await db.set_awaiting_phone(message.from_user.id, False)
    await db.set_awaiting_card(message.from_user.id, False)
    await db.set_active_ticket(message.from_user.id, None)
    await message.answer("Bekor qilindi. Asosiy menyu 👇", reply_markup=main_menu_kb())


@router.message(F.text == BTN_DONE)
async def finish_video_upload(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or not user["active_ticket_id"]:
        await message.answer("Faol murojaat topilmadi.", reply_markup=main_menu_kb())
        return
    await db.set_active_ticket(message.from_user.id, None)
    await message.answer(
        "Rahmat! Videongiz adminlarga yuborildi, tez orada bog'lanishadi. ✅",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == BTN_APPEAL)
async def start_appeal(message: Message) -> None:
    await db.set_awaiting_phone(message.from_user.id, False)
    ticket_id = await db.create_ticket(message.from_user.id, kind="appeal")
    await db.set_active_ticket(message.from_user.id, ticket_id)

    header = build_appeal_header(
        ticket_id, message.from_user.full_name, message.from_user.username, message.from_user.id
    )
    sent_list = await _send_to_admins(
        ticket_id, lambda admin_id: message.bot.send_message(admin_id, header)
    )
    if sent_list:
        await db.set_ticket_header(ticket_id, sent_list[0].chat.id, sent_list[0].message_id)
    else:
        logger.error(
            "Ticket #%s uchun hech qaysi adminga yetkazib bo'lmadi — ADMIN_IDS "
            "to'g'ri sozlanganini va adminlar botga /start bosganini tekshiring.",
            ticket_id,
        )

    await message.answer(
        "Murojaatingizni yozing (matn, rasm, video yoki ovozli xabar — hammasi "
        "mumkin). Yuborgach, javobni shu yerda kutib turing.",
        reply_markup=video_upload_kb(),
    )


@router.message(F.text == BTN_SELL_VIDEO)
async def start_video_sale(message: Message) -> None:
    await db.set_active_ticket(message.from_user.id, None)
    await db.set_awaiting_phone(message.from_user.id, True)
    await message.answer(VIDEO_INTRO_TEXT, reply_markup=phone_request_kb())


@router.message(F.text == BTN_BALANCE)
async def show_balance(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    balance = user["balance"] if user else 0
    if balance > 0:
        await message.answer(
            f"💰 Sizning balansingiz: <b>{_fmt_price(balance)} so'm</b>\n\n"
            "Bu — sotib olingan videolaringiz uchun to'langan/to'lanadigan "
            "summa. Yana video sotsangiz, shu balansga qo'shilib boradi. "
            "Xohlasangiz hoziroq yechib olishingiz mumkin 👇",
            reply_markup=balance_withdraw_kb(),
        )
    else:
        await message.answer(
            "💰 Sizning balansingiz: <b>0 so'm</b>\n\n"
            "Video sotsangiz va u sotib olinsa, summasi shu yerga "
            "qo'shilib boradi."
        )


@router.callback_query(F.data == "wd_req")
async def cb_withdraw_request(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    balance = user["balance"] if user else 0
    if balance <= 0:
        await callback.answer("Balansingiz bo'sh.", show_alert=True)
        return

    await db.set_awaiting_card(callback.from_user.id, True)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.message.answer(
        "💳 Pulni qaysi karta raqamiga o'tkazib berishimiz kerak? Iltimos, "
        "karta raqamingizni yuboring (masalan: 8600 1234 5678 9012).",
        reply_markup=card_request_kb(),
    )
    await callback.answer()


async def _process_card_number(message: Message, user) -> None:
    """Foydalanuvchi balansini yechib olish uchun karta raqamini yuborganda
    ishga tushadi — so'rovni yaratadi va adminlarga xabar beradi."""
    card = (message.text or "").strip()
    digits_only = "".join(ch for ch in card if ch.isdigit())
    if len(digits_only) < 8:
        await message.answer(
            "Iltimos, to'g'ri karta raqamini yuboring (masalan: "
            "8600 1234 5678 9012) yoki bekor qiling.",
            reply_markup=card_request_kb(),
        )
        return

    await db.set_awaiting_card(message.from_user.id, False)

    # Balansni qayta o'qiymiz — bu vaqt oralig'ida o'zgargan bo'lishi mumkin
    fresh_user = await db.get_user(message.from_user.id) or user
    balance = fresh_user["balance"] if fresh_user else 0
    if balance <= 0:
        await message.answer("Balansingiz bo'sh.", reply_markup=main_menu_kb())
        return

    withdrawal_id = await db.create_withdrawal(message.from_user.id, balance, card)

    full_name = (
        fresh_user["full_name"] if fresh_user and fresh_user["full_name"] else message.from_user.full_name
    )
    uname = f"@{fresh_user['username']}" if fresh_user and fresh_user["username"] else "username yo'q"
    phone = fresh_user["phone"] if fresh_user and fresh_user["phone"] else "noma'lum"
    text = (
        f"💳 <b>Yechib olish so'rovi</b> #{withdrawal_id}\n"
        f"👤 {html.escape(full_name)} ({html.escape(uname)})\n"
        f"🆔 <code>{message.from_user.id}</code>\n"
        f"📱 <code>{html.escape(phone)}</code>\n"
        f"💳 Karta: <code>{html.escape(card)}</code>\n"
        f"💰 Summa: <b>{_fmt_price(balance)} so'm</b>\n\n"
        "To'lovni shu kartaga amalga oshirgach, pastdagi tugmani bosing."
    )
    await _broadcast_to_admins(
        lambda admin_id: message.bot.send_message(
            admin_id, text, reply_markup=withdrawal_admin_kb(withdrawal_id)
        )
    )

    await message.answer(
        "✅ So'rovingiz qabul qilindi. Admin tez orada tekshirib, to'lovni "
        "amalga oshiradi.",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("wd:"))
async def cb_withdraw_confirm(callback: CallbackQuery, bot: Bot) -> None:
    try:
        _, wd_id_raw, action = callback.data.split(":")
        withdrawal_id = int(wd_id_raw)
    except ValueError:
        await callback.answer("Xatolik.")
        return

    if action != "confirm":
        return  # "paid" harakati faqat handlers/admin.py da ishlanadi

    withdrawal = await db.get_withdrawal(withdrawal_id)
    if not withdrawal or withdrawal["user_tg_id"] != callback.from_user.id:
        await callback.answer("Bu so'rov sizga tegishli emas.", show_alert=True)
        return

    if withdrawal["status"] == "yakunlandi":
        await callback.answer("Bu so'rov allaqachon yakunlangan.")
        return

    await db.set_withdrawal_status(withdrawal_id, "yakunlandi")
    new_balance = await db.subtract_from_balance(callback.from_user.id, withdrawal["amount"])

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.message.answer(
        "✅ Rahmat! To'lov yakunlandi.\n\nKelajakda yana sizdan video kutib qolamiz! 🎥"
    )
    await callback.answer("Tasdiqlandi ✅")

    await _broadcast_to_admins(
        lambda admin_id: bot.send_message(
            admin_id,
            f"✅ Foydalanuvchi to'lovni tasdiqladi — yechib olish #{withdrawal_id} "
            f"yakunlandi ({_fmt_price(withdrawal['amount'])} so'm). Joriy balansi: "
            f"{_fmt_price(new_balance)} so'm.",
        )
    )


@router.message(F.text)
async def receive_text(message: Message) -> None:
    """Har qanday matnli xabar shu yerga tushadi. Agar foydalanuvchi hozir
    karta raqami yuborishini kutayotgan bo'lsak (balansni yechib olish
    oqimi), shu yerda ishlaymiz — aks holda odatdagidek adminga relay
    qilamiz (murojaat matni va h.k.)."""
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        user = await db.get_user(message.from_user.id)

    if user and user["awaiting_card"]:
        await _process_card_number(message, user)
        return

    await _relay_to_admin(message)


@router.message(F.contact)
async def receive_contact(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or not user["awaiting_phone"]:
        # "Video sotaman" oqimida emasmiz — bu shunchaki foydalanuvchi ochiq
        # ticketga (masalan murojaat ichida) yuborgan kontakt bo'lishi mumkin,
        # shuning uchun uni yo'qotmasdan odatdagidek relay qilamiz.
        await _relay_to_admin(message)
        return

    if message.contact.user_id != message.from_user.id:
        await message.answer(
            "Iltimos, faqat o'zingizning raqamingizni yuboring.",
            reply_markup=phone_request_kb(),
        )
        return

    phone = message.contact.phone_number
    await db.set_user_phone(message.from_user.id, phone)
    await db.set_awaiting_phone(message.from_user.id, False)

    ticket_id = await db.create_ticket(message.from_user.id, kind="video", phone=phone)
    await db.set_active_ticket(message.from_user.id, ticket_id)

    header = build_video_header(
        ticket_id,
        message.from_user.full_name,
        message.from_user.username,
        message.from_user.id,
        phone,
        "yangi",
        cfg.min_video_price,
        cfg.max_video_price,
    )
    sent_list = await _send_to_admins(
        ticket_id,
        lambda admin_id: message.bot.send_message(
            admin_id, header, reply_markup=video_status_kb(ticket_id)
        ),
    )
    if sent_list:
        await db.set_ticket_header(ticket_id, sent_list[0].chat.id, sent_list[0].message_id)
    else:
        logger.error(
            "Ticket #%s uchun hech qaysi adminga yetkazib bo'lmadi — ADMIN_IDS "
            "to'g'ri sozlanganini va adminlar botga /start bosganini tekshiring.",
            ticket_id,
        )

    await message.answer(
        "Rahmat! Endi video(lar)ni yuboring — <b>tiniq va sifatli</b> bo'lsin. "
        "Qaerda va qachon suratga olinganini qisqacha va <b>aniq</b> yozib "
        "qo'ysangiz, ko'rib chiqish tezlashadi.\n\n"
        "Eslatma: shaxsingiz sir saqlanadi, to'lov esa video kanalga "
        "chiqqandan keyin amalga oshiriladi.\n\n"
        "Barcha videolarni yuborib bo'lgach \"✅ Tugatdim\" tugmasini bosing.",
        reply_markup=video_upload_kb(),
    )


@router.message(F.video)
async def relay_video(message: Message) -> None:
    handled = await _relay_to_admin(message)
    if handled:
        user = await db.get_user(message.from_user.id)
        if user and user["active_ticket_id"]:
            await db.increment_video_count(user["active_ticket_id"])


@router.message()
async def relay_generic(message: Message) -> None:
    await _relay_to_admin(message)


async def _relay_to_admin(message: Message) -> bool:
    """Foydalanuvchi xabarini faol ticketga (agar bo'lsa) barcha adminlarga forward qiladi.

    True qaytaradi — agar xabar hech bo'lmasa bitta adminga yetkazilgan bo'lsa.
    """
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        user = await db.get_user(message.from_user.id)

    if user["awaiting_phone"]:
        # Bu yerga "Video sotaman" bosgan, lekin telefon raqamini ulashmasdan
        # turib video/xabar yuborgan foydalanuvchilar ham tushadi — ular
        # ko'pincha nima uchun hech narsa bo'lmayotganini tushunmay qolishadi,
        # shuning uchun xabarni imkon qadar aniq va qat'iy qilib beramiz.
        await message.answer(
            "❌ <b>Bu xabar/video qabul qilinmadi — adminga yuborilmadi.</b>\n\n"
            "Davom etish uchun avval pastdagi \"📱 Raqamimni yuborish\" "
            "tugmasini bosing, so'ng video(lar)ingizni <b>qayta yuboring</b>. "
            "Yoki \"◀️ Bekor qilish\" tugmasini bosing.",
            reply_markup=phone_request_kb(),
        )
        return False

    ticket_id = user["active_ticket_id"]
    if not ticket_id:
        await message.answer(
            "Boshlash uchun quyidagi menyudan birini tanlang 👇", reply_markup=main_menu_kb()
        )
        return False

    # Video qaysi yo'l bilan yuborilishidan qat'i nazar (masalan "Oddiy
    # murojaat" ichida ham) — agar foydalanuvchining telefon raqami hali
    # bizda yo'q bo'lsa, avval shuni so'raymiz. Video shu joyda "yo'qoladi"
    # (yuborilmaydi) — foydalanuvchi telefon ulashgach, uni qayta yuborishi
    # kerak bo'ladi.
    if message.video and not user["phone"]:
        await db.set_awaiting_phone(message.from_user.id, True)
        await message.answer(
            "❌ <b>Bu video qabul qilinmadi va adminga yuborilmadi.</b>\n\n"
            "Video yuborishdan oldin telefon raqamingizni bilishimiz kerak. "
            "Iltimos, pastdagi \"📱 Raqamimni yuborish\" tugmasini bosing — "
            "shundan keyingina videongizni <b>qayta yuboring</b>.",
            reply_markup=phone_request_kb(),
        )
        return False

    identity = _build_sender_caption(message, ticket_id, user["phone"])

    async def _copy_with_identity(admin_id: int) -> Message:
        if message.content_type in CAPTIONABLE_TYPES:
            base_caption = message.caption or ""
            new_caption = f"{identity}\n\n{base_caption}" if base_caption else identity
            if len(new_caption) > 1024:
                new_caption = new_caption[:1021] + "..."
            return await message.bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_caption,
                parse_mode=None,
            )
        return await message.bot.copy_message(
            chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id
        )

    sent_list = await _send_to_admins(ticket_id, _copy_with_identity)
    if not sent_list:
        await message.answer("Xatolik yuz berdi, birozdan so'ng qayta urinib ko'ring.")
        return False
    return True
