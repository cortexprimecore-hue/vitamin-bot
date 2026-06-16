import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

TOKEN = "7820069678:AAFm_fiG_Ox_Uwbsp1GOMYqgqJMgytqR8fs"
CHAT_ID = 459283662

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

daily_status = {}

def reset_daily_status():
    global daily_status
    daily_status = {
        "before_breakfast": False,
        "after_breakfast": False,
        "before_lunch": False,
        "before_dinner": False,
    }

reset_daily_status()

MEAL_LABELS = {
    "before_breakfast": "до завтрака",
    "after_breakfast":  "после завтрака",
    "before_lunch":     "до обеда",
    "before_dinner":    "до ужина",
}

def meal_keyboard(meal: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("5 мин", callback_data=f"in:{meal}:5"),
            InlineKeyboardButton("15 мин", callback_data=f"in:{meal}:15"),
            InlineKeyboardButton("30 мин", callback_data=f"in:{meal}:30"),
            InlineKeyboardButton("60 мин", callback_data=f"in:{meal}:60"),
        ],
        [InlineKeyboardButton("Ввести своё время", callback_data=f"custom:{meal}")],
        [InlineKeyboardButton("Уже ем", callback_data=f"now:{meal}")],
    ]
    return InlineKeyboardMarkup(buttons)

def vitamin_keyboard(vitamin_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Принял!", callback_data=f"taken:{vitamin_key}"),
        InlineKeyboardButton("Напомни через 30 мин", callback_data=f"snooze:{vitamin_key}"),
    ]])

def after_breakfast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("15 мин", callback_data="after:15"),
        InlineKeyboardButton("30 мин", callback_data="after:30"),
        InlineKeyboardButton("45 мин", callback_data="after:45"),
    ]])

async def ask_meal(context: ContextTypes.DEFAULT_TYPE, meal: str):
    names = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"Привет! Через сколько планируешь {names[meal]}?",
        reply_markup=meal_keyboard(meal),
    )

async def job_ask_breakfast(context: ContextTypes.DEFAULT_TYPE):
    await ask_meal(context, "breakfast")

async def job_ask_lunch(context: ContextTypes.DEFAULT_TYPE):
    await ask_meal(context, "lunch")

async def job_ask_dinner(context: ContextTypes.DEFAULT_TYPE):
    await ask_meal(context, "dinner")

async def job_reset(context: ContextTypes.DEFAULT_TYPE):
    reset_daily_status()

async def send_vitamin_reminder(context: ContextTypes.DEFAULT_TYPE):
    vitamin_key = context.job.data["vitamin_key"]
    if daily_status.get(vitamin_key):
        return
    label = MEAL_LABELS[vitamin_key]
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"Пора принять витамины {label}!",
        reply_markup=vitamin_keyboard(vitamin_key),
    )
    context.job_queue.run_once(
        send_vitamin_reminder,
        when=timedelta(minutes=30),
        data={"vitamin_key": vitamin_key},
        name=f"retry_{vitamin_key}",
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    meal_map = {
        "breakfast": "before_breakfast",
        "lunch": "before_lunch",
        "dinner": "before_dinner",
    }
    meal_names = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}

    if data.startswith("in:"):
        _, meal, mins_str = data.split(":")
        mins = int(mins_str)
        vitamin_key = meal_map[meal]
        remind_in = max(1, mins - 5)
        await query.edit_message_text(
            f"Отлично! Напомню про витамины до {meal_names[meal]}а через {remind_in} мин."
        )
        context.job_queue.run_once(
            send_vitamin_reminder,
            when=timedelta(minutes=remind_in),
            data={"vitamin_key": vitamin_key},
        )
        if meal == "breakfast":
            context.job_queue.run_once(
                ask_after_breakfast,
                when=timedelta(minutes=mins + 5),
                data={},
            )

    elif data.startswith("now:"):
        meal = data.split(":")[1]
        vitamin_key = meal_map[meal]
        await query.edit_message_text(
            f"Принимай витамины до {meal_names[meal]}а прямо сейчас!"
        )
        context.job_queue.run_once(
            send_vitamin_reminder,
            when=timedelta(seconds=5),
            data={"vitamin_key": vitamin_key},
        )
        if meal == "breakfast":
            context.job_queue.run_once(
                ask_after_breakfast,
                when=timedelta(minutes=20),
                data={},
            )

    elif data.startswith("custom:"):
        meal = data.split(":")[1]
        context.user_data["waiting_custom_meal"] = meal
        await query.edit_message_text(
            f"Напиши через сколько минут планируешь {meal_names[meal]} (просто цифру, например 45):"
        )

    elif data.startswith("after:"):
        mins = int(data.split(":")[1])
        await query.edit_message_text(f"Напомню витамины после завтрака через {mins} мин!")
        context.job_queue.run_once(
            send_vitamin_reminder,
            when=timedelta(minutes=mins),
            data={"vitamin_key": "after_breakfast"},
        )

    elif data.startswith("taken:"):
        vitamin_key = data.split(":")[1]
        daily_status[vitamin_key] = True
        label = MEAL_LABELS[vitamin_key]
        await query.edit_message_text(f"Принял витамины {label}! Молодец!")
        if vitamin_key == "before_breakfast":
            await context.bot.send_message(
                chat_id=chat_id,
                text="Через сколько закончишь завтракать? Напомню про витамины после.",
                reply_markup=after_breakfast_keyboard(),
            )

    elif data.startswith("snooze:"):
        vitamin_key = data.split(":")[1]
        label = MEAL_LABELS[vitamin_key]
        await query.edit_message_text(f"Напомню про витамины {label} через 30 минут!")
        context.job_queue.run_once(
            send_vitamin_reminder,
            when=timedelta(minutes=30),
            data={"vitamin_key": vitamin_key},
        )

async def ask_after_breakfast(context: ContextTypes.DEFAULT_TYPE):
    if daily_status.get("after_breakfast"):
        return
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="Позавтракал? Через сколько минут напомнить про витамины после завтрака?",
        reply_markup=after_breakfast_keyboard(),
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meal = context.user_data.get("waiting_custom_meal")
    if meal:
        try:
            mins = int(update.message.text.strip())
            vitamin_key = {"breakfast": "before_breakfast", "lunch": "before_lunch", "dinner": "before_dinner"}[meal]
            meal_names = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}
            remind_in = max(1, mins - 5)
            await update.message.reply_text(
                f"Напомню про витамины до {meal_names[meal]}а через {remind_in} мин!"
            )
            context.job_queue.run_once(
                send_vitamin_reminder,
                when=timedelta(minutes=remind_in),
                data={"vitamin_key": vitamin_key},
            )
            context.user_data["waiting_custom_meal"] = None
        except ValueError:
            await update.message.reply_text("Напиши просто цифру, например: 45")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я буду напоминать тебе про витамины.\n\n"
        "Каждый день я сам спрошу тебя:\n"
        "В 8:00 — про завтрак\n"
        "В 13:00 — про обед\n"
        "В 18:00 — про ужин\n\n"
        "Или нажми кнопку прямо сейчас:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Завтрак", callback_data="now:breakfast"),
            InlineKeyboardButton("Обед", callback_data="now:lunch"),
            InlineKeyboardButton("Ужин", callback_data="now:dinner"),
        ]])
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    icons = {"before_breakfast": "до завтрака", "after_breakfast": "после завтрака",
             "before_lunch": "до обеда", "before_dinner": "до ужина"}
    lines = []
    for key, label in icons.items():
        icon = "Принял" if daily_status.get(key) else "Не принял"
        lines.append(f"{icon} — {label}")
    await update.message.reply_text("Статус на сегодня:\n" + "\n".join(lines))

from telegram.ext import MessageHandler, filters

def main():
    from datetime import time as dtime
    import pytz
    tz = pytz.timezone("Europe/Amsterdam")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    jq = app.job_queue
    jq.run_daily(job_ask_breakfast, time=dtime(8, 0, tzinfo=tz), name="ask_breakfast")
    jq.run_daily(job_ask_lunch,     time=dtime(13, 0, tzinfo=tz), name="ask_lunch")
    jq.run_daily(job_ask_dinner,    time=dtime(18, 0, tzinfo=tz), name="ask_dinner")
    jq.run_daily(job_reset,         time=dtime(0, 0, tzinfo=tz),  name="reset")

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
