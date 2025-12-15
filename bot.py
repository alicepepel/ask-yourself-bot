import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# ====== Настройки ======
BOT_TOKEN = "6781609247:AAGEWMxkKtdWgOjRrMkMQRSJt-LdQBIg3Dg"
DEV_MODE = True
DEV_INTERVAL = 15

QUESTIONS = [
    "1. Какой подарок сделает тебя счастливым?",
    "2. Как можно поддержать тебя в трудный период?",
    "3. Ты можешь влюбиться в случайного прохожего?"
]
EMOJIS = ["😇", "😉", "🥹"]
SUBSCRIBERS = set()
DAILY_INTROS = [
    "Привет! Время ежедневного вопроса 🙃",
    "День без глубокомысленного вопроса прожит зря 😌 Поэтому...",
    "Привет! Очередной вопрос, который ты себе никогда не задавал 😈",
    "Я успел соскучиться за день 😇 Расскажи еще немного о себе?",
    "Привет! Нашел еще один интересный вопрос для тебя..."
]

# ====== Старые пользователи ======
OLD_USERS = [411024223]
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
    "Привет! Это Ask Yourself Bot 2.0 😉\n\n"
    "Я - генератор вопросов, которые ты можешь использовать для самопознания. "
    "В моей базе больше 200 вопросов, и они постоянно пополняются 😌\n\n"
    "Если мы уже знакомы - я получил новые полезные фичи: "
    "✨ Уникальные вопросы без повторов "
    "🎙 Отправка текста, голосовыми, фото и музыки"
)

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
    available = [q for q in QUESTIONS if q not in asked]
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
            await bot.send_message(chat_id=user_id, text=UPDATE_MESSAGE, reply_markup=start_buttons())
            old_users_notified.add(user_id)
        except Exception as e:
            print(f"Ошибка при отправке {user_id}: {e}")


import datetime
import pytz

SEND_HOURS = [12, 17, 22]  # часы по Москве для ежедневной рассылки

async def send_daily_question(user_id: int):
    # Получаем уже заданные вопросы
    user_state = DAILY_STATE.setdefault(user_id, {})
    asked = set(user_state.get("asked_questions", []))

    # Выбираем новый вопрос
    available = [q for q in QUESTIONS if q not in asked]
    if not available:
        # Если вопросы закончились, сбрасываем и уведомляем
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

    # Отправляем интро + вопрос
    intro = random.choice(DAILY_INTROS)
    await bot.send_message(user_id, intro)
    await bot.send_message(user_id, question)



async def daily_question_sender():
    moscow_tz = pytz.timezone("Europe/Moscow")
    last_sent_hour = None

    while True:
        if not SUBSCRIBERS:
            await asyncio.sleep(60)
            continue

        now = datetime.datetime.now(moscow_tz)
        current_hour = now.hour

        if current_hour in SEND_HOURS and last_sent_hour != current_hour:
            for user_id in list(SUBSCRIBERS):
                try:
                    await send_daily_question(user_id)  # теперь без state
                except Exception as e:
                    print(f"Ошибка отправки {user_id}: {e}")
            last_sent_hour = current_hour

        await asyncio.sleep(60)



# ====== Хендлер /start ======
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    SUBSCRIBERS.add(user_id)
    await message.answer(text=UPDATE_MESSAGE, reply_markup=start_buttons())

# ====== Хендлеры what_do / want_example ======
@dp.callback_query(lambda c: c.data == "what_do")
async def what_do_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    SUBSCRIBERS.add(user_id)  # 👈 подключаем к ежедневной рассылке

    await callback.message.answer(
        "💫 Ты можешь отвечать на вопросы в этом чате - получится что-то вроде личного дневника ) "
        "Здесь будут храниться все твои ответы - вдруг ты захочешь их перечитать и переосмыслить.\n\n"
        "💫 Также ты можешь анонимно отправить ответ в общий канал. "
        "Там можно читать ответы других пользователей, но нельзя их комментировать.\n\n"
        "Хочешь пример вопроса?",
        reply_markup=want_example_button()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "want_example")
async def want_example_callback(callback: types.CallbackQuery, state: FSMContext):
    question = await get_unique_question(state)
    if question is None:
        await callback.message.answer(
            "Вопросы закончились 😅 Но они регулярно пополняются! "
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
            "Вопросы закончились 😅 Но они регулярно пополняются! "
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
    if message.text:
        await state.update_data(user_answer=message.text, content_type="text")
    elif message.voice:
        await state.update_data(user_answer=message.voice.file_id, content_type="voice")
    elif message.photo:
        await state.update_data(user_answer=message.photo[-1].file_id, content_type="photo")
    elif message.video:
        await state.update_data(user_answer=message.video.file_id, content_type="video")
    else:
        await state.update_data(user_answer="[Неподдерживаемый формат]", content_type="text")
    await message.answer(
        "Начало личного дневника положено ) Теперь ты можешь поделиться ответом с другими юзерами ) "
        "Это анонимно и необязательно. Можешь оставить все ответы между нами 😌",
        reply_markup=share_buttons()
    )
    await state.set_state(Form.share_decision)


@dp.message(Form.waiting_for_answer_more)
async def handle_answer_more(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    if message.text:
        await state.update_data(user_answer=message.text, content_type="text")
    elif message.voice:
        await state.update_data(user_answer=message.voice.file_id, content_type="voice")
    elif message.photo:
        await state.update_data(user_answer=message.photo[-1].file_id, content_type="photo")
    elif message.video:
        await state.update_data(user_answer=message.video.file_id, content_type="video")
    else:
        await state.update_data(user_answer="[Неподдерживаемый формат]", content_type="text")
    await message.answer(
        "Хочешь поделиться этим ответом?",
        reply_markup=share_buttons_more()
    )
    await state.set_state(Form.share_decision)


# ====== Хендлеры share ======
async def send_to_channel(user_answer, content_type, current_question):
    caption_text = f"❓ {current_question}\n\n"
    if content_type == "text":
        await bot.send_message(chat_id="@pukmuk3000", text=f"{caption_text}{user_answer}")
    elif content_type == "voice":
        await bot.send_message(chat_id="@pukmuk3000", text=caption_text)
        await bot.send_voice(chat_id="@pukmuk3000", voice=user_answer)
    elif content_type == "photo":
        await bot.send_photo(chat_id="@pukmuk3000", photo=user_answer, caption=caption_text)
    elif content_type == "video":
        await bot.send_video(chat_id="@pukmuk3000", video=user_answer, caption=caption_text)

@dp.callback_query(lambda c: c.data in ["share_yes", "share_no", "share_yes_more", "share_no_more"])
async def share_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_answer = data.get("user_answer")
    content_type = data.get("content_type", "text")
    current_question = data.get("current_question", "Вопрос неизвестен")
    if callback.data in ["share_yes", "share_yes_more"]:
        await send_to_channel(user_answer, content_type, current_question)
        await callback.message.answer(
            "Спасибо! Твой ответ уже тут t.me/pukmuk3000" if "more" in callback.data else
            "Спасибо! Уверен, твой ответ будет интересен всем, кто на меня подписан 🤍 Найти его (и почитать других) можно в специальном канале t.me/pukmuk3000\n\nЖди следующий вопрос завтра! Если захочешь дополнительный (или просто другой) вопрос, используй команду /morequestions"
        )
    else:
        await callback.message.answer(
            "Договорились, пусть всё останется в тайне 🌘" if "more" in callback.data else
            "Что ж, на то он и Личный Дневник 😈\n\nЖди следующий вопрос завтра! Если захочешь дополнительный (или просто другой) вопрос, используй команду /morequestions"
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
        "Что-то не работает? Есть предложения, как сделать бот лучше? "
        "А может, хочешь поделиться вопросами? 😇 "
        "Мы обязательно добавим их в список!\n\n"
        "Напиши сообщение, и оно точно долетит до техподдержки 🥰"
    )

@dp.message()
async def handle_support_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in SUPPORT_STATE:
        return
    SUPPORT_STATE.remove(user_id)
    # пересылаем админу
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "📩 Новое сообщение в поддержку\n\n"
            f"👤 User ID: {user_id}\n"
            f"💬 Сообщение:\n{message.text or '[не текстовое сообщение]'}"
        )
    )
    await message.answer(
        "Спасибо! Админ прочитает в ближайшее время )"
    )


@dp.message()
async def handle_daily_answer(message: types.Message):
    user_id = message.from_user.id

    # Игнорируем, если юзер в поддержку
    if user_id in SUPPORT_STATE:
        return

    user_state = DAILY_STATE.get(user_id)
    if not user_state or not user_state.get("waiting_answer"):
        return

    # Игнорируем команды
    if message.text and message.text.startswith("/"):
        return

    # Фиксируем ответ
    user_state["last_answer"] = message.text if message.text else "[Неподдерживаемый формат]"
    user_state["waiting_answer"] = False

    # Сохраняем вопрос для share
    user_state["current_question_for_share"] = user_state.get("current_question", "Вопрос неизвестен")

    # Отправляем кнопки "Хочу! / Не хочу" **НЕ через FSM, а напрямую**
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
