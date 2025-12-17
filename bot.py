import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import StateFilter
import json
import os


# ====== Настройки ======
BOT_TOKEN = "6781609247:AAGEWMxkKtdWgOjRrMkMQRSJt-LdQBIg3Dg"
DEV_MODE = True
DEV_INTERVAL = 15

# ====== Автоподхват вопросов из JSON ======
QUESTIONS = []
QUESTIONS_MTIME = 0

def load_questions():
    global QUESTIONS, QUESTIONS_MTIME
    try:
        mtime = os.path.getmtime("questions.json")
        if mtime > QUESTIONS_MTIME:
            with open("questions.json", "r", encoding="utf-8") as f:
                QUESTIONS = json.load(f)
            QUESTIONS_MTIME = mtime
    except Exception as e:
        print(f"Ошибка загрузки questions.json: {e}")
    return QUESTIONS


EMOJIS = ["😇", "😉", "🥹"]
SUBSCRIBERS = set()
SUBSCRIBERS_FILE = "subscribers.json"

DAILY_INTROS = [
    "Привет! Время ежедневного вопроса 🙃",
    "День без глубокомысленного вопроса прожит зря 😌 Поэтому...",
    "Привет! Очередной вопрос, который ты себе никогда не задавал 😈",
    "Я успел соскучиться за день 😇 Расскажи еще немного о себе?",
    "Привет! Нашел еще один интересный вопрос для тебя...",
    "Лучшее время дня - то, которое можно уделить себе 🤭 Поболтаем?"
]

# ====== Старые пользователи ======
OLD_USERS = [411024223, 965001148]
old_users_notified = set()
# ====== Состояние ежедневных вопросов ======
# user_id -> {
#   "asked": set(),
#   "waiting_answer": bool,
#   "current_question": str
# }
DAILY_STATE = {}
SUPPORT_STATE = set()
# user_id, ожидающие сообщение в поддержку
ADMIN_ID = 411024223



UPDATE_MESSAGE = (
    "Привет! Это Ask Yourself Bot 2.0 😉 \n\n"
    "Я - генератор вопросов, которые ты можешь использовать для самопознания. "
    "В моей базе больше 200 вопросов, и они постоянно пополняются 😌 \n\n"
    "Если мы уже знакомы - я получил новые полезные фичи: \n"
    "✨ Уникальные вопросы без повторов \n"
    "🎙 Отправка текста, голосовыx, фото или музыки"
)

WELCOME_TEXT = ""
WELCOME_MTIME = 0

def load_welcome_text():
    global WELCOME_TEXT, WELCOME_MTIME
    try:
        mtime = os.path.getmtime("welcome_message.json")
        if mtime > WELCOME_MTIME:
            with open("welcome_message.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                WELCOME_TEXT = data.get("text", "")
            WELCOME_MTIME = mtime
    except Exception as e:
        print(f"Ошибка загрузки welcome_message.json: {e}")

    return WELCOME_TEXT


storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ====== FSM ======
class Form(StatesGroup):
    waiting_for_answer = State()
    waiting_for_share_decision = State()
    waiting_for_answer_more = State()
    share_decision = State()

# ====== Кнопки ======
def start_buttons():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Зачем все это нужно?", callback_data="what_do")]
        ]
    )

def want_example_button():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Хочу!", callback_data="want_example")]
        ]
    )

def share_buttons():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Хочу поделиться ответом с миром!", callback_data="share_yes")],
            [types.InlineKeyboardButton(text="Не буду делиться )", callback_data="share_no")]
        ]
    )

def share_buttons_more():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="Хочу! ☺", callback_data="share_yes_more"),
                types.InlineKeyboardButton(text="Не хочу 😈", callback_data="share_no_more")
            ]
        ]
    )

def thanks_button():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Спасибо!", callback_data="thanks")]
        ]
    )

# ====== Получение уникального вопроса ======
async def get_unique_question(state: FSMContext):
    data = await state.get_data()
    asked = set(data.get("asked_questions", []))
    questions = load_questions()
    available = [q for q in questions if q not in asked]
    if not available:
        return None
    question = random.choice(available)
    asked.add(question)
    await state.update_data(asked_questions=list(asked), current_question=question)
    return question


# ====== Однократное уведомление старых пользователей ======
async def notify_old_users():
    for user_id in OLD_USERS:
        if user_id in old_users_notified:
            continue
        try:
            welcome_text = load_welcome_text()
            # ✅ просто показываем кнопку, подписка только после клика
            await bot.send_message(chat_id=user_id, text=welcome_text, reply_markup=start_buttons())
            old_users_notified.add(user_id)
        except Exception as e:
            print(f"Ошибка при отправке {user_id}: {e}")


import datetime
import pytz

SEND_HOURS = [12, 17, 23]  # часы по Москве для ежедневной рассылки

def load_subscribers_stats():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return {}
    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_subscriber(user_id: int):
    data = load_subscribers_stats()

    now = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
    data[str(user_id)] = {
        "subscribed_date": now.strftime("%Y-%m-%d"),
        "subscribed_time": now.strftime("%H:%M:%S")
    }

    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ====== Вспомогательные функции ======
def remove_subscriber(user_id: int):
    """Удаляем пользователя из json и множества SUBSCRIBERS"""
    data = load_subscribers_stats()
    if str(user_id) in data:
        del data[str(user_id)]
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    SUBSCRIBERS.discard(user_id)


async def safe_send_message(user_id: int, *args, **kwargs):
    """
    Безопасная отправка сообщения пользователю.
    Если бот заблокирован или чат удалён — удаляем пользователя из подписчиков.
    """
    try:
        await bot.send_message(user_id, *args, **kwargs)
    except Exception as e:
        # Telegram возвращает Forbidden если бот заблокирован или чат удалён
        if "Forbidden" in str(e) or "chat not found" in str(e):
            print(f"Удаляем отписавшегося пользователя {user_id}")
            remove_subscriber(user_id)
        else:
            print(f"Ошибка отправки {user_id}: {e}")


async def send_daily_question(user_id: int):
    # Получаем уже заданные вопросы
    user_state = DAILY_STATE.setdefault(user_id, {})

    now = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
    current_hour = now.hour

    # 👇 если пользователь подписался в этот час — пропускаем ОДИН РАЗ
    skip_hour = user_state.get("skip_daily_hour")
    if skip_hour == current_hour:
        print(f"[DEBUG][DAILY] skip first daily for user {user_id} at hour {current_hour}")
        user_state.pop("skip_daily_hour", None)
        return

    asked = set(user_state.get("asked_questions", []))

    state = dp.fsm.get_context(bot=bot, user_id=user_id, chat_id=user_id)

    # Выбираем новый вопрос
    questions = load_questions()
    available = [q for q in questions if q not in asked]
    if not available:
        user_state["asked_questions"] = []
        await bot.send_message(
            user_id,
            "Ты прошёл все вопросы! 🎉 Начнём новый круг — используй /start"
        )
        return

    question = random.choice(available)
    asked.add(question)

    user_state["asked_questions"] = list(asked)
    user_state["current_question"] = question
    user_state["waiting_answer"] = True
    # 🔧 синхронизация FSM
    await state.update_data(
        current_question=question,
        user_answer=None,
        content_type=None
    )

    intro = random.choice(DAILY_INTROS)
    await safe_send_message(user_id, intro)
    await safe_send_message(user_id, question)


async def daily_question_sender():
    moscow_tz = pytz.timezone("Europe/Moscow")
    last_sent_key = None  # (date, hour)

    while True:
        if not SUBSCRIBERS:
            await asyncio.sleep(60)
            continue

        now = datetime.datetime.now(moscow_tz)
        current_hour = now.hour

        send_key = (now.date(), current_hour)

        if current_hour in SEND_HOURS and last_sent_key != send_key:
            for user_id in list(SUBSCRIBERS):
                try:
                    await send_daily_question(user_id)
                except Exception as e:
                    print(f"Ошибка отправки {user_id}: {e}")

            last_sent_key = send_key

        await asyncio.sleep(60)



# ====== Хендлер /start ======
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    # ❌ больше не добавляем в SUBSCRIBERS
    welcome_text = load_welcome_text()
    await message.answer(text=welcome_text, reply_markup=start_buttons())

# ====== Хендлеры what_do / want_example ======
@dp.callback_query(lambda c: c.data == "what_do")
async def what_do_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    # ✅ только здесь подписка после нажатия кнопки
    SUBSCRIBERS.add(user_id)
    save_subscriber(user_id)

    # сохраняем час подписки, чтобы пропустить рассылку в этот час
    now = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
    DAILY_STATE.setdefault(user_id, {})
    DAILY_STATE[user_id]["skip_daily_hour"] = now.hour

    await callback.message.answer(
        "💫 Ты можешь отвечать на вопросы в этом чате - получится что-то вроде личного дневника ✍️ "
        "Здесь будут храниться все твои ответы - вдруг ты захочешь их перечитать и переосмыслить. \n\n"
        "💫 Также ты можешь анонимно отправить ответ в общий канал t.me/pukmuk3000. "
        "Там можно читать ответы других пользователей, но нельзя их комментировать 👀 \n\n"
        "Хочешь пример вопроса?",
        reply_markup=want_example_button()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "want_example")
async def want_example_callback(callback: types.CallbackQuery, state: FSMContext):
    question = await get_unique_question(state)
    if question is None:
        await callback.message.answer(
            "Вопросы закончились 😅 Но они регулярно пополняются! \n"
            "А пока можно начать заново, нажав команду /start"
        )
        return
    await callback.message.answer(question)
    await state.set_state(Form.waiting_for_answer)


# ====== Команда /morequestions ======
@dp.message(Command("morequestions"))
async def more_questions(message: types.Message, state: FSMContext):
    question = await get_unique_question(state)
    if question is None:
        await message.answer(
            "Вопросы закончились 😅 Но они регулярно пополняются! \n"
            "А пока можно начать заново, нажав команду /start"
        )
        return
    await message.answer(question)
    await state.set_state(Form.waiting_for_answer_more)



# ====== Обработка ответов ======
@dp.message(Form.waiting_for_answer)
async def handle_answer_standard(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return

    user_data = {}

    # текст
    if message.text:
        user_data["text"] = message.text
    if message.caption:
        user_data["text"] = user_data.get("text", "") + ("\n" if "text" in user_data else "") + message.caption

    # фото
    if message.photo:
        user_data["media_id"] = message.photo[-1].file_id
        user_data["media_type"] = "photo"

    # видео
    elif message.video:
        user_data["media_id"] = message.video.file_id
        user_data["media_type"] = "video"

    # аудио (mp3)
    elif message.audio:
        user_data["media_id"] = message.audio.file_id
        user_data["media_type"] = "mp3"

    # документ (mp3/mp4)
    elif message.document:
        file_name = message.document.file_name or ""
        mime = message.document.mime_type or ""

        if file_name.lower().endswith(".mp3") or mime in ["audio/mpeg", "audio/mp3"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp3"
        elif file_name.lower().endswith(".mp4") or mime in ["video/mp4", "audio/mp4"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp4"
        else:
            if not user_data.get("text"):
                user_data["text"] = "[Неподдерживаемый формат]"

    # голосовое
    elif message.voice:
        user_data["media_id"] = message.voice.file_id
        user_data["media_type"] = "voice"

    # DEBUG
    print(f"[DEBUG] user_data={user_data}")

    # определяем content_type
    if "media_id" in user_data and "text" in user_data:
        content_type = "combined"
    elif "media_id" in user_data:
        content_type = user_data["media_type"]
    else:
        content_type = "text"

    # сохраняем в FSM
    await state.update_data(
        user_answer=user_data if user_data else {"text": "[Неподдерживаемый формат]"},
        content_type=content_type
    )

    await message.answer(
        "Начало личного дневника положено ) Теперь ты можешь поделиться ответом с другими юзерами ) \n\n"
        "Это анонимно и необязательно. Можешь оставить все ответы между нами 😌",
        reply_markup=share_buttons()
    )
    await state.set_state(Form.share_decision)


@dp.message(Form.waiting_for_answer_more)
async def handle_answer_more(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return

    user_data = {}

    # текст
    if message.text:
        user_data["text"] = message.text
    if message.caption:
        user_data["text"] = user_data.get("text", "") + ("\n" if "text" in user_data else "") + message.caption

    # фото
    if message.photo:
        user_data["media_id"] = message.photo[-1].file_id
        user_data["media_type"] = "photo"

    # видео
    elif message.video:
        user_data["media_id"] = message.video.file_id
        user_data["media_type"] = "video"

    # аудио (mp3)
    elif message.audio:
        user_data["media_id"] = message.audio.file_id
        user_data["media_type"] = "mp3"

    # документ (mp3/mp4)
    elif message.document:
        file_name = message.document.file_name or ""
        mime = message.document.mime_type or ""

        if file_name.lower().endswith(".mp3") or mime in ["audio/mpeg", "audio/mp3"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp3"
        elif file_name.lower().endswith(".mp4") or mime in ["video/mp4", "audio/mp4"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp4"
        else:
            if not user_data.get("text"):
                user_data["text"] = "[Неподдерживаемый формат]"

    # голосовое
    elif message.voice:
        user_data["media_id"] = message.voice.file_id
        user_data["media_type"] = "voice"

    # DEBUG
    print(f"[DEBUG] user_data={user_data}")

    # определяем content_type
    if "media_id" in user_data and "text" in user_data:
        content_type = "combined"
    elif "media_id" in user_data:
        content_type = user_data["media_type"]
    else:
        content_type = "text"

    # сохраняем в FSM
    await state.update_data(
        user_answer=user_data if user_data else {"text": "[Неподдерживаемый формат]"},
        content_type=content_type
    )

    await message.answer(
        "Хочешь поделиться этим ответом?",
        reply_markup=share_buttons_more()
    )
    await state.set_state(Form.share_decision)


async def send_to_channel(user_answer, content_type, current_question):
    if not isinstance(user_answer, dict):
        print(f"[DEBUG][SEND] user_answer invalid: {user_answer}")
        user_answer = {}

    caption_text = f"❓ {current_question}"
    chat_id = "@pukmuk3000"

    # ===== НОРМАЛИЗАЦИЯ =====
    # если пришла строка (ежедневные вопросы)
    if isinstance(user_answer, str):
        if content_type == "text":
            user_answer = {"text": user_answer}
        else:
            user_answer = {
                "media_id": user_answer,
                "media_type": content_type
            }

    # ---- только текст ----
    if content_type == "text":
        text = user_answer.get("text", "")
        await bot.send_message(
            chat_id=chat_id,
            text=f"{caption_text}\n\n{text}" if text else caption_text
        )
        return

    # ---- голосовое ----
    if content_type == "voice":
        await bot.send_message(chat_id=chat_id, text=caption_text)
        await bot.send_voice(chat_id=chat_id, voice=user_answer["media_id"])
        return

    media_id = user_answer.get("media_id")
    media_type = user_answer.get("media_type")
    text = user_answer.get("text", "")

    # ---- медиа ----
    if media_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=media_id, caption=caption_text)

    elif media_type == "video":
        await bot.send_video(chat_id=chat_id, video=media_id, caption=caption_text)

    elif media_type == "mp3":
        await bot.send_audio(
            chat_id=chat_id,
            audio=media_id,
            caption=caption_text
        )

    elif media_type == "mp4":
        await bot.send_document(
            chat_id=chat_id,
            document=media_id,
            caption=caption_text
        )

    # ---- текст для комбинированных ----
    if text:
        await bot.send_message(chat_id=chat_id, text=text)



@dp.callback_query(lambda c: c.data in ["share_yes", "share_no", "share_yes_more", "share_no_more"])
async def share_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    print(f"[DEBUG][SHARE] FSM data = {data}")
    user_answer = data.get("user_answer") or {}
    content_type = data.get("content_type", "text")
    current_question = data.get("current_question", "Вопрос неизвестен")

    if callback.data in ["share_yes", "share_yes_more"]:
        await send_to_channel(user_answer, content_type, current_question)
        await callback.message.answer(
            "Спасибо! Твой ответ уже тут t.me/pukmuk3000" if "more" in callback.data else
            "Спасибо! Уверен, твой ответ будет интересен всем, кто на меня подписан 🤍 \n\nНайти его (и почитать других) можно в специальном канале t.me/pukmuk3000 💬 \n\nЖди следующий вопрос завтра! Если захочешь дополнительный (или просто другой) вопрос, используй команду /morequestions"
        )
    else:
        await callback.message.answer(
            "Договорились, пусть всё останется в тайне 🌘" if "more" in callback.data else
            "Что ж, на то он и Личный Дневник 😈 \n\nЖди следующий вопрос завтра! Если захочешь дополнительный (или просто другой) вопрос, используй команду /morequestions"
        )
    await state.set_state(None)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "thanks")
async def thanks_callback(callback: types.CallbackQuery):
    emoji = random.choice(EMOJIS)
    await callback.message.answer(emoji)
    await callback.answer()

@dp.message(Command("support"))
async def support_command(message: types.Message):
    user_id = message.from_user.id
    SUPPORT_STATE.add(user_id)

    await message.answer(
        "Что-то не работает? Есть предложения, как сделать бот лучше? \n"
        "А может, хочешь поделиться вопросами? 😇 \n"
        "Мы обязательно добавим их в список! \n\n"
        "Напиши сообщение, оно точно долетит до техподдержки 🥰"
    )

@dp.message(StateFilter(None))
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    # Сначала проверяем поддержку
    if user_id in SUPPORT_STATE:
        SUPPORT_STATE.remove(user_id)

        # Текст — как было
        if message.text:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📩 Новое сообщение в поддержку\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"💬 Сообщение:\n{message.text}"
                )
            )

        # Голос
        elif message.voice:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📩 Новое сообщение в поддержку\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"💬 Сообщение:\n[не текстовое сообщение]"
                )
            )
            await bot.send_voice(
                chat_id=ADMIN_ID,
                voice=message.voice.file_id
            )

        # Фото
        elif message.photo:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📩 Новое сообщение в поддержку\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"💬 Сообщение:\n[не текстовое сообщение]"
                )
            )
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id
            )

        # Видео
        elif message.video:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📩 Новое сообщение в поддержку\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"💬 Сообщение:\n[не текстовое сообщение]"
                )
            )
            await bot.send_video(
                chat_id=ADMIN_ID,
                video=message.video.file_id
            )

        await message.answer(
            "Спасибо! Админ прочитает в ближайшее время )"
        )
        return

    # Проверяем ежедневный вопрос
    user_state = DAILY_STATE.get(user_id)
    if not user_state or not user_state.get("waiting_answer"):
        return

    # Игнорируем команды
    if message.text and message.text.startswith("/"):
        return

    # Фиксируем ответ
    user_state["last_answer"] = message.text if message.text else "[Неподдерживаемый формат]"
    user_state["waiting_answer"] = False

    # 🔧 КЛЮЧЕВОЕ: сохраняем ответ в FSM
    state = dp.fsm.get_context(bot=bot, user_id=user_id, chat_id=user_id)

    user_data = {}

    # текст / caption
    if message.text:
        user_data["text"] = message.text
    if message.caption:
        user_data["text"] = user_data.get("text", "") + (
            "\n" if "text" in user_data else ""
        ) + message.caption

    # аудио mp3
    if message.audio:
        user_data["media_id"] = message.audio.file_id
        user_data["media_type"] = "mp3"

    # документ mp3 / mp4
    elif message.document:
        file_name = message.document.file_name or ""
        mime = message.document.mime_type or ""

        if file_name.lower().endswith(".mp3") or mime in ["audio/mpeg", "audio/mp3"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp3"
        elif file_name.lower().endswith(".mp4") or mime in ["video/mp4", "audio/mp4"]:
            user_data["media_id"] = message.document.file_id
            user_data["media_type"] = "mp4"

    # фото
    elif message.photo:
        user_data["media_id"] = message.photo[-1].file_id
        user_data["media_type"] = "photo"

    # видео
    elif message.video:
        user_data["media_id"] = message.video.file_id
        user_data["media_type"] = "video"

    # голос
    elif message.voice:
        user_data["media_id"] = message.voice.file_id
        user_data["media_type"] = "voice"

    # DEBUG
    print(f"[DEBUG][DAILY] user_data={user_data}")

    # content_type
    if "media_id" in user_data and "text" in user_data:
        content_type = "combined"
    elif "media_id" in user_data:
        content_type = user_data["media_type"]
    else:
        content_type = "text"

    await state.update_data(
        user_answer=user_data if user_data else {"text": "[Неподдерживаемый формат]"},
        content_type=content_type
    )

    # Отправляем кнопки "Хочу! / Не хочу"
    await message.answer(
        "Хочешь поделиться этим ответом?",
        reply_markup=share_buttons_more()
    )


# ====== Запуск бота ======
async def main():
    print("Бот запущен...")
    await notify_old_users()
    # создаём таск после небольшой паузы
    asyncio.create_task(daily_question_sender())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
