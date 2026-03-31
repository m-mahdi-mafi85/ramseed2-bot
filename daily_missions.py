import random

def generate_daily_mission():
    missions = [
        {
            "title": "مأموریت روز",
            "description": "امروز یک متن ۵۰ تا ۱۵۰ کلمه‌ای درباره یک اتفاق کوچک اما واقعی بنویس.",
            "points": 30
        },
        {
            "title": "چالش خبری",
            "description": "یک خبر کوتاه و دقیق از یک اتفاق محلی یا خانوادگی بنویس.",
            "points": 25
        },
        {
            "title": "داستانک ۱۰۰ کلمه‌ای",
            "description": "یک داستان کوتاه ۱۰۰ کلمه‌ای با محوریت «امید» بنویس.",
            "points": 20
        },
        {
            "title": "گزارش لحظه‌ای",
            "description": "یک لحظه از امروز که برایت جالب بود را به شکل گزارش خبری بنویس.",
            "points": 30
        }
    ]

    return random.choice(missions)
