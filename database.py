import sqlite3
from pathlib import Path

DB_PATH = Path("bot_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Optional: returns dict-like rows
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

    conn.commit()
    conn.close()


# Insert a member when they accept rules
def add_member(user_id: int, username: str, accepted_at: str):
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO members (user_id, username, accepted_at)
        VALUES (?, ?, ?)
    """, (user_id, username, accepted_at))

    conn.commit()
    conn.close()


# Remove a member when they unaccept the rules
def remove_member(user_id: int):
    conn = get_connection()
    c = conn.cursor()

    c.execute("DELETE FROM members WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()


# Get all members
def get_all_members():
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM members")
    rows = c.fetchall()

    conn.close()
    return rows
