import json
import os
import random
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

DB = Path(__file__).with_name("tasks.db")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
WORDS = {"واحد":"1","واحدة":"1","اتنين":"2","اثنين":"2","تلاتة":"3","ثلاثة":"3","اربعة":"4","أربعة":"4","خمسة":"5","خمسه":"5","ستة":"6","سبعة":"7","ثمانية":"8","تمانية":"8","تسعة":"9","عشرة":"10","عشره":"10","حداشر":"11","اتناشر":"12"}
OPENERS = ("يلا يا بطل، وقت الجد وصل.", "المهمة بتنادي عليك، متخليشها تستنى.", "خمس دقائق بداية أحسن من تأجيل كبير.", "سيب أي تشتيت وابدأ أول خطوة.", "أنت وعدت نفسك بالمهمة دي، يلا نفذ.", "الإنجاز مش محتاج مزاج، محتاج قرار.", "النسخة الأقوى منك مستنياك تبدأ.", "هدفك مش بعيد، بس عايز الحركة دي.", "مفيش هروب النهارده، ابدأ دلوقتي.", "التنبيه وصل، والباقي عليك يا نجم.", "قوم اعملها، وبعدها اشكر نفسك.", "العادة بتتبني دلوقتي، مش بعدين.", "متفاوضش نفسك كتير، ابدأ وبس.", "الدقيقة دي ممكن تكون أحسن قرار في يومك.", "مفيش حد هيعملها مكانك، يلا بينا.", "يلا نكسب الجولة دي قبل ما الوقت يسبقنا.", "خد نفس، افتح المهمة، وابدأ أول جزء.", "المهمة الصغيرة دي بتبني فرق كبير.", "الكسل بيحب كلمة بعدين، وأنت قول له لأ.", "تركيز بسيط الآن، وفخر كبير بعدين.", "مش لازم تعملها كاملة، المهم تبدأها.", "ده وقتك تثبت إن كلامك مع نفسك له قيمة.", "بطل تحضير في دماغك، وابدأ تنفيذ بإيدك.", "النجاح بيحب الناس اللي بتقوم وقت التنبيه.")
FOLLOW = (("عدت دقيقة ولسه مستني كلمة تم. ابدأ حتى لو بخطوة صغيرة.", "فينك يا بطل؟ دقيقة كاملة كفاية تفكير. افتح المهمة دلوقتي.", "أنا مش ناسي، والمهمة كمان مش هتختفي. يلا ابدأ."), ("بصراحة كده، المهمة مستنياك وأنت سايبها. قوم يا نجم.", "مفيش تسويف النهارده. افتح المهمة واكتب تم لما تبدأ.", "هدفك أهم من السوشيال دقيقة واحدة. ركز وابدأ."), ("ده التنبيه الأخير قبل ما أعتبرك بتتهرب! ابدأ حالاً.", "بطل تفاوض، بطل تأجيل، نفذ أول خطوة الآن.", "مستني تم منك. خليك قد وعدك لنفسك."))


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def setup():
    with db() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, hour INTEGER, minute INTEGER, last_sent TEXT);
        CREATE TABLE IF NOT EXISTS reminders (task_id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, phase INTEGER, next_at TEXT);
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);""")


def api(token, method, payload):
    try:
        request = Request(f"https://api.telegram.org/bot{token}/{method}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
        return data.get("result") if data.get("ok") else None
    except Exception:
        return None


def send(token, chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup: data["reply_markup"] = markup
    return api(token, "sendMessage", data)


def parse_task(raw):
    if "|" in raw:
        clock, task = (part.strip() for part in raw.split("|", 1))
    else:
        text = raw.translate(DIGITS).lower()
        for word, number in WORDS.items(): text = re.sub(rf"\b{word}\b", number, text)
        found = re.search(r"(?P<prefix>الساعة|الساعه|at)?\s*(?P<hour>\d{1,2})(?:\s*(?:و|:)?\s*(?P<minute>\d{1,2}|ربع|نص|نصف))?\s*(?P<period>الفجر|صباحا?|صباحاً|مساءا?|مساءً|بالليل|بليل|ليلا?|ليلًا)?", text)
        if not found or not any((found["prefix"], found["minute"], found["period"])): raise ValueError
        hour = int(found["hour"])
        minute_value = found["minute"] or "0"
        minute_words = {"ربع": 15, "نص": 30, "نصف": 30}
        minute = minute_words[minute_value] if minute_value in minute_words else int(minute_value)
        period = found["period"] or ""
        if period in {"مساء", "مساءا", "مساءً", "بالليل", "بليل", "ليل", "ليلا", "ليلًا"} and hour < 12: hour += 12
        if period in {"الفجر", "صباح", "صباحا", "صباحاً"} and hour == 12: hour = 0
        clock, task = f"{hour}:{minute}", (text[:found.start()] + text[found.end():]).strip(" -،.")
    try:
        hour, minute = (int(value) for value in clock.split(":", 1))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59 or not task: raise ValueError
        return hour, minute, task
    except (ValueError, TypeError): raise ValueError from None


def instructions():
    return "أهلاً! أنا بوت مهامك اليومية 🤝\n\nأضف مهمة بوقت 24 ساعة:\n/add 19:00 | مذاكرة الإنجليزي\n\nأو اكتب: هاذاكر الإنجليزي الساعة 7 مساءً\n\nعند الموعد أذكرك. لو لم تكتب «تم»، أتابع معك كل دقيقة بثلاث رسائل تشجيع أقوى.\n\nالأوامر:\n/tasks عرض المهام وحذفها\n/delete 1 حذف مهمة\nتم إيقاف المتابعات\n/help المساعدة"


def add_task(token, chat_id, text):
    try: hour, minute, task = parse_task(text)
    except ValueError:
        send(token, chat_id, "اكتب هكذا:\n/add 19:00 | مذاكرة الإنجليزي\nأو: هاذاكر الإنجليزي الساعة 7 مساءً")
        return
    with db() as c: c.execute("INSERT INTO tasks (chat_id, text, hour, minute) VALUES (?, ?, ?, ?)", (chat_id, task, hour, minute))
    send(token, chat_id, f"تم الحفظ ✅\nسأذكرك يومياً الساعة {hour:02d}:{minute:02d}\nالمهمة: {task}")


def tasks_list(token, chat_id):
    with db() as c: tasks = c.execute("SELECT * FROM tasks WHERE chat_id=? ORDER BY hour, minute", (chat_id,)).fetchall()
    if not tasks:
        send(token, chat_id, "ليس لديك مهام حالياً. أضف واحدة مثل: /add 19:00 | مذاكرة")
        return
    lines, buttons = ["📋 مهامك اليومية:"], []
    for task in tasks:
        lines.append(f"{task['id']}. {task['hour']:02d}:{task['minute']:02d} - {task['text']}")
        buttons.append([{"text": f"حذف {task['hour']:02d}:{task['minute']:02d}", "callback_data": f"delete:{task['id']}"}])
    send(token, chat_id, "\n".join(lines), {"inline_keyboard": buttons})


def delete_task(chat_id, task_id):
    with db() as c:
        task = c.execute("SELECT * FROM tasks WHERE id=? AND chat_id=?", (task_id, chat_id)).fetchone()
        if task:
            c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            c.execute("DELETE FROM reminders WHERE task_id=?", (task_id,))
    return task


def handle_update(token, update):
    callback = update.get("callback_query")
    if callback:
        api(token, "answerCallbackQuery", {"callback_query_id": callback["id"]})
        chat, data = callback["message"]["chat"]["id"], callback.get("data", "")
        if data.startswith("delete:") and data[7:].isdigit():
            task = delete_task(chat, int(data[7:]))
            api(token, "editMessageText", {"chat_id": chat, "message_id": callback["message"]["message_id"], "text": "تم حذف المهمة 🗑️" if task else "المهمة غير موجودة."})
        return
    message = update.get("message")
    if not message or "text" not in message: return
    chat, text = message["chat"]["id"], message["text"].strip()
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    if command in {"/start", "/help"}: send(token, chat, instructions())
    elif command == "/tasks": tasks_list(token, chat)
    elif command == "/delete" and len(text.split()) == 2 and text.split()[1].isdigit(): send(token, chat, "تم حذف المهمة 🗑️" if delete_task(chat, int(text.split()[1])) else "لم أجد هذه المهمة.")
    elif command == "/add": add_task(token, chat, text.partition(" ")[2])
    elif re.fullmatch(r"\s*(تم|خلصت|أنجزت|انجزت|خلصنا)\s*", text):
        with db() as c: c.execute("DELETE FROM reminders WHERE chat_id=?", (chat,))
        send(token, chat, "عاش! سجلت إنك خلصت، مش هفكرك تاني بالمهام الحالية 👏")
    else: add_task(token, chat, text)


def schedule(token, zone):
    now, today = datetime.now(zone), datetime.now(zone).date().isoformat()
    with db() as c: due = c.execute("SELECT * FROM tasks WHERE last_sent IS NULL OR last_sent != ?", (today,)).fetchall()
    for task in due:
        if (task["hour"], task["minute"]) > (now.hour, now.minute): continue
        if send(token, task["chat_id"], f"⏰ {random.choice(OPENERS)}\n\nمهمتك الآن: {task['text']}\n\nاكتب «تم» بعد الإنجاز."):
            with db() as c:
                c.execute("UPDATE tasks SET last_sent=? WHERE id=?", (today, task["id"]))
                c.execute("INSERT OR REPLACE INTO reminders VALUES (?, ?, ?, ?, ?)", (task["id"], task["chat_id"], task["text"], 0, (now + timedelta(minutes=1)).isoformat()))
    with db() as c: reminders = c.execute("SELECT * FROM reminders WHERE next_at <= ?", (now.isoformat(),)).fetchall()
    for reminder in reminders:
        phase = reminder["phase"]
        send(token, reminder["chat_id"], f"⏰ {random.choice(FOLLOW[phase])}\n\nالمهمة: {reminder['text']}\nاكتب «تم» عندما تنجز.")
        with db() as c:
            if phase + 1 == len(FOLLOW): c.execute("DELETE FROM reminders WHERE task_id=?", (reminder["task_id"],))
            else: c.execute("UPDATE reminders SET phase=?, next_at=? WHERE task_id=?", (phase + 1, (now + timedelta(minutes=1)).isoformat(), reminder["task_id"]))


def worker(token, timezone_name):
    zone, offset = ZoneInfo(timezone_name), 0
    setup()
    with db() as c:
        saved = c.execute("SELECT value FROM state WHERE key='offset'").fetchone()
    if saved: offset = int(saved["value"])
    while True:
        schedule(token, zone)
        updates = api(token, "getUpdates", {"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]}) or []
        for update in updates:
            offset = update["update_id"] + 1
            handle_update(token, update)
            with db() as c: c.execute("INSERT OR REPLACE INTO state VALUES ('offset', ?)", (str(offset),))
        time.sleep(2)


@st.cache_resource
def start_bot(token, timezone_name):
    thread = threading.Thread(target=worker, args=(token, timezone_name), daemon=True)
    thread.start()
    return thread


st.set_page_config(page_title="بوت مهامي", page_icon="⏰")
st.title("بوت مهامي على تيليجرام")
st.write("تذكيرات يومية، رسائل متنوعة، ومتابعة تلقائية عند عدم كتابة «تم».")
token = os.getenv("TELEGRAM_BOT_TOKEN", "") or st.secrets.get("TELEGRAM_BOT_TOKEN", "")
timezone = os.getenv("BOT_TIMEZONE", "") or st.secrets.get("BOT_TIMEZONE", "Africa/Cairo")
if token:
    start_bot(token, timezone)
    st.success("البوت يعمل. افتح تيليجرام وأرسل له /start")
    st.code("/add 19:00 | مذاكرة الإنجليزي\n/tasks\nتم", language="text")
else:
    st.warning("أضف التوكن في Streamlit Secrets ثم أعد تشغيل التطبيق.")
    st.code('TELEGRAM_BOT_TOKEN = "8622116695:AAHUEnKjQ789MwyVrMIDWY0s6UbnLfHHiTw"\nBOT_TIMEZONE = "Africa/Cairo"', language="toml")
