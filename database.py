import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path("bot_data.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    conn = get_connection()
    c = conn.cursor()

    # Table for members who accept the rules
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            accepted_at TEXT
        )
    """)

    # Table for daily image posting limits (restart-safe)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_image_posts (
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            post_date TEXT NOT NULL,
            PRIMARY KEY (user_id, channel_id, post_date)
        )
    """)

    # ✅ NEW: Table for daily personal updates (logbook)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_personal_updates (
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, channel_id, log_date)
        )
    """)

    conn.commit()
    conn.close()


# ======================
# Members logic
# ======================

def add_member(user_id: int, username: str, accepted_at: str):
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO members (user_id, username, accepted_at)
        VALUES (?, ?, ?)
    """, (user_id, username, accepted_at))

    conn.commit()
    conn.close()


def remove_member(user_id: int):
    conn = get_connection()
    c = conn.cursor()

    c.execute("DELETE FROM members WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()


def get_all_members():
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM members")
    rows = c.fetchall()

    conn.close()
    return rows


# ======================
# Daily image logic
# ======================

def has_posted_today(user_id: int, channel_id: int) -> bool:
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT 1 FROM daily_image_posts
        WHERE user_id = ? AND channel_id = ? AND post_date = ?
        """,
        (user_id, channel_id, today)
    )

    result = c.fetchone()
    conn.close()

    return result is not None


def record_post(user_id: int, channel_id: int):
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        INSERT OR IGNORE INTO daily_image_posts
        (user_id, channel_id, post_date)
        VALUES (?, ?, ?)
        """,
        (user_id, channel_id, today)
    )

    conn.commit()
    conn.close()


def cleanup_old_daily_posts():
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        DELETE FROM daily_image_posts
        WHERE post_date < ?
        """,
        (today,)
    )

    conn.commit()
    conn.close()


# ======================
# Daily personal update (logbook) logic
# ======================

def has_personal_update_today(user_id: int, channel_id: int, log_date: str) -> bool:
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT 1 FROM daily_personal_updates
        WHERE user_id = ? AND channel_id = ? AND log_date = ?
        """,
        (user_id, channel_id, log_date)
    )

    result = c.fetchone()
    conn.close()
    return result is not None


def insert_personal_update(
    user_id: int,
    channel_id: int,
    message_id: int,
    log_date: str,
    content: str,
    created_at: str
) -> bool:
    """
    Returns True if inserted, False if already exists (same user/channel/date).
    """
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        INSERT OR IGNORE INTO daily_personal_updates
        (user_id, channel_id, message_id, log_date, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, channel_id, message_id, log_date, content, created_at)
    )

    conn.commit()
    inserted = (c.rowcount == 1)
    conn.close()
    return inserted


def get_personal_updates(user_id: int, limit: int = 10):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT log_date, content, created_at
        FROM daily_personal_updates
        WHERE user_id = ?
        ORDER BY log_date DESC
        LIMIT ?
        """,
        (user_id, limit)
    )

    rows = c.fetchall()
    conn.close()
    return rows


def get_personal_update_by_date(user_id: int, log_date: str):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        SELECT log_date, content, created_at
        FROM daily_personal_updates
        WHERE user_id = ? AND log_date = ?
        """,
        (user_id, log_date)
    )

    row = c.fetchone()
    conn.close()
    return row


def get_user_updates_for_mod_view(user_id: int, limit: int = 10):
    """
    Same as get_personal_updates, but kept separate for clarity / future expansion.
    """
    return get_personal_updates(user_id, limit=limit)
