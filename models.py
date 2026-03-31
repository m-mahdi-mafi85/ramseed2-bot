import sqlite3
from settings import DB_NAME


def get_connection():
    return sqlite3.connect(DB_NAME)


# -------------------------
# USERS
# -------------------------
def create_user(tg_id, name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO users (tg_id, name, points, level)
    VALUES (?, ?, 0, 1)
    """, (tg_id, name))

    conn.commit()
    conn.close()


def get_user_by_tg(tg_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, tg_id, name, points, level FROM users WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "tg_id": row[1],
            "name": row[2],
            "points": row[3],
            "level": row[4]
        }

    return None


def add_points(user_id, points):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET points = points + ?
    WHERE id = ?
    """, (points, user_id))

    conn.commit()
    conn.close()


# -------------------------
# MISSIONS
# -------------------------
def add_mission(title, description):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO missions (title, description)
    VALUES (?, ?)
    """, (title, description))

    conn.commit()
    conn.close()


def get_mission_by_id(mission_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, title, description FROM missions WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2]
        }

    return None


# -------------------------
# SUBMISSIONS
# -------------------------
def save_submission(user_id, mission_id, type, content, file_id=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO submissions (user_id, mission_id, type, content, file_id, status)
    VALUES (?, ?, ?, ?, ?, 'pending')
    """, (user_id, mission_id, type, content, file_id))

    conn.commit()
    conn.close()


def get_pending_submissions():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT submissions.id, users.name, missions.title, submissions.type,
           submissions.content, submissions.file_id
    FROM submissions
    JOIN users ON submissions.user_id = users.id
    JOIN missions ON submissions.mission_id = missions.id
    WHERE submissions.status = 'pending'
    ORDER BY submissions.id ASC
    """)

    rows = cur.fetchall()
    conn.close()
    return rows


def update_submission_status(submission_id, status):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE submissions
    SET status = ?
    WHERE id = ?
    """, (status, submission_id))

    conn.commit()
    conn.close()


def get_submission_user(submission_id):
    """برای گرفتن user_id هنگام تأیید/رد"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM submissions WHERE id = ?", (submission_id,))
    row = cur.fetchone()
    conn.close()

    return row[0] if row else None
