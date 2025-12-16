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
