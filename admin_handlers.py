from telegram import Update
from models import (
    get_pending_submissions,
    update_submission_status,
    add_points,
    get_submission_user,
)


async def admin_panel(update: Update, context):
    msg = update.message or update.callback_query.message

    subs = get_pending_submissions()

    if not subs:
        await msg.reply_text("هیچ مدرکی برای بررسی وجود ندارد.")
        return

    for sub in subs:
        sub_id, name, mission_title, type, content, file_id = sub

        caption = (
            f"👤 کاربر: {name}\n"
            f"📝 مأموریت: {mission_title}\n"
            f"📄 نوع مدرک: {type}\n\n"
        )

        if type == "text":
            caption += content
            sent = await msg.reply_text(caption)

        elif type == "photo":
            sent = await msg.reply_photo(file_id, caption=caption)

        else:
            sent = await msg.reply_document(file_id, caption=caption)

        await sent.reply_text(
            f"➕ امتیازدهی:\n"
            f"/accept_{sub_id}_10    قبول +10 امتیاز\n"
            f"/accept_{sub_id}_20    قبول +20 امتیاز\n"
            f"/reject_{sub_id}       رد"
        )


async def accept_submission(update: Update, context):
    _, sub_id, points = update.message.text.split("_")
    sub_id = int(sub_id)
    points = int(points)

    user_id = get_submission_user(sub_id)
    if user_id:
        add_points(user_id, points)

    update_submission_status(sub_id, "accepted")

    await update.message.reply_text(f"✔ مدرک تأیید شد. +{points} امتیاز")


async def reject_submission(update: Update, context):
    _, sub_id = update.message.text.split("_")
    sub_id = int(sub_id)

    update_submission_status(sub_id, "rejected")

    await update.message.reply_text("❌ مدرک رد شد.")
