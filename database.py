"""
Ma'lumotlar bazasi qatlami. SQLite (aiosqlite) ishlatiladi — kichik va
o'rta hajmdagi botlar uchun to'liq yetarli, alohida server talab qilmaydi.

Jadvallar:
- users            : har bir foydalanuvchi (profil, telefon, faol ticket)
- tickets          : har bir murojaat/video-taklif "chizig'i" (thread)
- ticket_messages  : admin guruhidagi xabar ID -> ticket moslashuvi
                      (admin javob/reply bosganda qaysi ticketga tegishli
                      ekanini shu jadval orqali topamiz)
"""

import datetime
from dataclasses import dataclass
from typing import Optional

import aiosqlite

_db_path = "bot.db"


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


async def init_db(db_path: str) -> None:
    global _db_path
    _db_path = db_path
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                active_ticket_id INTEGER,
                awaiting_phone INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                created_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                status TEXT DEFAULT 'yangi',
                phone TEXT,
                price INTEGER,
                video_count INTEGER DEFAULT 0,
                header_chat_id INTEGER,
                header_message_id INTEGER,
                created_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                admin_chat_id INTEGER NOT NULL,
                admin_message_id INTEGER NOT NULL,
                created_at TEXT
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticket_messages_lookup "
            "ON ticket_messages (admin_chat_id, admin_message_id)"
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'so_ralgan',
                created_at TEXT
            )
            """
        )
        # Eski (price/balance ustunisiz) bazalar bilan moslik uchun — agar
        # jadval allaqachon mavjud bo'lsa-yu, ustun bo'lmasa, shu yerda
        # qo'shamiz.
        for alter_sql in (
            "ALTER TABLE tickets ADD COLUMN price INTEGER",
            "ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0",
        ):
            try:
                await db.execute(alter_sql)
            except aiosqlite.OperationalError:
                pass  # ustun allaqachon bor
        await db.commit()


# ---------- users ----------

async def get_or_create_user(tg_id: int, username: Optional[str], full_name: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO users (tg_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,
                                              full_name=excluded.full_name
            """,
            (tg_id, username, full_name, _now()),
        )
        await db.commit()


async def get_user(tg_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return await cur.fetchone()


async def set_awaiting_phone(tg_id: int, value: bool) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET awaiting_phone = ? WHERE tg_id = ?", (1 if value else 0, tg_id)
        )
        await db.commit()


async def set_user_phone(tg_id: int, phone: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("UPDATE users SET phone = ? WHERE tg_id = ?", (phone, tg_id))
        await db.commit()


async def set_active_ticket(tg_id: int, ticket_id: Optional[int]) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET active_ticket_id = ? WHERE tg_id = ?", (ticket_id, tg_id)
        )
        await db.commit()


async def add_to_balance(tg_id: int, amount: int) -> int:
    """Balansga summa qo'shadi va yangi balansni qaytaradi."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, tg_id)
        )
        await db.commit()
        cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return row[0] if row else amount


async def subtract_from_balance(tg_id: int, amount: int) -> int:
    """Balansdan summani ayiradi (0 dan pastga tushmaydi) va yangi balansni qaytaradi."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET balance = MAX(balance - ?, 0) WHERE tg_id = ?", (amount, tg_id)
        )
        await db.commit()
        cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


# ---------- tickets ----------

async def create_ticket(user_tg_id: int, kind: str, phone: Optional[str] = None) -> int:
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            "INSERT INTO tickets (user_tg_id, kind, phone, created_at) VALUES (?, ?, ?, ?)",
            (user_tg_id, kind, phone, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_ticket(ticket_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return await cur.fetchone()


async def set_ticket_header(ticket_id: int, chat_id: int, message_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE tickets SET header_chat_id = ?, header_message_id = ? WHERE id = ?",
            (chat_id, message_id, ticket_id),
        )
        await db.commit()


async def increment_video_count(ticket_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE tickets SET video_count = video_count + 1 WHERE id = ?", (ticket_id,)
        )
        await db.commit()


async def set_ticket_status(ticket_id: int, status: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        await db.commit()


async def set_ticket_price(ticket_id: int, price: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("UPDATE tickets SET price = ? WHERE id = ?", (price, ticket_id))
        await db.commit()


# ---------- ticket_messages (routing) ----------

async def link_admin_message(ticket_id: int, admin_chat_id: int, admin_message_id: int) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO ticket_messages (ticket_id, admin_chat_id, admin_message_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (ticket_id, admin_chat_id, admin_message_id, _now()),
        )
        await db.commit()


async def find_ticket_by_admin_message(admin_chat_id: int, admin_message_id: int):
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT ticket_id FROM ticket_messages WHERE admin_chat_id = ? AND admin_message_id = ?",
            (admin_chat_id, admin_message_id),
        )
        row = await cur.fetchone()
        return row["ticket_id"] if row else None


# ---------- withdrawals (balansni yechib olish) ----------

async def create_withdrawal(user_tg_id: int, amount: int) -> int:
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            "INSERT INTO withdrawals (user_tg_id, amount, created_at) VALUES (?, ?, ?)",
            (user_tg_id, amount, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_withdrawal(withdrawal_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))
        return await cur.fetchone()


async def set_withdrawal_status(withdrawal_id: int, status: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE withdrawals SET status = ? WHERE id = ?", (status, withdrawal_id)
        )
        await db.commit()


# ---------- statistika ----------

@dataclass
class Stats:
    total_users: int
    total_appeals: int
    total_video_offers: int
    videos_bought: int
    videos_rejected: int
    videos_pending: int
    total_spent: int
    outstanding_balance: int


async def get_stats() -> Stats:
    async with aiosqlite.connect(_db_path) as db:
        async def _count(query: str, params=()) -> int:
            cur = await db.execute(query, params)
            row = await cur.fetchone()
            return row[0] if row else 0

        total_users = await _count("SELECT COUNT(*) FROM users")
        total_appeals = await _count("SELECT COUNT(*) FROM tickets WHERE kind = 'appeal'")
        total_video_offers = await _count("SELECT COUNT(*) FROM tickets WHERE kind = 'video'")
        videos_bought = await _count(
            "SELECT COUNT(*) FROM tickets WHERE kind = 'video' AND status = 'sotib_olindi'"
        )
        videos_rejected = await _count(
            "SELECT COUNT(*) FROM tickets WHERE kind = 'video' AND status = 'rad_etildi'"
        )
        videos_pending = await _count(
            "SELECT COUNT(*) FROM tickets WHERE kind = 'video' "
            "AND status NOT IN ('sotib_olindi', 'rad_etildi')"
        )
        total_spent = await _count(
            "SELECT COALESCE(SUM(price), 0) FROM tickets "
            "WHERE kind = 'video' AND status = 'sotib_olindi'"
        )
        outstanding_balance = await _count("SELECT COALESCE(SUM(balance), 0) FROM users")
        return Stats(
            total_users=total_users,
            total_appeals=total_appeals,
            total_video_offers=total_video_offers,
            videos_bought=videos_bought,
            videos_rejected=videos_rejected,
            videos_pending=videos_pending,
            total_spent=total_spent,
            outstanding_balance=outstanding_balance,
        )


async def list_bought_videos(limit: int = 20):
    """Sotib olingan videolarning oxirgi ro'yxati (narxi bilan)."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT t.id AS ticket_id, t.price AS price, t.created_at AS created_at,
                   u.full_name AS full_name, u.username AS username
            FROM tickets t
            LEFT JOIN users u ON u.tg_id = t.user_tg_id
            WHERE t.kind = 'video' AND t.status = 'sotib_olindi'
            ORDER BY t.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cur.fetchall()
