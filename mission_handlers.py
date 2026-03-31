from telegram import Update
from telegram.ext import ConversationHandler
from models import get_user_by_tg, save_submission


SUBMIT_WAIT = 1


async def start_submission(update: Update, context):
    user = update.message.from_user
    mission_id = context.user_data.get("mission_id")

    if not mission_id:
        await update.message.reply_text("❌ ابتدا یک مأموریت را انتخاب کن.")
        return ConversationHandler.END

    await update.message.reply_text(
        "مدرک مأموریت را ارسال کن:\n\n"
        "• متن\n"
        "• عکس\n"
        "• فایل (PDF — Word — Zip)\n"
    )

    return SUBMIT_WAIT


async def receive_text_submission(update: Update, context):
    user = update.message.from_user
    text = update.message.text
    mission_id = context.user_data.get("mission_id")

    u = get_user_by_tg(user.id)
    save_submission(u["id"], mission_id, "text", text)

    await update.message.reply_text("✔ متن شما ثبت شد و منتظر بررسی ادمین است.")
    return ConversationHandler.END


async def receive_photo_submission(update: Update, context):
    user = update.message.from_user
    photo = update.message.photo[-1]
    file_id = photo.file_id
    mission_id = context.user_data.get("mission_id")

    u = get_user_by_tg(user.id)
    save_submission(u["id"], mission_id, "photo", "", file_id)

    await update.message.reply_text("✔ عکس شما ثبت شد و منتظر بررسی ادمین است.")
    return ConversationHandler.END


async def receive_file_submission(update: Update, context):
    user = update.message.from_user
    file = update.message.document
    file_id = file.file_id
    mission_id = context.user_data.get("mission_id")

    u = get_user_by_tg(user.id)
    save_submission(u["id"], mission_id, "file", "", file_id)

    await update.message.reply_text("✔ فایل شما ثبت شد و منتظر بررسی ادمین است.")
    return ConversationHandler.END
