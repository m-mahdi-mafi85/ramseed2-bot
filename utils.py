# utils.py
# -----------------------------------------------------------
# توابع کمکی سطح، امتیاز و نمایش پیشرفت
# -----------------------------------------------------------

import random

RANKS = [
    (1, "📝 نویسنده تازه‌کار"),
    (3, "✍️ خبرنگار فعال"),
    (6, "📰 خبرنگار حرفه‌ای"),
    (10, "📡 تحلیلگر رسانه"),
    (15, "🎖 استاد رسانه")
]


def random_emoji():
    emojis = ["✨", "🔥", "🚀", "🎯", "💡", "⭐"]
    return random.choice(emojis)


def wrap_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]


def calculate_level(points):
    return (points // 100) + 1


def get_rank(level):
    current = RANKS[0][1]
    for lvl, title in RANKS:
        if level >= lvl:
            current = title
    return current


def get_progress_bar(points):

    level = calculate_level(points)
    base = (level - 1) * 100
    progress = points - base

    filled = int((progress / 100) * 20)
    bar = "█" * filled + "░" * (20 - filled)

    return f"{bar}  {progress}/100"


def format_profile(user):

    level = calculate_level(user["points"])
    rank = get_rank(level)

    bar = get_progress_bar(user["points"])

    txt = f"""
👤 **پروفایل کاربر**

نام: {user['full_name']}
نقش: {user['role']}

سطح فعلی: {level}
رتبه: {rank}

امتیاز کل: {user['points']}

پیشرفت تا سطح بعدی:
{bar}
"""
    return txt
