from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from models import (
    get_user,
    create_user,
    save_suggestion
)

from keyboards import (
    main_menu_keyboard
)

from settings import ROLES


# states
REGISTER_NAME = 1
REGISTER_ROLE = 2
SUGGEST_TEXT = 3


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if user:
        await update.message.reply_text(
            "به باشگاه نویسندگان خوش آمدید.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "به باشگاه نویسندگان خوش آمدید.\n\n"
        "برای شروع ثبت‌نام لطفاً نام خود را ارسال کنید."
    )

    return REGISTER_NAME


# ---------------- REGISTER ----------------

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text

    roles_text = "\n".join([f"- {r}" for r in ROLES])

    await update.message.reply_text(
        "نقش خود را انتخاب کنید:\n\n" + roles_text
    )

    return REGISTER_ROLE


async def register_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text

    if role not in ROLES:
        await update.message.reply_text("لطفاً یکی از نقش‌های معتبر را انتخاب کنید.")
        return REGISTER_ROLE

    name = context.user_data["name"]
    user_id = update.effective_user.id

    create_user(
        telegram_id=user_id,
        name=name,
        role=role
    )

    await update.message.reply_text(
        "✅ ثبت‌نام با موفقیت انجام شد.",
        reply_markup=main_menu_keyboard()
    )

    return ConversationHandler.END


# ---------------- DASHBOARD ----------------

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text("ابتدا با /start ثبت‌نام کنید.")
        return

    name = user["name"]
    role = user["role"]
    points = user["points"]

    text = (
        f"👤 نام: {name}\n"
        f"🎭 نقش: {role}\n"
        f"⭐ امتیاز: {points}"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu_keyboard()
    )


# ---------------- PROFILE ----------------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text("کاربر یافت نشد.")
        return

    text = (
        f"📌 پروفایل شما\n\n"
        f"نام: {user['name']}\n"
        f"نقش: {user['role']}\n"
        f"امتیاز: {user['points']}"
    )

    await update.message.reply_text(text)


# ---------------- SUGGESTION ----------------

async def suggest_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "پیشنهاد خود را ارسال کنید:"
    )

    return SUGGEST_TEXT


async def receive_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    save_suggestion(user_id, text)

    await update.message.reply_text(
        "✅ پیشنهاد شما ثبت شد."
    )

    return ConversationHandler.END


# ---------------- CANCEL ----------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END


# ---------------- HANDLER REGISTER ----------------

def get_user_handlers():

    register_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)
            ],
            REGISTER_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_role)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    suggestion_conv = ConversationHandler(
        entry_points=[CommandHandler("suggest", suggest_start)],
        states={
            SUGGEST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_suggestion)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    return [
        register_conv,
        suggestion_conv,
        CommandHandler("dashboard", dashboard),
        CommandHandler("profile", profile),
    ]
