# settings.py
# ----------------------------------------
# تنظیمات اصلی پروژه باشگاه نویسندگان فردا
# ----------------------------------------

import os

# توکن ربات تلگرام
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8761278126:AAGQIVOZxootZuJnbbzxQjnzXZduL_SFe_0")

# کلید API برای ChatGPT
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PUT-YOUR-API-KEY-HERE")

# مسیر دیتابیس
DB_NAME = "club.db"

# نقش‌های باشگاه
ROLES = ["خبرنگار", "پژوهشگر", "رسانه"]

# بازه‌های زمانی فعالیت
TIME_SLOTS = ["صبح", "عصر", "شب"]

# ادمین‌ها
ADMINS = [
    8553725254,   # آیدی مدیر ۱
    # آیدی مدیرهای بعدی را اینجا اضافه کن
]

# تنظیمات هوش مصنوعی
AI_MODEL = "gpt-5.2"
AI_SYSTEM_PROMPT = """
You are the AI engine for the Persian Writers Club.
Your job is to generate high-quality missions, analyze texts, and assist admin moderation.
"""
# database.py
# ----------------------------------------
# مدیریت پایگاه داده SQLite - نسخه حرفه‌ای
# ----------------------------------------

import sqlite3
import logging
from settings import DB_NAME

# تنظیمات لاگ برای دیباگ راحت‌تر
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection():
    """برقراری اتصال به دیتابیس"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # برای دسترسی به دیتا با نام ستون
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_db():
    """ایجاد جداول در صورت عدم وجود"""
    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor()
    
    # ۱. جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT,       -- خبرنگار، پژوهشگر، رسانه
            shift TEXT,      -- صبح، عصر، شب
            points INTEGER DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ۲. جدول فعالیت‌ها (مأموریت‌های تعریف شده توسط سیستم یا ادمین)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            role_required TEXT, -- نقشی که می‌تواند این مأموریت را انجام دهد
            points_reward INTEGER DEFAULT 10,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ۳. جدول ثبت انجام مأموریت (مدارک ارسالی کاربران)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mission_id INTEGER,
            content_type TEXT,  -- text, photo, document, link
            content_data TEXT,  -- متن یا آیدی فایل تلگرام
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            admin_note TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (mission_id) REFERENCES missions (id)
        )
    ''')

    # ۴. جدول پیشنهادات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

if __name__ == "__main__":
    # اگر این فایل را مستقیم اجرا کنی، دیتابیس ساخته می‌شود
    init_db()
# models.py
# -----------------------------------------------------------
# توابع CRUD برای کار با جداول دیتابیس پروژه باشگاه نویسندگان
# -----------------------------------------------------------

import sqlite3
from database import get_connection

# =========================
#  کاربران (Users)
# =========================

def add_user(user_id: int, username: str, full_name: str, role: str, shift: str, is_admin: bool = False):
    """افزودن کاربر جدید در صورت عدم وجود."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing = cur.fetchone()

    if existing:
        conn.close()
        return False  # کاربر از قبل وجود دارد

    cur.execute("""
        INSERT INTO users (user_id, username, full_name, role, shift, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, full_name, role, shift, int(is_admin)))

    conn.commit()
    conn.close()
    return True


def get_user(user_id: int):
    """برگرداندن اطلاعات کاربر بر اساس user_id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_points(user_id: int, delta: int):
    """افزودن یا کسر امتیاز از کاربر."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (delta, user_id))
    conn.commit()
    conn.close()


def get_all_users(active_only: bool = True):
    """نمایش تمام کاربران (اختیاری فقط فعال‌ها)."""
    conn = get_connection()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM users WHERE is_active = 1")
    else:
        cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# =========================
#  مأموریت‌ها (Missions)
# =========================

def add_mission(title: str, description: str, role_required: str, points_reward: int = 10):
    """افزودن مأموریت جدید."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO missions (title, description, role_required, points_reward)
        VALUES (?, ?, ?, ?)
    """, (title, description, role_required, points_reward))
    conn.commit()
    conn.close()


def get_active_missions(role_required: str = None):
    """برگرداندن مأموریت‌های فعال (اختیاری فیلتر بر اساس نقش)."""
    conn = get_connection()
    cur = conn.cursor()
    if role_required:
        cur.execute("SELECT * FROM missions WHERE is_active = 1 AND role_required = ?", (role_required,))
    else:
        cur.execute("SELECT * FROM missions WHERE is_active = 1")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mission_by_id(mid: int):
    """دریافت جزئیات مأموریت با id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM missions WHERE id = ?", (mid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# =========================
#  ثبت مأموریت (Submissions)
# =========================

def add_submission(user_id: int, mission_id: int, content_type: str, content_data: str):
    """ثبت ارسال مأموریت از سوی کاربر."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO submissions (user_id, mission_id, content_type, content_data)
        VALUES (?, ?, ?, ?)
    """, (user_id, mission_id, content_type, content_data))
    conn.commit()
    conn.close()


def get_pending_submissions():
    """برگرداندن لیست مدارک در انتظار بررسی."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, u.full_name, u.username, m.title 
        FROM submissions s
        JOIN users u ON s.user_id = u.user_id
        JOIN missions m ON s.mission_id = m.id
        WHERE s.status = 'pending'
    """)
    rows = cur.fetchall()
    conn.close()
    returndict(r) for r in rows]


def update_submission_status(submission_id: int, status: str, admin_note: str = None):
    """تغییر وضعیت مدرک (approved / rejected)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE submissions
        SET status = ?, admin_note = ?
        WHERE id = ?
    """, (status, admin_note, submission_id))
    conn.commit()
    conn.close()


# =========================
#  پیشنهادات (Suggestions)
# =========================

def add_suggestion(user_id: int, text: str):
    """ثبت پیشنهاد کاربر."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO suggestions (user_id, text) VALUES (?, ?)", (user_id, text))
    conn.commit()
    conn.close()


def get_all_suggestions(unread_only: bool = False):
    """نمایش پیشنهادات (اختیاری فقط خوانده‌نشده‌ها)."""
    conn = get_connection()
    cur = conn.cursor()
    if unread_only:
        cur.execute("""
            SELECT s.*, u.full_name, u.username
            FROM suggestions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.is_read = 0
        """)
    else:
        cur.execute("""
            SELECT s.*, u.full_name, u.username
            FROM suggestions s
            JOIN users u ON s.user_id = u.user_id
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_suggestion_read(suggestion_id: int):
    """علامت‌گذاری پیشنهاد به عنوان خوانده‌شده."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE suggestions SET is_read = 1 WHERE id = ?", (suggestion_id,))
    conn.commit()
    conn.close()
# utils.py
# -----------------------------------------------------------
# ابزارهای کمکی عمومی برای پروژه باشگاه نویسندگان
# -----------------------------------------------------------

import datetime
import random
import textwrap
import logging
import re

logger = logging.getLogger(__name__)

# -------------------------------
# 🕒 زمان و تاریخ
# -------------------------------

def get_now_str() -> str:
    """تاریخ و زمان فعلی به صورت استرینگ خوانا (میلادی)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def human_friendly_time(ts: str) -> str:
    """تبدیل تاریخ دیتابیس (YYYY-MM-DD HH:MM:SS) به فرم خوانا."""
    try:
        t = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return t.strftime("%d %B %Y - %H:%M")
    except Exception:
        return ts


# -------------------------------
# 🧮 امتیازدهی و محاسبه سطح
# -------------------------------

def calculate_level(points: int) -> int:
    """
    محاسبه سطح کاربر بر اساس امتیاز.
    فرمول: هر 100 امتیاز = 1 سطح.
    """
    return (points // 100) + 1


def get_progress_bar(points: int) -> str:
    """
    نوار پیشرفت سطح کاربر با ایموجی.
    """
    level = calculate_level(points)
    within_level = points % 100
    bars = int(within_level / 10)
    return f"سطح {level} 🎯\n" + "🟩" * bars + "⬜" * (10 - bars)


# -------------------------------
# 🔤 متون و پیام‌ها
# -------------------------------

def wrap_text(text: str, width: int = 4000) -> list[str]:
    """
    تقسیم متن بلند به قطعات قابل ارسال در تلگرام.
    (تعداد کاراکترها در پیام تلگرام محدود است ~4096)
    """
    chunks = textwrap.wrap(text, width)
    return chunks or ["(متن خالی)"]


def clean_text(text: str) -> str:
    """
    حذف فاصله‌های متوالی، newlineهای اضافی و space در ابتدا/انتها.
    """
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def random_emoji() -> str:
    """برگرداندن یک ایموجی تشویقی تصادفی برای پیام‌ها."""
    emojis = ["✨", "🔥", "✍️", "💫", "📖", "🌱", "🪶", "💎"]
    return random.choice(emojis)


# -------------------------------
# 🎲 انتخاب مأموریت و متون تصادفی
# -------------------------------

def pick_random_mission(missions: list[dict]) -> dict | None:
    """انتخاب تصادفی یک مأموریت از لیست."""
    if not missions:
        return None
    return random.choice(missions)


def format_mission_text(mission: dict) -> str:
    """تبدیل دیتای مأموریت به متن زیبا برای نمایش کاربر."""
    text = f"""
🪶 <b>{mission['title']}</b>

{mission.get('description', 'بدون توضیح')}

🎯 امتیاز: {mission.get('points_reward', 0)}
🧩 مناسب برای نقش: {mission.get('role_required', 'همه')}
"""
    return text.strip()


# -------------------------------
# 🧠 هوش مصنوعی (یاری‌دهنده عمومی)
# -------------------------------

def ai_safe_prompt(prompt: str) -> str:
    """تمیزسازی متن قبل از ارسال به مدل هوش مصنوعی."""
    cleaned = clean_text(prompt)
    if len(cleaned) > 4000:
        cleaned = cleaned[:4000] + "..."
    return cleaned


# -------------------------------
# 🧹 مدیریت استثناها و گزارش‌ها
# -------------------------------

def safe_exec(func, *args, **kwargs):
    """اجرای امن توابع با مدیریت خطا و چاپ در لاگ."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in {func.__name__}: {e}")
        return None
# ai_engine.py
# -----------------------------------------------------------
# موتور هوش مصنوعی برای کمک به ادمین
# -----------------------------------------------------------

import logging
from utils import ai_safe_prompt
from settings import OPENAI_API_KEY

# در آینده مدل واقعی اضافه می‌شود
# فعلاً ساختار آماده است و از استاب استفاده می‌کند

logger = logging.getLogger(__name__)

# -------------------------------
# توابع پایه
# -------------------------------

def call_ai(prompt: str) -> str:
    """
    تابع عمومی برای ارسال پرس‌وجو به هوش مصنوعی.
    بعداً با OpenAI API پر می‌شود.
    """
    safe = ai_safe_prompt(prompt)  # جهت جلوگیری از ورودی خراب

    # استاب موقت برای توسعه:
    simulated = f"[AI پاسخ شبیه‌سازی‌شده به درخواست:\n{safe}\n]"
    logger.info(f"AI simulated response for prompt: {safe[:120]}")
    return simulated


# -------------------------------
# تولید مأموریت جدید
# -------------------------------

def ai_generate_mission(role: str, shift: str) -> dict:
    """
    تولید یک مأموریت کامل برای ادمین.
    role مثل: خبرنگار، پژوهشگر، رسانه
    shift مثل: صبح، عصر، شب
    """
    prompt = f"""
    یک مأموریت جذاب برای نقش {role} در بازه زمانی {shift} پیشنهاد بده.
    خروجی باید شامل: عنوان، توضیح، امتیاز پیشنهادی.
    """

    answer = call_ai(prompt)

    # در استفاده واقعی JSON می‌دهیم؛ فعلاً تبدیل ساده:
    return {
        "title": f"مأموریت پیشنهادی برای {role}",
        "description": answer,
        "points": 20
    }


# -------------------------------
# تحلیل پیشنهادات کاربران
# -------------------------------

def ai_analyze_suggestion(text: str) -> str:
    """
    خلاصه و تحلیل یک پیشنهاد کاربر.
    """
    prompt = f"این پیشنهاد را تحلیل کن و خلاصه‌ای مدیریتی بده:\n{text}"
    return call_ai(prompt)


# -------------------------------
# تحلیل کیفیت متن ارسالی کاربران
# -------------------------------

def ai_text_quality(text: str) -> str:
    """
    بررسی متن کاربر (اختصاصی برای خبرنگار و پژوهشگر).
    """
    prompt = f"""
    کیفیت متن زیر را ارزیابی کن:
    معیارها: انسجام، نگارش، جذابیت، بیان.
    متن:
    {text}
    """
    return call_ai(prompt)
# keyboards.py
# -----------------------------------------------------------
# کیبوردهای تلگرام برای کاربر و ادمین
# -----------------------------------------------------------

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# -------------------------------
# کیبورد ثبت‌نام
# -------------------------------

ROLES = ["خبرنگار", "پژوهشگر", "رسانه"]
SHIFTS = ["صبح", "عصر", "شب"]

def role_keyboard():
    return ReplyKeyboardMarkup(
        [[r] for r in ROLES],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def shift_keyboard():
    return ReplyKeyboardMarkup(
        [[s] for s in SHIFTS],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# -------------------------------
# کیبورد اصلی کاربر
# -------------------------------

def user_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📋 دریافت مأموریت"],
            ["📝 ارسال مدرک"],
            ["📊 داشبورد من"],
            ["💡 پیشنهاد"],
        ],
        resize_keyboard=True
    )

# -------------------------------
# کیبورد مأموریت‌ها (اینلاین)
# -------------------------------

def mission_inline_keyboard(mission_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✔️ قبول مأموریت", callback_data=f"accept_{mission_id}")
        ]
    ])

# -------------------------------
# کیبورد بررسی مدرک توسط ادمین
# -------------------------------

def admin_review_keyboard(submission_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 تأیید", callback_data=f"approve_{submission_id}"),
            InlineKeyboardButton("👎 رد", callback_data=f"reject_{submission_id}")
        ]
    ])

# -------------------------------
# کیبورد پنل مدیریت
# -------------------------------

def admin_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ افزودن مأموریت"],
            ["📬 بررسی مدارک"],
            ["📢 ارسال پیام همگانی"],
            ["📊 گزارش کاربران"],
            ["💡 پیشنهادات کاربران"],
            ["🤖 ابزار هوش مصنوعی"],
        ],
        resize_keyboard=True
    )
# user_handlers.py
# -----------------------------------------------------------
# هندلرهای پیام و عملیات سمت کاربری باشگاه نویسندگان
# -----------------------------------------------------------

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from models import add_user, get_user, update_user_points
from keyboards import role_keyboard, shift_keyboard, user_main_keyboard
from utils import wrap_text, random_emoji, get_progress_bar, calculate_level
from mission_handlers import get_user_missions, handle_submit_proof
from models import add_suggestion

# وضعیت‌های گفتگو
ROLE_SELECT, SHIFT_SELECT = range(2)

# -------------------------------
# هندلر شروع / ثبت‌نام
# -------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id
    username = user.username or "-"
    full_name = user.full_name or "-"

    info = get_user(telegram_id)
    if info:
        await update.message.reply_text(
            f"سلام {full_name} 👋\nبه باشگاه نویسندگان خوش آمدی!\nمنوی اصلی در اختیار تو است.",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "برای ادامه لطفاً نقش خود را انتخاب کن:",
        reply_markup=role_keyboard()
    )
    return ROLE_SELECT

async def role_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text
    if role not in ["خبرنگار", "پژوهشگر", "رسانه"]:
        await update.message.reply_text("نقش انتخابی معتبر نیست. لطفاً مجدد انتخاب کن.", reply_markup=role_keyboard())
        return ROLE_SELECT

    context.user_data["role"] = role
    await update.message.reply_text("شیفت فعالیت خود را انتخاب کن:", reply_markup=shift_keyboard())
    return SHIFT_SELECT

async def shift_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shift = update.message.text
    if shift not in ["صبح", "عصر", "شب"]:
        await update.message.reply_text("شیفت انتخابی معتبر نیست. لطفاً مجدد انتخاب کن.", reply_markup=shift_keyboard())
        return SHIFT_SELECT

    role = context.user_data.get("role", "خبرنگار")
    user = update.effective_user
    telegram_id = user.id
    username = user.username or "-"
    full_name = user.full_name or "-"

    add_user(telegram_id, username, full_name, role, shift)
    await update.message.reply_text(
        f"ثبت‌نام با موفقیت انجام شد ✨\nخوش آمدی {random_emoji()}",
        reply_markup=user_main_keyboard()
    )
    return ConversationHandler.END

# -------------------------------
# هندلر داشبورد کاربر
# -------------------------------

async def dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    info = get_user(user.id)
    if not info:
        await update.message.reply_text("ابتدا ثبت‌نام کن.", reply_markup=user_main_keyboard())
        return

    points = info.get("points", 0)
    level = calculate_level(points)
    progress = get_progress_bar(points)
    missions = get_user_missions(user.id)  # مأموریت‌های کاربر

    text = f"""📊 داشبورد تو:
نام: {info['full_name']}
نقش: {info['role']}
شیفت: {info['shift']}

امتیاز: {points}
سطح جاری: {level}
{progress}

تعداد مأموریت‌های فعال: {len(missions)}
"""
    for chunk in wrap_text(text):
        await update.message.reply_text(chunk, reply_markup=user_main_keyboard())

# -------------------------------
# هندلر ارسال پیشنهاد کاربر
# -------------------------------

async def suggestion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("پیشنهاد یا انتقاد خود را بنویسید و ارسال کنید.")
    return "SUGGESTION_TEXT"

async def suggestion_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    add_suggestion(user.id, text)
    await update.message.reply_text("پیشنهاد ثبت شد! ممنون از مشارکتت 💡", reply_markup=user_main_keyboard())
    return ConversationHandler.END

# -------------------------------
# هندلر ارسال مدرک
# -------------------------------

async def submit_proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # انتقال به هندلر تخصصی مأموریت‌ها
    await handle_submit_proof(update, context)

# -------------------------------
# هندلر دریافت مأموریت
# -------------------------------

async def get_mission_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_message(chat_id=user.id, text="درخواست مأموریت جدید به مأموریت‌باز ارسال شد.")
    # مأموریت‌باز در mission_handlers اجرا می‌شود

# -------------------------------
# هندلر خروج
# -------------------------------

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=user_main_keyboard())
    return ConversationHandler.END
# mission_handlers.py
# -----------------------------------------------------------
# مدیریت مأموریت‌ها و هندلرهای مأموریت برای کاربران و ادمین
# -----------------------------------------------------------

from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

from models import get_active_missions, get_mission_by_id, add_submission
from keyboards import mission_inline_keyboard
from utils import format_mission_text, wrap_text, random_emoji

# -------------------------------
# دریافت مأموریت برای کاربر
# -------------------------------

def get_user_missions(user_id: int):
    # این تابع لیست مأموریت‌های مناسب کاربر را برمی‌گرداند
    # (در نسخه پایه: همه مأموریت‌های فعال، در نسخه حرفه‌ای: بر اساس نقش و شیفت)
    # فرضاً از مدل user و role/shift می‌گیریم
    # در نسخه بعدی بهینه خواهد شد
    return get_active_missions()

async def send_mission_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    missions = get_user_missions(user.id)
    if not missions:
        await context.bot.send_message(chat_id=user.id, text="مأموریت فعال یافت نشد! لطفاً بعداً امتحان کن.")
        return
    mission = missions[0]  # فعلاً اولین مأموریت (در آینده تصادفی یا تخصیص‌شده)
    text = format_mission_text(mission)
    for chunk in wrap_text(text):
        await context.bot.send_message(chat_id=user.id, text=chunk, parse_mode="HTML")
    await context.bot.send_message(
        chat_id=user.id,
        text="برای دریافت و ارسال مدرک، دکمه زیر را بزن:",
        reply_markup=mission_inline_keyboard(mission["id"])
    )

# -------------------------------
# ارسال مدرک مأموریت
# -------------------------------

async def handle_submit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "مدرک انجام مأموریت را ارسال کن (متن، عکس، فایل یا لینک)."
    )
    context.user_data["pending_submission"] = True
    return "AWAIT_PROOF"

async def proof_receive_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    content_type = "text"
    content_data = ""
    mission_id = context.user_data.get("current_mission_id", None)
    if update.message.text:
        content_type = "text"
        content_data = update.message.text
    elif update.message.photo:
        content_type = "photo"
        photo = update.message.photo[-1]  # بهترین کیفیت
        file_id = photo.file_id
        content_data = file_id
    elif update.message.document:
        content_type = "file"
        file_id = update.message.document.file_id
        content_data = file_id
    elif update.message.entities:  # احتمالا لینک یا mention
        content_type = "link"
        content_data = update.message.text

    if mission_id is None:
        await update.message.reply_text("مأموریت انتخاب نشده است.")
        return

    add_submission(user.id, mission_id, content_type, content_data)
    await update.message.reply_text(
        f"مدرک ثبت شد و در صف بررسی است {random_emoji()}"
    )
    context.user_data["pending_submission"] = False
    return ConversationHandler.END

# -------------------------------
# هندلرهای مدیریتی و توسعه‌پذیری
# (در نسخه کامل پنل ادمین کامل‌تر می‌شود)
# admin_handlers.py
# -----------------------------------------------------------
# پنل مدیریت ربات باشگاه نویسندگان
# -----------------------------------------------------------

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from settings import ADMIN_IDS
from keyboards import admin_main_keyboard, admin_review_keyboard
from models import (
    add_mission,
    get_pending_submissions,
    approve_submission,
    reject_submission,
    get_all_users,
    get_suggestions
)

from ai_engine import ai_generate_mission, ai_analyze_suggestion

# وضعیت‌ها
MISSION_TITLE, MISSION_DESC, MISSION_POINTS = range(3)


# -------------------------------
# بررسی دسترسی ادمین
# -------------------------------

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# -------------------------------
# ورود به پنل مدیریت
# -------------------------------

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("شما دسترسی ادمین ندارید.")
        return

    await update.message.reply_text(
        "به پنل مدیریت خوش آمدید:",
        reply_markup=admin_main_keyboard()
    )


# -------------------------------
# افزودن مأموریت
# -------------------------------

async def add_mission_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text("عنوان مأموریت را ارسال کنید:")
    return MISSION_TITLE


async def mission_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mission_title"] = update.message.text
    await update.message.reply_text("توضیح مأموریت:")
    return MISSION_DESC


async def mission_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mission_desc"] = update.message.text
    await update.message.reply_text("امتیاز مأموریت:")
    return MISSION_POINTS


async def mission_points(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        points = int(update.message.text)
    except:
        await update.message.reply_text("امتیاز باید عدد باشد.")
        return MISSION_POINTS

    title = context.user_data["mission_title"]
    desc = context.user_data["mission_desc"]

    add_mission(title, desc, points)

    await update.message.reply_text(
        "✅ مأموریت ثبت شد.",
        reply_markup=admin_main_keyboard()
    )

    return ConversationHandler.END


# -------------------------------
# بررسی مدارک
# -------------------------------

async def review_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    subs = get_pending_submissions()

    if not subs:
        await update.message.reply_text("مدرک جدیدی وجود ندارد.")
        return

    for s in subs:

        text = f"""
مدرک جدید

کاربر: {s['user_id']}
مأموریت: {s['mission_id']}
نوع: {s['content_type']}
"""

        await update.message.reply_text(
            text,
            reply_markup=admin_review_keyboard(s["id"])
        )


# -------------------------------
# تایید مدرک
# -------------------------------

async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    sub_id = int(query.data.split("_")[1])

    approve_submission(sub_id)

    await query.edit_message_text("✅ مدرک تایید شد")


# -------------------------------
# رد مدرک
# -------------------------------

async def reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    sub_id = int(query.data.split("_")[1])

    reject_submission(sub_id)

    await query.edit_message_text("❌ مدرک رد شد")


# -------------------------------
# مشاهده پیشنهادات کاربران
# -------------------------------

async def show_suggestions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    suggestions = get_suggestions()

    if not suggestions:
        await update.message.reply_text("پیشنهادی ثبت نشده.")
        return

    for s in suggestions:

        analysis = ai_analyze_suggestion(s["text"])

        msg = f"""
پیشنهاد کاربر:

{s['text']}

تحلیل AI:

{analysis}
"""

        await update.message.reply_text(msg)


# -------------------------------
# پیام همگانی
# -------------------------------

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("متن پیام هگانی را ارسال کنید:")
    return "BROADCAST"


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    users = get_all_users()

    sent = 0

    for u in users:

        try:
            await context.bot.send_message(u["telegram_id"], text)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"پیام برای {sent} کاربر ارسال شد.")
    return ConversationHandler.END


# -------------------------------
# ابزار AI
# -------------------------------

async def ai_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):

    mission = ai_generate_mission("خبرنگار", "صبح")

    text = f"""
پیشنهاد AI برای مأموریت:

عنوان:
{mission['title']}

توضیح:
{mission['description']}

امتیاز پیشنهادی:
{mission['points']}
"""

    await update.message.reply_text(text)
# main.py
# -----------------------------------------------------------
# هسته اصلی اجرای ربات
# -----------------------------------------------------------

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from settings import BOT_TOKEN

# user
from user_handlers import (
    start_handler,
    role_select_handler,
    shift_select_handler,
    dashboard_handler,
    suggestion_handler,
    suggestion_text_handler
)

# mission
from mission_handlers import (
    proof_receive_handler
)

# admin
from admin_handlers import (
    admin_panel,
    add_mission_start,
    mission_title,
    mission_desc,
    mission_points,
    review_submissions,
    approve_callback,
    reject_callback,
    show_suggestions,
    broadcast_start,
    broadcast_send,
    ai_tools
)

# -------------------------------
# وضعیت‌ها
# -------------------------------

ROLE_SELECT = 0
SHIFT_SELECT = 1


# -------------------------------
# اجرای برنامه
# -------------------------------

def main():

    app = Application.builder().token(BOT_TOKEN).build()

    # -------------------------------
    # ثبت نام
    # -------------------------------

    register_conv = ConversationHandler(

        entry_points=[CommandHandler("start", start_handler)],

        states={

            ROLE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, role_select_handler)
            ],

            SHIFT_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, shift_select_handler)
            ],
        },

        fallbacks=[]
    )

    app.add_handler(register_conv)

    # -------------------------------
    # داشبورد
    # -------------------------------

    app.add_handler(MessageHandler(filters.Regex("داشبورد"), dashboard_handler))


    # -------------------------------
    # پیشنهاد
    # -------------------------------

    suggestion_conv = ConversationHandler(

        entry_points=[MessageHandler(filters.Regex("پیشنهاد"), suggestion_handler)],

        states={
            "SUGGESTION_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, suggestion_text_handler)
            ]
        },

        fallbacks=[]
    )

    app.add_handler(suggestion_conv)


    # -------------------------------
    # دریافت مدرک
    # -------------------------------

    app.add_handler(MessageHandler(filters.ALL, proof_receive_handler))


    # -------------------------------
    # پنل مدیریت
    # -------------------------------

    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(MessageHandler(filters.Regex("بررسی مدارک"), review_submissions))

    app.add_handler(MessageHandler(filters.Regex("پیشنهادات کاربران"), show_suggestions))

    app.add_handler(MessageHandler(filters.Regex("ابزار هوش مصنوعی"), ai_tools))


    # -------------------------------
    # افزودن مأموریت
    # -------------------------------

    mission_conv = ConversationHandler(

        entry_points=[MessageHandler(filters.Regex("افزودن مأموریت"), add_mission_start)],

        states={

            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, mission_title)],

            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, mission_desc)],

            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, mission_points)],

        },

        fallbacks=[]
    )

    app.add_handler(mission_conv)


    # -------------------------------
    # broadcast
    # -------------------------------

    broadcast_conv = ConversationHandler(

        entry_points=[MessageHandler(filters.Regex("ارسال پیام همگانی"), broadcast_start)],

        states={
            "BROADCAST": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)
            ]
        },

        fallbacks=[]
    )

    app.add_handler(broadcast_conv)


    # -------------------------------
    # callback
    # -------------------------------

    app.add_handler(CallbackQueryHandler(approve_callback, pattern="approve_"))
    app.add_handler(CallbackQueryHandler(reject_callback, pattern="reject_"))


    # -------------------------------
    # اجرای ربات
    # -------------------------------

    print("✅ Bot Started")

    app.run_polling()


if __name__ == "__main__":
    main()
# database.py
# -----------------------------------------------------------
# مدیریت اتصال به دیتابیس SQLite
# -----------------------------------------------------------

import sqlite3

DB_NAME = "club.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_connection()
    cur = conn.cursor()

    # کاربران
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        role TEXT,
        shift TEXT,
        points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # مأموریت‌ها
    cur.execute("""
    CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        points INTEGER,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # مدارک
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mission_id INTEGER,
        content_type TEXT,
        content_data TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # پیشنهادات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
# models.py
# -----------------------------------------------------------
# عملیات دیتابیس
# -----------------------------------------------------------

from database import get_connection


# -------------------------
# USERS
# -------------------------

def add_user(telegram_id, username, full_name, role, shift):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO users (telegram_id, username, full_name, role, shift)
    VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, username, full_name, role, shift))

    conn.commit()
    conn.close()


def get_user(telegram_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cur.fetchone()

    conn.close()

    return dict(user) if user else None


def update_user_points(user_id, points):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET points = points + ?
    WHERE telegram_id = ?
    """, (points, user_id))

    conn.commit()
    conn.close()


def get_all_users():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()

    conn.close()

    return [dict(r) for r in rows]


# -------------------------
# MISSIONS
# -------------------------

def add_mission(title, description, points):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO missions (title, description, points)
    VALUES (?, ?, ?)
    """, (title, description, points))

    conn.commit()
    conn.close()


def get_active_missions():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM missions WHERE active = 1")

    rows = cur.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def get_mission_by_id(mid):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM missions WHERE id = ?", (mid,))

    row = cur.fetchone()

    conn.close()

    return dict(row) if row else None


# -------------------------
# SUBMISSIONS
# -------------------------

def add_submission(user_id, mission_id, content_type, content_data):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO submissions
    (user_id, mission_id, content_type, content_data)
    VALUES (?, ?, ?, ?)
    """, (user_id, mission_id, content_type, content_data))

    conn.commit()
    conn.close()


def get_pending_submissions():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM submissions
    WHERE status = 'pending'
    """)

    rows = cur.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def approve_submission(sub_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE submissions
    SET status = 'approved'
    WHERE id = ?
    """, (sub_id,))

    conn.commit()
    conn.close()


def reject_submission(sub_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE submissions
    SET status = 'rejected'
    WHERE id = ?
    """, (sub_id,))

    conn.commit()
    conn.close()


# -------------------------
# SUGGESTIONS
# -------------------------

def add_suggestion(user_id, text):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO suggestions (user_id, text)
    VALUES (?, ?)
    """, (user_id, text))

    conn.commit()
    conn.close()


def get_suggestions():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM suggestions")

    rows = cur.fetchall()

    conn.close()

    return [dict(r) for r in rows]
# utils.py
# -----------------------------------------------------------
# توابع کمکی
# -----------------------------------------------------------

import random


# ایموجی تصادفی
def random_emoji():
    emojis = ["✨", "🔥", "🚀", "🎯", "✅", "💡"]
    return random.choice(emojis)


# تقسیم متن بلند
def wrap_text(text, size=3500):

    parts = []

    for i in range(0, len(text), size):
        parts.append(text[i:i+size])

    return parts


# نوار پیشرفت
def get_progress_bar(points):

    level = points // 100
    progress = points % 100

    filled = int(progress / 10)

    bar = "█" * filled + "░" * (10 - filled)

    return f"[{bar}] {progress}%"



# محاسبه سطح
def calculate_level(points):

    return (points // 100) + 1


# قالب متن مأموریت
def format_mission_text(mission):

    text = f"""
🎯 مأموریت جدید

عنوان:
{mission['title']}

شرح:
{mission['description']}

امتیاز:
{mission['points']}
"""

    return text
