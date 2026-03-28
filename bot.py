import sqlite3
from datetime import datetime
import logging

# telegram
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
Application,
CommandHandler,
MessageHandler,
ConversationHandler,
ContextTypes,
filters
)

# admin panel
import streamlit as st
import pandas as pd

TOKEN = "8747795870:AAEpTEuNHLjmjCLJam_Gng-cDT6s_hswpgI"
DB_NAME = "club.db"

logging.basicConfig(level=logging.INFO)

FIRST, LAST, NATIONAL, REF, ROLE, TIME, FIELD = range(7)

def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    first_name TEXT,
    last_name TEXT,
    national_id TEXT,
    referral TEXT,
    role TEXT,
    time_slot TEXT,
    field TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS activities(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    category TEXT,
    time_slot TEXT,
    active INTEGER DEFAULT 1
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS missions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    activity_id INTEGER,
    status TEXT,
    proof TEXT,
    created TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS suggestions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    created TEXT
    )
    """)

    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
به باشگاه نویسندگان فردا خوش آمدید

دستورات:
/register ثبت نام
/mission دریافت ماموریت
/done ثبت انجام
/dashboard داشبورد
/suggest پیشنهاد
"""
    await update.message.reply_text(text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("نام؟")
    return FIRST

async def first(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first"] = update.message.text
    await update.message.reply_text("نام خانوادگی؟")
    return LAST

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last"] = update.message.text
    await update.message.reply_text("شماره ملی؟")
    return NATIONAL

async def national(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["national"] = update.message.text
    await update.message.reply_text("کد معرف؟")
    return REF

async def ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ref"] = update.message.text
    keyboard = [["نگار","پژوهشگر","رسانه"]]
    await update.message.reply_text(
        "نقش شما؟",
        reply_markup=ReplyKeyboardMarkup(keyboard,one_time_keyboard=True)
    )
    return ROLE

async def role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    keyboard=[["۲-۵","۱۰-۲۰","۳۰-۱۲۰"]]
    await update.message.reply_text(
        "زمان فعالیت؟",
        reply_markup=ReplyKeyboardMarkup(keyboard,one_time_keyboard=True)
    )
    return TIME

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"]=update.message.text
    keyboard=[["مجازی","میدانی","هردو"]]
    await update.message.reply_text(
        "عرصه فعالیت؟",
        reply_markup=ReplyKeyboardMarkup(keyboard,one_time_keyboard=True)
    )
    return FIELD

async def field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["field"]=update.message.text

    conn=get_db()
    c=conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO users
    (telegram_id,first_name,last_name,national_id,referral,role,time_slot,field)
    VALUES(?,?,?,?,?,?,?,?)
    """,(
    update.effective_user.id,
    context.user_data["first"],
    context.user_data["last"],
    context.user_data["national"],
    context.user_data["ref"],
    context.user_data["role"],
    context.user_data["time"],
    context.user_data["field"]
    ))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "ثبت نام انجام شد ✅",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def mission(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn=get_db()
    c=conn.cursor()

    c.execute("SELECT id,time_slot FROM users WHERE telegram_id=?",
    (update.effective_user.id,))
    user=c.fetchone()

    if not user:
        await update.message.reply_text("اول /register بزن")
        return

    user_id=user[0]
    time_slot=user[1]

    c.execute("""
    SELECT id,title FROM activities
    WHERE active=1 AND time_slot=?
    ORDER BY RANDOM()
    LIMIT 1
    """,(time_slot,))

    act=c.fetchone()

    if not act:
        await update.message.reply_text("فعلا فعالیتی نیست")
        return

    act_id,title=act

    c.execute("""
    INSERT INTO missions(user_id,activity_id,status,created)
    VALUES(?,?,?,?)
    """,(user_id,act_id,"pending",datetime.now().isoformat()))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"ماموریت شما:\n\n{title}\n\nبعد از انجام /done بزن"
    )

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn=get_db()
    c=conn.cursor()

    c.execute("""
    UPDATE missions
    SET status='done'
    WHERE id=(SELECT id FROM missions ORDER BY id DESC LIMIT 1)
    """)

    conn.commit()
    conn.close()

    await update.message.reply_text("ثبت شد ✅")

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn=get_db()
    c=conn.cursor()

    c.execute("SELECT COUNT(*) FROM missions WHERE status='done'")
    done=c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM missions WHERE status='pending'")
    pending=c.fetchone()[0]

    conn.close()

    await update.message.reply_text(
        f"""
داشبورد شما

انجام شده: {done}
در انتظار: {pending}
"""
    )

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text=update.message.text.replace("/suggest","")

    conn=get_db()
    c=conn.cursor()

    c.execute("""
    INSERT INTO suggestions(user_id,text,created)
    VALUES(?,?,?)
    """,(update.effective_user.id,text,datetime.now().isoformat()))

    conn.commit()
    conn.close()

    await update.message.reply_text("پیشنهاد ثبت شد")

def run_bot():

    init_db()

    app=Application.builder().token(TOKEN).build()

    conv=ConversationHandler(
        entry_points=[CommandHandler("register",register)],
        states={
            FIRST:[MessageHandler(filters.TEXT,first)],
            LAST:[MessageHandler(filters.TEXT,last)],
            NATIONAL:[MessageHandler(filters.TEXT,national)],
            REF:[MessageHandler(filters.TEXT,ref)],
            ROLE:[MessageHandler(filters.TEXT,role)],
            TIME:[MessageHandler(filters.TEXT,time)],
            FIELD:[MessageHandler(filters.TEXT,field)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start",start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("mission",mission))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("dashboard",dashboard))
    app.add_handler(CommandHandler("suggest",suggest))

    app.run_polling()

def run_admin():

    st.title("پنل مدیریت باشگاه")

    menu=st.sidebar.selectbox("منو",
    ["کاربران","فعالیت ها","ماموریت ها","پیشنهادات"])

    conn=get_db()

    if menu=="کاربران":

        df=pd.read_sql("SELECT * FROM users",conn)
        st.dataframe(df)

    if menu=="فعالیت ها":

        title=st.text_input("عنوان فعالیت")
        cat=st.selectbox("دسته",["مجازی","میدانی"])
        time=st.selectbox("زمان",["۲-۵","۱۰-۲۰","۳۰-۱۲۰"])

        if st.button("ثبت"):

            c=conn.cursor()
            c.execute("""
            INSERT INTO activities(title,category,time_slot)
            VALUES(?,?,?)
            """,(title,cat,time))

            conn.commit()
            st.success("ثبت شد")

        df=pd.read_sql("SELECT * FROM activities",conn)
        st.dataframe(df)

    if menu=="ماموریت ها":

        df=pd.read_sql("""
        SELECT missions.id,activities.title,missions.status
        FROM missions
        JOIN activities
        ON missions.activity_id=activities.id
        """,conn)

        st.dataframe(df)

    if menu=="پیشنهادات":

        df=pd.read_sql("SELECT * FROM suggestions",conn)
        st.dataframe(df)

if __name__=="__main__":
    run_bot()
