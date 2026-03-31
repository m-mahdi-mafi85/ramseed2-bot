from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from settings import BOT_TOKEN, ADMINS
from mission_handlers import (
    start_submission,
    receive_text_submission,
    receive_photo_submission,
    receive_file_submission,
    SUBMIT_WAIT,
)
from admin_handlers import admin_panel, accept_submission, reject_submission


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Submit conversation ---
    submit_conv = ConversationHandler(
        entry_points=[CommandHandler("submit", start_submission)],
        states={
            SUBMIT_WAIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text_submission),
                MessageHandler(filters.PHOTO, receive_photo_submission),
                MessageHandler(filters.Document.ALL, receive_file_submission),
            ]
        },
        fallbacks=[],
    )
    application.add_handler(submit_conv)

    # --- Admin panel ---
    application.add_handler(CommandHandler("admin", admin_panel))

    # --- Accept/Reject ---
    application.add_handler(CommandHandler("accept", accept_submission))
    application.add_handler(CommandHandler("reject", reject_submission))

    print("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
