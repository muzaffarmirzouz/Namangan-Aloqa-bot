"""Adminlar uchun xabar matnlarini shakllantiruvchi yordamchi funksiyalar."""

STATUS_LABELS = {
    "yangi": "🆕 Yangi",
    "muzokara": "🤝 Muzokarada",
    "sotib_olindi": "✅ Sotib olindi",
    "rad_etildi": "❌ Rad etildi",
}


def fmt_price(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def build_appeal_header(ticket_id: int, full_name: str, username: str | None, tg_id: int) -> str:
    uname = f"@{username}" if username else "username yo'q"
    return (
        f"🆕 Yangi murojaat #{ticket_id}\n"
        f"👤 {full_name} ({uname})\n"
        f"🆔 <code>{tg_id}</code>\n\n"
        f"Javob berish uchun ushbu xabarga (yoki shu foydalanuvchidan kelgan "
        f"istalgan xabarga) reply qiling — javobingiz avtomatik unga yetkaziladi."
    )


def build_video_header(
    ticket_id: int,
    full_name: str,
    username: str | None,
    tg_id: int,
    phone: str,
    status: str,
    min_price: int,
    max_price: int,
    price: int | None = None,
) -> str:
    uname = f"@{username}" if username else "username yo'q"
    status_text = STATUS_LABELS.get(status, status)
    min_fmt = fmt_price(min_price)
    max_fmt = fmt_price(max_price)

    if status == "sotib_olindi" and price is not None:
        price_line = f"💰 Sotib olindi: <b>{fmt_price(price)} so'm</b>"
    else:
        price_line = f"💰 Taxminiy narx: {min_fmt}–{max_fmt} so'm (holatiga qarab)"

    return (
        f"🎥 Yangi video taklif #{ticket_id}\n"
        f"👤 {full_name} ({uname})\n"
        f"🆔 <code>{tg_id}</code>\n"
        f"📱 <code>{phone}</code>\n"
        f"{price_line}\n"
        f"📌 Holat: {status_text}\n\n"
        f"Muzokara uchun ushbu xabarga (yoki foydalanuvchidan kelgan video "
        f"xabarga) reply qiling. Holatni pastdagi tugmalar orqali belgilang."
    )
