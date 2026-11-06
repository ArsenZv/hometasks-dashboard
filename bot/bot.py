"""Telegram bot for the HomeTasks dashboard.

- Password-protected: a chat must send BOT_PASSWORD before it gets anything.
- Polls the dashboard API and notifies when a task turns yellow or red.
- Saturday reminder (and optional daily digest) listing tasks to bring back to green.
- /todo, /list, /done: inspect tasks and mark any task (even a green one) as done.
- /report: household statistics for 30 days, 90 days or all time.
"""
import hmac
import json
import logging
import os
import time as pytime
from datetime import time
from zoneinfo import ZoneInfo

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # would log the bot token in URLs
log = logging.getLogger("hometasks-bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_PASSWORD = os.environ["BOT_PASSWORD"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
TZ = ZoneInfo(os.getenv("TZ", "Europe/Paris"))
SATURDAY_TIME = os.getenv("SATURDAY_TIME", "10:00")
DAILY_DIGEST_TIME = os.getenv("DAILY_DIGEST_TIME", "")  # e.g. "09:00"; empty = disabled
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
STATE_FILE = os.getenv("STATE_FILE", "/state/bot_state.json")

MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
ORDER = {"red": 0, "yellow": 1, "green": 2}

failed_attempts = {}  # chat_id -> (count, locked_until)


# ---------- persistent state ----------
def load_state():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    state.setdefault("chats", [])
    state.setdefault("statuses", {})
    state.setdefault("seeded", False)
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def is_authorized(state, chat_id):
    return chat_id in state["chats"]


# ---------- dashboard API ----------
def client(context) -> httpx.AsyncClient:
    return context.application.bot_data["http"]


async def fetch_tasks(context):
    r = await client(context).get("/api/tasks")
    r.raise_for_status()
    return r.json()


async def refresh_task(context, task_id):
    r = await client(context).post(f"/api/tasks/{task_id}/refresh")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ---------- formatting ----------
def label(t):
    """Task name prefixed with its own emoji (set on the edit page), if any."""
    return f"{t['emoji']} {t['string']}" if t.get("emoji") else t["string"]


def fmt_task(t, colour=True):
    """colour=False for alerts, whose header line already shows the colour."""
    prefix = f"{EMOJI[t['status']]} " if colour else ""
    return f"{prefix}{label(t)} ({t['age_days']:.1f}/{t['lifespan']:g} days)"


def done_keyboard(tasks):
    rows = [[InlineKeyboardButton(f"✅ {label(t)}", callback_data=f"done:{t['id']}")] for t in tasks]
    return InlineKeyboardMarkup(rows) if rows else None


def sorted_tasks(tasks):
    return sorted(tasks, key=lambda t: (ORDER[t["status"]], -t["age_days"] / max(t["lifespan"], 0.1)))


# ---------- auth ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    if is_authorized(state, update.effective_chat.id):
        await update.message.reply_text(
            "You're connected ✅\n/todo – what needs doing\n/list – all tasks\n/done – mark a task as done")
    else:
        await update.message.reply_text("Please send the password.")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Any text from an unauthorised chat is treated as a password attempt."""
    chat_id = update.effective_chat.id
    state = load_state()
    if is_authorized(state, chat_id):
        await update.message.reply_text("Use /todo, /list, /done or /report.")
        return

    count, locked_until = failed_attempts.get(chat_id, (0, 0))
    if locked_until > pytime.time():
        return  # silently ignore while locked

    try:
        await update.message.delete()  # don't leave the password in the chat
    except Exception:
        pass

    supplied = (update.message.text or "").strip()
    if hmac.compare_digest(supplied.encode(), BOT_PASSWORD.encode()):
        failed_attempts.pop(chat_id, None)
        state["chats"].append(chat_id)
        save_state(state)
        log.info("Chat %s authorised", chat_id)
        await context.bot.send_message(chat_id, "Welcome! You'll get alerts when tasks turn yellow or red.\n"
                                                "/todo – what needs doing\n/list – all tasks\n/done – mark a task as done")
    else:
        count += 1
        locked = pytime.time() + LOCK_SECONDS if count >= MAX_FAILS else 0
        failed_attempts[chat_id] = (0 if locked else count, locked)
        log.warning("Failed password attempt from chat %s (%d)", chat_id, count)
        msg = "Too many attempts. Try again in 15 minutes." if locked else "Wrong password."
        await context.bot.send_message(chat_id, msg)


def authorized_only(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_authorized(load_state(), update.effective_chat.id):
            if update.callback_query:
                await update.callback_query.answer("Not authorised", show_alert=True)
            return
        await handler(update, context)
    return wrapper


# ---------- commands ----------
@authorized_only
async def todo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = await fetch_tasks(context)
    counts = {s: sum(1 for t in tasks if t["status"] == s) for s in EMOJI}
    lines = [f"🟢 {counts['green']}   🟡 {counts['yellow']}   🔴 {counts['red']}"]
    attention = [t for t in sorted_tasks(tasks) if t["status"] != "green"]
    if attention:
        lines += [""] + [fmt_task(t) for t in attention]
    else:
        lines.append("\nEverything is green 🎉")
    await update.message.reply_text("\n".join(lines), reply_markup=done_keyboard(attention))


@authorized_only
async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = sorted_tasks(await fetch_tasks(context))
    if not tasks:
        await update.message.reply_text("No tasks yet.")
        return
    await update.message.reply_text("\n".join(fmt_task(t) for t in tasks))


RANGE_LABEL = {"30": "last 30 days", "90": "last 90 days", "all": "all time"}


def range_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=f"report:{key}")
                                  for key, text in (("30", "30 days"), ("90", "90 days"), ("all", "All time"))]])


def build_report(stats, range_key):
    dist, prog = stats["distribution"], stats["progress"]
    lines = [f"📊 Report – {RANGE_LABEL[range_key]}",
             f"Overall progress: {prog['green']:g}% of task-days on track",
             f"{EMOJI['green']} {dist['green']} on track",
             f"{EMOJI['yellow']} {dist['yellow']} ok",
             f"{EMOJI['red']} {dist['red']} overdue"]

    def task_line(prefix, t):
        return f"{prefix} {label(t)}"

    if stats["oldest"]:
        lines += ["", "Oldest tasks:"] + [f"{label(t)} ({t['age_days']:g} days)" for t in stats["oldest"]]
    if stats["tasks"]:
        lines += ["", task_line("❤️ Easiest:", stats["easiest"][0]),
                  task_line("💔 Most hated:", stats["hated"][0])]
    longest = stats["procrastination"]["longest"]
    lines += ["", f"Longest procrastination: {longest} days" if longest
              else "Longest procrastination: none in this period 🎉"]
    return "\n".join(lines)


async def fetch_report(context, range_key):
    r = await client(context).get("/api/stats", params={"range": range_key})
    r.raise_for_status()
    return build_report(r.json(), range_key)


@authorized_only
async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = (context.args[0].lower() if context.args else "")
    arg = {"30d": "30", "90d": "90", "30days": "30", "90days": "90", "alltime": "all"}.get(arg, arg)
    if arg in RANGE_LABEL:
        await update.message.reply_text(await fetch_report(context, arg))
    else:
        await update.message.reply_text("Which period?", reply_markup=range_keyboard())


@authorized_only
async def report_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text(await fetch_report(context, query.data.split(":", 1)[1]),
                                      reply_markup=range_keyboard())
    except Exception:
        log.debug("Report message unchanged or could not be edited", exc_info=True)


@authorized_only
async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = sorted_tasks(await fetch_tasks(context))
    if not tasks:
        await update.message.reply_text("No tasks yet.")
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        f"{EMOJI[t['status']]} {label(t)}", callback_data=f"done:{t['id']}")] for t in tasks])
    await update.message.reply_text("Which task did you do? (any colour)", reply_markup=kb)


@authorized_only
async def done_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task_id = query.data.split(":", 1)[1]
    result = await refresh_task(context, task_id)
    if result is None:
        await query.answer("This task no longer exists", show_alert=True)
        return
    await query.answer("Done ✅")
    who = query.from_user.first_name or "someone"
    original = query.message.text or ""
    # Keep the other buttons on a multi-task message so several tasks can be ticked off.
    remaining = [row for row in (query.message.reply_markup.inline_keyboard if query.message.reply_markup else [])
                 if row[0].callback_data != query.data]
    is_picker = original.startswith("Which task")
    note = f"\n✅ {result['string']} – done by {who}"
    try:
        await query.edit_message_text(
            original + note,
            reply_markup=InlineKeyboardMarkup(remaining) if remaining and not is_picker else None)
    except Exception:
        log.exception("Could not edit message")
    # Task is now green; record it so a later yellow/red change notifies again.
    state = load_state()
    state["statuses"][task_id] = "green"
    save_state(state)


# ---------- scheduled jobs ----------
async def broadcast(context, text, keyboard=None):
    for chat_id in load_state()["chats"]:
        try:
            await context.bot.send_message(chat_id, text, reply_markup=keyboard)
        except Exception:
            log.exception("Could not send to chat %s", chat_id)


async def check_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        tasks = await fetch_tasks(context)
    except Exception as e:
        log.warning("Dashboard unreachable: %s", e)
        return

    state = load_state()
    previous = state["statuses"]
    current = {t["id"]: t["status"] for t in tasks}

    if not state["seeded"]:
        # First run: remember the current colours without flooding everyone.
        state.update(statuses=current, seeded=True)
        save_state(state)
        return

    for t in tasks:
        old = previous.get(t["id"])
        if t["status"] in ("yellow", "red") and old != t["status"]:
            icon = EMOJI[t["status"]]
            await broadcast(context, f"{icon} Task turned {t['status']}:\n{fmt_task(t, colour=False)}", done_keyboard([t]))

    state["statuses"] = current
    save_state(state)


async def digest(context: ContextTypes.DEFAULT_TYPE, header: str):
    try:
        tasks = await fetch_tasks(context)
    except Exception as e:
        log.warning("Dashboard unreachable: %s", e)
        return
    attention = [t for t in sorted_tasks(tasks) if t["status"] != "green"]
    if not attention:
        await broadcast(context, "Everything is green 🎉")
        return
    await broadcast(context, header + "\n\n" + "\n".join(fmt_task(t) for t in attention), done_keyboard(attention))


async def saturday_job(context: ContextTypes.DEFAULT_TYPE):
    await digest(context, "🧹 Saturday! Think about getting these back to OK for the week:")


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await digest(context, "☀️ Priorities for today:")


def parse_hhmm(value):
    hour, minute = value.split(":")
    return time(int(hour), int(minute), tzinfo=TZ)


async def post_init(app: Application):
    app.bot_data["http"] = httpx.AsyncClient(base_url=DASHBOARD_URL, timeout=10)


async def post_shutdown(app: Application):
    await app.bot_data["http"].aclose()


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("todo", todo_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CallbackQueryHandler(report_button, pattern=r"^report:(30|90|all)$"))
    app.add_handler(CallbackQueryHandler(done_button, pattern=r"^done:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_handler))

    app.job_queue.run_repeating(check_job, interval=CHECK_INTERVAL, first=10)
    # python-telegram-bot: days are 0-6 = Sunday-Saturday, so 6 is Saturday.
    app.job_queue.run_daily(saturday_job, parse_hhmm(SATURDAY_TIME), days=(6,))
    if DAILY_DIGEST_TIME:
        app.job_queue.run_daily(daily_job, parse_hhmm(DAILY_DIGEST_TIME))

    log.info("Bot started (dashboard=%s, tz=%s, saturday=%s)", DASHBOARD_URL, TZ, SATURDAY_TIME)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
