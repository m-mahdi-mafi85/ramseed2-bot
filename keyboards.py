from telegram import ReplyKeyboardMarkup

def user_main_menu():
    buttons = [
        ["📋 داشبورد", "📨 ارسال پیشنهاد"],
        ["📝 مأموریت‌ها", "📤 ارسال مدرک"],
        ["🏆 رتبه‌بندی"],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
