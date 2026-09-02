from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_APPEAL = "✉️ Oddiy murojaat"
BTN_SELL_VIDEO = "🎥 Video sotaman"
BTN_BALANCE = "💰 Balansim"
BTN_SHARE_PHONE = "📱 Raqamimni yuborish"
BTN_CANCEL = "◀️ Bekor qilish"
BTN_DONE = "✅ Tugatdim"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_APPEAL)],
            [KeyboardButton(text=BTN_SELL_VIDEO)],
            [KeyboardButton(text=BTN_BALANCE)],
        ],
        resize_keyboard=True,
    )


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def video_upload_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DONE)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def subscribe_kb(channel_username: str) -> InlineKeyboardMarkup:
    username = channel_username.lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{username}")],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
        ]
    )


def balance_withdraw_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Hoziroq yechib olish", callback_data="wd_req")]
        ]
    )


def withdrawal_admin_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ To'ladim", callback_data=f"wd:{withdrawal_id}:paid")]
        ]
    )


def withdrawal_confirm_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, pul tushdi", callback_data=f"wd:{withdrawal_id}:confirm"
                )
            ]
        ]
    )


def video_status_kb(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Sotib olindi", callback_data=f"vst:{ticket_id}:bought"
                ),
                InlineKeyboardButton(
                    text="🤝 Muzokara", callback_data=f"vst:{ticket_id}:negotiate"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish", callback_data=f"vst:{ticket_id}:reject"
                ),
            ],
        ]
    )
