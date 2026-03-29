# -*- coding: utf-8 -*-
import logging
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ----------------

TOKEN = "8747795870:AAEpTEuNHLjmjCLJam_Gng-cDT6s_hswpgI"

# آیدی عددی ادمین‌ها (مثلا [123456789, 987654321])
ADMIN_IDS = [8553725254]


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------------- DB ----------------

DB_PATH = "bot.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # کاربران
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            national_id TEXT,
            referral_code TEXT,
            role TEXT,
            time_slot TEXT,
            field TEXT,
            score INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )

    # فعالیت‌ها (فهرست فعالیت‌ها بر اساس PDF)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,            -- تعامل / تبیین / روایت / راهبری / پژوهش / صدقه / ...
            time_slot TEXT,           -- 2-5 / 10-20 / 30-120 / custom
            field TEXT,               -- virtual / field
            mission_type TEXT,        -- daily / weekly / yearly / self_report / suggestion
            importance INTEGER DEFAULT 1,  -- برای تعداد نوتیف و وزن
            points INTEGER DEFAULT 5, -- امتیاز فعالیت
            requires_proof INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_by_admin INTEGER DEFAULT 1
        )
        """
    )

    # مأموریت‌های تخصیص‌یافته / انجام‌شده
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            activity_id INTEGER,
            mission_type TEXT,        -- daily / weekly / yearly / self_report
            status TEXT,              -- pending / approved / rejected
            proof TEXT,               -- file_id عکس یا متن
            importance INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(activity_id) REFERENCES activities(id)
        )
        """
    )

    # پیشنهاد فعالیت جدید توسط کاربران
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'new',   -- new / accepted / rejected
            created_at TEXT,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


# ---------------- SEED ابتدایی برخی فعالیت‌ها (بر اساس PDF) ----------------

def seed_activities():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM activities")
    if cur.fetchone()["c"] > 0:
        conn.close()
        return  # قبلا پر شده

    base_activities = [
        # 2-5 دقیقه - فضای مجازی - تعامل
        ("لایک پست", "تعامل", "2-5", "virtual", "daily", 1, 2),
        ("اشتراک / فوروارد محتوا", "تعامل", "2-5", "virtual", "daily", 2, 3),
        ("کامنت کوتاه حمایتی", "تعامل", "2-5", "virtual", "daily", 2, 4),
        ("ریپورت محتوای مجرمانه با مستندات", "تعامل", "2-5", "virtual", "daily", 3, 6),

        # 2-5 دقیقه - فضای مجازی - تبیین/روایت
        ("توضیح کوتاه در کامنت برای شکستن جو", "تبیین", "2-5", "virtual", "daily", 3, 5),
        ("ثبت یک خط روایت روز", "روایت", "2-5", "virtual", "daily", 2, 4),

        # 2-5 دقیقه - عرصه میدانی
        ("سلام کردن هر روزه به اهالی محل", "مسئولیت اجتماعی", "2-5", "field", "daily", 1, 3),
        ("انتقال شایعات میدانی به پلتفرم", "روایت", "2-5", "field", "daily", 2, 4),

        # 10-20 دقیقه - فضای مجازی
        ("تولید یک پست ساده (متن + عکس)", "تولید محتوا", "10-20", "virtual", "weekly", 3, 10),
        ("خلاصه‌نویسی 3 صفحه از یک کتاب", "پژوهش", "10-20", "virtual", "weekly", 3, 10),

        # 30-120 دقیقه - فضای مجازی
        ("طراحی یک عملیات/کمپین کوچک", "راهبری", "30-120", "virtual", "weekly", 4, 20),

        # 30-120 دقیقه - میدانی
        ("تبیین در جمع کوچک (مثلا مسجد/خانواده)", "تبیین", "30-120", "field", "weekly", 4, 20),
    ]

    for title, category, ts, field, mtype, imp, pts in base_activities:
        cur.execute(
            """
            INSERT INTO activities
            (title, category, time_slot, field, mission_type, importance, points, requires_proof, active, created_by_admin)
            VALUES (?,?,?,?,?,?,?,?,1,1)
            """,
            (title, category, ts, field, mtype, imp, pts, 1),
        )

    conn.commit()
    conn.close()


# ---------------- کمک‌ها ----------------

def is_admin(chat_id: int) -> bool:
    return chat_id in ADMIN_IDS


def get_or_create_user(update: Update) -> sqlite3.Row | None:
    chat_id = update.effective_chat.id
    username = update.effective_chat.username or ""

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = cur.fetchone()
    if user:
        conn.close()
        return user

    # کاربر جدید – فقط رکورد خام با chat_id
    cur.execute(
        """
        INSERT INTO users(chat_id, username, created_at)
        VALUES(?,?,?)
        """,
        (chat_id, username, datetime.utcnow().isoformat()),
    )
    conn.commit()
    cur.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = cur.fetchone()
    conn.close()
    return user
# ---------------- STATES ----------------
(
    FIRST_NAME,
    LAST_NAME,
    NATIONAL_ID,
    REFERRAL,
    ROLE,
    TIME_SLOT,
    FIELD,
) = range(1, 8)

# برای سیستم مأموریت
SEND_PROOF = 20


# ---------------- START & REGISTRATION ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update)

    # اگر ثبت نام کامل شده بود، می‌بریمش روی داشبورد
    if user["first_name"] and user["last_name"] and user["national_id"]:
        await update.message.reply_text(
            "خوش آمدید 🌱\n"
            "شما قبلا ثبت نام کرده‌اید.\n"
            "برای دیدن مأموریت‌ها: /missions\n"
            "برای دیدن امتیاز: /score"
        )
        return ConversationHandler.END

    await update.message.reply_text("به پلتفرم تسهیلگری خوش آمدید 🌱\n\nنام خود را وارد کنید:")
    return FIRST_NAME


async def ask_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text.strip()
    await update.message.reply_text("نام خانوادگی خود را وارد کنید:")
    return LAST_NAME


async def ask_national_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_name"] = update.message.text.strip()
    await update.message.reply_text("شماره ملی خود را وارد کنید:")
    return NATIONAL_ID


async def ask_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["national_id"] = update.message.text.strip()
    await update.message.reply_text(
        "کد معرف (در صورت وجود) را وارد کنید:\n"
        "اگر ندارید، خط تیره (-) ارسال کنید."
    )
    return REFERRAL


async def ask_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["referral_code"] = update.message.text.strip()

    await update.message.reply_text(
        "نقش نگار خود را بنویسید (مثلا: دانشجو، مربی، فعال محلی، ...):"
    )
    return ROLE


async def ask_time_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text.strip()

    keyboard = [
        [KeyboardButton("2-5 دقیقه"), KeyboardButton("10-20 دقیقه")],
        [KeyboardButton("30-120 دقیقه"), KeyboardButton("بازه‌ی دلخواه")],
    ]
    await update.message.reply_text(
        "مایل هستید روزانه چه مقدار زمان صرف مسئولیت اجتماعی کنید؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return TIME_SLOT


async def ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "2-5" in text:
        ts = "2-5"
    elif "10-20" in text:
        ts = "10-20"
    elif "30-120" in text:
        ts = "30-120"
    else:
        ts = "custom"

    context.user_data["time_slot"] = ts

    keyboard = [
        [KeyboardButton("فضای مجازی"), KeyboardButton("عرصه میدانی")],
    ]
    await update.message.reply_text(
        "یک عرصه را انتخاب بفرمایید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return FIELD


async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_text = update.message.text.strip()
    if "مجازی" in field_text:
        field = "virtual"
    else:
        field = "field"

    chat_id = update.effective_chat.id
    username = update.effective_chat.username or ""

    data = context.user_data

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET username=?, first_name=?, last_name=?, national_id=?,
            referral_code=?, role=?, time_slot=?, field=?
        WHERE chat_id=?
        """,
        (
            username,
            data.get("first_name"),
            data.get("last_name"),
            data.get("national_id"),
            data.get("referral_code"),
            data.get("role"),
            data.get("time_slot"),
            field,
            chat_id,
        ),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "ثبت نام شما کامل شد ✅\n\n"
        "برای مشاهده مأموریت‌های متناسب با پروفایل‌تان، دستور /missions را ارسال کنید.",
        reply_markup=ReplyKeyboardMarkup([["/missions"]], resize_keyboard=True),
    )

    return ConversationHandler.END
# ---------------- MISSIONS LISTING ----------------

async def missions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = cur.fetchone()

    if not user or not user["time_slot"] or not user["field"]:
        conn.close()
        await update.message.reply_text("ابتدا ثبت نام را تکمیل کنید:\n/start")
        return

    time_slot = user["time_slot"]
    field = user["field"]

    # فقط فعالیت‌های فعال متناسب با بازه زمانی و عرصه کاربر
    cur.execute(
        """
        SELECT id, title, category, mission_type, importance, points
        FROM activities
        WHERE active=1
          AND time_slot=?
          AND field=?
        ORDER BY mission_type, importance DESC
        """,
        (time_slot, field),
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("برای پروفایل شما هنوز فعالیتی ثبت نشده است.")
        return

    text = "📋 مأموریت‌های متناسب با پروفایل شما:\n\n"
    keyboard = []

    for r in rows:
        mission_type_fa = {
            "daily": "امروز",
            "weekly": "این هفته",
            "yearly": "سالانه",
            "self_report": "خوداظهاری",
            "suggestion": "پیشنهادی",
        }.get(r["mission_type"], "نامشخص")

        text += (
            f"#{r['id']} - [{mission_type_fa}] {r['title']}\n"
            f"دسته: {r['category']} | اهمیت: {r['importance']} | امتیاز: {r['points']}\n\n"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"✅ انجام #{r['id']}", callback_data=f"done_{r['id']}"
                )
            ]
        )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
# ---------------- DASHBOARD / SCORE ----------------

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        await update.message.reply_text("ابتدا ثبت نام کنید:\n/start")
        return

    cur.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved_count
        FROM missions
        WHERE user_id=?
        """,
        (user["id"],),
    )
    m = cur.fetchone()

    total = m["total"] or 0
    approved = m["approved_count"] or 0

    text = (
        f"👤 {user['first_name']} {user['last_name']}\n\n"
        f"🏅 امتیاز کل: {user['score']}\n"
        f"📌 مأموریت ثبت شده: {total}\n"
        f"✅ مأموریت تایید شده: {approved}\n"
        f"⏱ بازه زمانی: {user['time_slot']}\n"
        f"🌐 عرصه فعالیت: {user['field']}"
    )

    conn.close()
    await update.message.reply_text(text)


# ---------------- SUGGESTIONS (پیشنهاد فعالیت جدید) ----------------

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_or_create_user(update)
    if not user or not user["first_name"]:
        await update.message.reply_text("ابتدا ثبت نام را تکمیل کنید:\n/start")
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text(
            "لطفاً بعد از دستور /suggest متن پیشنهاد فعالیت خود را بنویسید.\n"
            "مثال:\n"
            "/suggest برگزاری پویش کتابخوانی در محله"
        )
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO suggestions(user_id, text, status, created_at)
        VALUES(?,?, 'new', ?)
        """,
        (user["id"], text, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ پیشنهاد شما ثبت شد و توسط پشتیبانی بررسی می‌شود.")
# ---------------- DONE FLOW: درخواست مدرک ----------------

async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    activity_id = int(query.data.split("_")[1])
    context.user_data["activity_id"] = activity_id

    await query.message.reply_text(
        "لطفا اسکرین‌شات یا عکس مدرک انجام این فعالیت را ارسال کنید 📷"
    )

    return SEND_PROOF


# ---------------- دریافت مدرک ----------------

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_or_create_user(update)
    if not user:
        await update.message.reply_text("ابتدا ثبت نام کنید:\n/start")
        return ConversationHandler.END

    if "activity_id" not in context.user_data:
        await update.message.reply_text("خطا در ثبت مأموریت. دوباره /missions را بزنید.")
        return ConversationHandler.END

    activity_id = context.user_data["activity_id"]

    # فقط عکس را قبول می‌کنیم (در صورت نیاز می‌توان caption را هم ذخیره کرد)
    if not update.message.photo:
        await update.message.reply_text("لطفاً حتما یک عکس ارسال کنید.")
        return SEND_PROOF

    photo_file_id = update.message.photo[-1].file_id

    conn = get_db_connection()
    cur = conn.cursor()

    # اهمیت و نوع مأموریت را از خود فعالیت بگیریم
    cur.execute("SELECT mission_type, importance FROM activities WHERE id=?", (activity_id,))
    act = cur.fetchone()
    if not act:
        conn.close()
        await update.message.reply_text("فعالیت پیدا نشد. دوباره /missions را بزنید.")
        return ConversationHandler.END

    mission_type = act["mission_type"]
    importance = act["importance"]

    now = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT INTO missions(user_id, activity_id, mission_type, status, proof, importance, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (user["id"], activity_id, mission_type, "pending", photo_file_id, importance, now, now),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ مأموریت ثبت شد و در حالت «در انتظار تأیید» است.\n"
        "پس از بررسی ادمین، در صورت تأیید، امتیاز به حساب شما اضافه می‌شود."
    )

    # پاک کردن state
    context.user_data.pop("activity_id", None)
    return ConversationHandler.END
# ---------------- ADMIN PANEL ----------------

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ شما دسترسی مدیر ندارید.")
        return

    keyboard = [
        [InlineKeyboardButton("📋 لیست فعالیت‌ها", callback_data="admin_activities")],
        [InlineKeyboardButton("🕒 مأموریت‌های در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton("➕ افزودن فعالیت", callback_data="admin_add_help")],
        [InlineKeyboardButton("🏆 لیدربورد کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("💡 پیشنهادهای کاربران", callback_data="admin_suggestions")],
    ]

    await update.message.reply_text(
        "پنل مدیریت:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    # لیست فعالیت‌ها
    if data == "admin_activities":
        cur.execute(
            """
            SELECT id, title, category, time_slot, field, mission_type, importance, points, active
            FROM activities
            ORDER BY id DESC
            """
        )
        rows = cur.fetchall()

        if not rows:
            text = "هیچ فعالیتی ثبت نشده است."
        else:
            text = "📋 لیست فعالیت‌ها:\n\n"
            for r in rows:
                act = "فعال" if r["active"] else "غیرفعال"
                text += (
                    f"ID:{r['id']} | {r['title']}\n"
                    f"دسته: {r['category']} | بازه: {r['time_slot']} | عرصه: {r['field']}\n"
                    f"نوع مأموریت: {r['mission_type']} | اهمیت: {r['importance']} | امتیاز: {r['points']} | {act}\n\n"
                )

        await query.edit_message_text(text)

    # مأموریت‌های در انتظار تأیید
    elif data == "admin_pending":
        cur.execute(
            """
            SELECT m.id AS mid, u.first_name, u.last_name, a.title, m.created_at
            FROM missions m
            JOIN users u ON m.user_id = u.id
            JOIN activities a ON m.activity_id = a.id
            WHERE m.status='pending'
            ORDER BY m.created_at ASC
            LIMIT 30
            """
        )
        rows = cur.fetchall()

        if not rows:
            await query.edit_message_text("هیچ مأموریت در انتظار تأیید نیست.")
        else:
            text = "🕒 مأموریت‌های در انتظار:\n\n"
            keyboard = []
            for r in rows:
                text += (
                    f"#{r['mid']} - {r['first_name']} {r['last_name']}\n"
                    f"فعالیت: {r['title']}\n"
                    f"ثبت در: {r['created_at']}\n\n"
                )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"✅ تایید #{r['mid']}", callback_data=f"appr_{r['mid']}"
                        ),
                        InlineKeyboardButton(
                            f"❌ رد #{r['mid']}", callback_data=f"rej_{r['mid']}"
                        ),
                    ]
                )

            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # راهنمای افزودن فعالیت
    elif data == "admin_add_help":
        await query.edit_message_text(
            "برای افزودن فعالیت جدید، از این فرمت استفاده کنید:\n\n"
            "/addactivity عنوان | دسته | time_slot | field | mission_type | importance | points\n\n"
            "مثال:\n"
            "/addactivity لایک پست | تعامل | 2-5 | virtual | daily | 1 | 2"
        )

    # لیدربورد کاربران
    elif data == "admin_users":
        cur.execute(
            """
            SELECT first_name, last_name, score
            FROM users
            ORDER BY score DESC
            LIMIT 20
            """
        )
        users = cur.fetchall()

        if not users:
            await query.edit_message_text("کاربری ثبت نشده است.")
        else:
            text = "🏆 رتبه‌بندی کاربران:\n\n"
            rank = 1
            for u in users:
                text += (
                    f"{rank}. {u['first_name']} {u['last_name']} - {u['score']} امتیاز\n"
                )
                rank += 1

            await query.edit_message_text(text)

    # پیشنهادهای کاربران
    elif data == "admin_suggestions":
        cur.execute(
            """
            SELECT s.id, u.first_name, u.last_name, s.text, s.status
            FROM suggestions s
            JOIN users u ON s.user_id = u.id
            WHERE s.status='new'
            ORDER BY s.id DESC
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        if not rows:
            await query.edit_message_text("پیشنهاد جدیدی وجود ندارد.")
        else:
            text = "💡 پیشنهادهای جدید:\n\n"
            keyboard = []
            for r in rows:
                text += (
                    f"#{r['id']} - {r['first_name']} {r['last_name']}:\n"
                    f"{r['text']}\n\n"
                )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"قبول #{r['id']}", callback_data=f"suggacc_{r['id']}"
                        ),
                        InlineKeyboardButton(
                            f"رد #{r['id']}", callback_data=f"suggrej_{r['id']}"
                        ),
                    ]
                )

            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    conn.close()


# ---------------- افزودن فعالیت توسط ادمین ----------------

async def add_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return

    text = update.message.text.replace("/addactivity", "").strip()
    try:
        title, category, time_slot, field, mission_type, importance, points = [
            p.strip() for p in text.split("|")
        ]
        importance = int(importance)
        points = int(points)
    except Exception:
        await update.message.reply_text(
            "فرمت اشتباه است.\n"
            "فرمت درست:\n"
            "/addactivity عنوان | دسته | time_slot | field | mission_type | importance | points"
        )
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activities
        (title, category, time_slot, field, mission_type, importance, points, requires_proof, active, created_by_admin)
        VALUES (?,?,?,?,?,?,?,?,1,1)
        """,
        (title, category, time_slot, field, mission_type, importance, points, 1),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ فعالیت جدید اضافه شد.")


# ---------------- تأیید / رد مأموریت‌ها (Callback) ----------------

async def admin_mission_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    if data.startswith("appr_"):
        mid = int(data.split("_")[1])

        # ماموریت + فعالیت + کاربر
        cur.execute(
            """
            SELECT m.*, a.points, u.chat_id
            FROM missions m
            JOIN activities a ON m.activity_id = a.id
            JOIN users u ON m.user_id = u.id
            WHERE m.id=?
            """,
            (mid,),
        )
        m = cur.fetchone()
        if not m:
            conn.close()
            await query.edit_message_text("ماموریت پیدا نشد.")
            return

        if m["status"] != "pending":
            conn.close()
            await query.edit_message_text("این ماموریت قبلا بررسی شده است.")
            return

        points = m["points"]
        user_chat_id = m["chat_id"]

        # آپدیت وضعیت ماموریت
        cur.execute(
            "UPDATE missions SET status='approved', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), mid),
        )
        # اضافه کردن امتیاز
        cur.execute(
            "UPDATE users SET score = score + ? WHERE id=?",
            (points, m["user_id"]),
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(f"✅ مأموریت #{mid} تأیید شد (+{points} امتیاز).")

        # اطلاع به کاربر
        try:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=f"✅ مأموریت شما (ID: {mid}) تایید شد و {points} امتیاز گرفتید.",
            )
        except Exception:
            pass

    elif data.startswith("rej_"):
        mid = int(data.split("_")[1])

        cur.execute(
            """
            SELECT m.*, u.chat_id
            FROM missions m
            JOIN users u ON m.user_id = u.id
            WHERE m.id=?
            """,
            (mid,),
        )
        m = cur.fetchone()
        if not m:
            conn.close()
            await query.edit_message_text("ماموریت پیدا نشد.")
            return

        if m["status"] != "pending":
            conn.close()
            await query.edit_message_text("این ماموریت قبلا بررسی شده است.")
            return

        cur.execute(
            "UPDATE missions SET status='rejected', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), mid),
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(f"❌ مأموریت #{mid} رد شد.")

        # اطلاع به کاربر
        try:
            await context.bot.send_message(
                chat_id=m["chat_id"],
                text=f"❌ مأموریت شما (ID: {mid}) توسط ادمین رد شد.",
            )
        except Exception:
            pass

    # پذیرش/رد پیشنهادها
    elif data.startswith("suggacc_") or data.startswith("suggrej_"):
        sid = int(data.split("_")[1])
        new_status = "accepted" if data.startswith("suggacc_") else "rejected"
        cur.execute(
            "UPDATE suggestions SET status=?, reviewed_at=? WHERE id=?",
            (new_status, datetime.utcnow().isoformat(), sid),
        )
        conn.commit()
        conn.close()

        msg = "✅ پیشنهاد پذیرفته شد." if new_status == "accepted" else "❌ پیشنهاد رد شد."
        await query.edit_message_text(msg)


# ---------------- MAIN ----------------

def main():
    init_db()
    seed_activities()

    app = (
    ApplicationBuilder()
    .token(TOKEN)
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
)


    # ثبت‌نام
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_last_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_national_id)],
            NATIONAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_referral)],
            REFERRAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_role)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time_slot)],
            TIME_SLOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_field)],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_registration)],
            SEND_PROOF: [MessageHandler(filters.PHOTO, receive_proof)],
        },
        fallbacks=[],
    )
    app.add_handler(conv)

    # دستورات عمومی
    app.add_handler(CommandHandler("missions", missions))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("suggest", suggest))
    app.add_handler(MessageHandler(filters.PHOTO, receive_proof))


    # ادمین
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addactivity", add_activity))

    # کال‌بک‌ها
    app.add_handler(CallbackQueryHandler(done_callback, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_mission_decision, pattern="^(appr_|rej_|suggacc_|suggrej_)"))

    app.run_polling()


if __name__ == "__main__":
    main()
