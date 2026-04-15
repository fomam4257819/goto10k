import telebot
from telebot import types
import psycopg2

# =========================
# 🔐 НАСТРОЙКИ
# =========================
user_states = {}
trainer_data = {}
user_form = {}  # ← ДОБАВЛЕНО
TOKEN = "ТВОЙ_ТОКЕН_БОТА"
ADMIN_ID = 123456789  # сюда вставишь свой Telegram ID

DB_CONFIG = {
    "dbname": "ТВОЯ_БД",
    "user": "ТВОЙ_ЮЗЕР",
    "password": "ТВОЙ_ПАРОЛЬ",
    "host": "ТВОЙ_ХОСТ",
    "port": "5432"
}

bot = telebot.TeleBot(TOKEN)

# =========================
# 🗄️ ПОДКЛЮЧЕНИЕ К БД
# =========================

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# =========================
# 🏁 СТАРТ
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Выбрать тренера", "Связаться с администратором")

    bot.send_message(
        message.chat.id,
        "Добро пожаловать в шахматную школу ♟️\nВыберите действие:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "Выбрать тренера")
def choose_trainer_start(message):
    user_states[message.chat.id] = "waiting_phone"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("Отправить номер", request_contact=True)
    markup.add(btn)

    bot.send_message(message.chat.id, "Отп��авь номер телефона:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Связаться с администратором")
def contact_admin_start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Завершить чат")

    bot.send_message(
        message.chat.id,
        "Ожидайте ответа администратора...",
        reply_markup=markup
    )

# =========================
# 👤 ПОЛУЧЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ
# =========================

@bot.message_handler(content_types=['contact'])
def get_phone(message):
    if user_states.get(message.chat.id) != "waiting_phone":
        return

    user_form[message.chat.id] = {}
    user_form[message.chat.id]["phone"] = message.contact.phone_number

    user_states[message.chat.id] = "waiting_user_name"
    bot.send_message(message.chat.id, "Введи своё имя:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_user_name")
def get_user_name(message):
    user_form[message.chat.id]["name"] = message.text

    user_states[message.chat.id] = "waiting_level"
    bot.send_message(message.chat.id, "Опиши уровень игры:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_level")
def get_level(message):
    user_form[message.chat.id]["level"] = message.text

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM trainers")
        trainers = cursor.fetchall()

        cursor.close()
        conn.close()

        if not trainers:
            bot.send_message(message.chat.id, "Нет доступных тренеров")
            return

        markup = types.InlineKeyboardMarkup()

        for t in trainers:
            btn = types.InlineKeyboardButton(
                text=t[1],
                callback_data=f"choose_{t[0]}"
            )
            markup.add(btn)

        bot.send_message(message.chat.id, "Выбери тренера:", reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("choose_"))
def send_request_to_trainer(call):
    trainer_id = call.data.split("_")[1]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT username, name FROM trainers WHERE id = %s", (trainer_id,))
        trainer = cursor.fetchone()

        cursor.close()
        conn.close()

        if not trainer:
            bot.answer_callback_query(call.id, "Ошибка")
            return

        username, trainer_name = trainer
        data = user_form.get(call.message.chat.id)

        if not data:
            bot.answer_callback_query(call.id, "Ошибка данных")
            return

        text = f"""
Вас выбрали как тренера!

Имя: {data['name']}
Телефон: {data['phone']}
Уровень: {data['level']}
        """

        bot.send_message(username, text)
        bot.answer_callback_query(call.id, "Заявка отправлена ✅")

        # очистка данных
        user_states.pop(call.message.chat.id, None)
        user_form.pop(call.message.chat.id, None)

    except Exception as e:
        bot.answer_callback_query(call.id, "Ошибка")
        bot.send_message(call.message.chat.id, f"Ошибка: {e}")

# =========================
# 👨‍💼 АДМИНИСТРАТОРСКАЯ ПАНЕЛЬ
# =========================

@bot.message_handler(func=lambda message: message.text == "Edit")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Нет доступа")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Добавить пользователя", "Удалить пользователя")

    bot.send_message(message.chat.id, "Админ-панель:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Добавить пользователя")
def add_trainer_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    user_states[message.chat.id] = "waiting_username"
    bot.send_message(message.chat.id, "Введи @username тренера:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_username")
def get_username(message):
    trainer_data[message.chat.id] = {}
    trainer_data[message.chat.id]["username"] = message.text

    user_states[message.chat.id] = "waiting_name"
    bot.send_message(message.chat.id, "Введи имя тренера:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_name")
def get_name(message):
    trainer_data[message.chat.id]["name"] = message.text

    user_states[message.chat.id] = "waiting_description"
    bot.send_message(message.chat.id, "Введи описание тренера:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_description")
def get_description(message):
    trainer_data[message.chat.id]["description"] = message.text

    data = trainer_data[message.chat.id]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO trainers (username, name, description) VALUES (%s, %s, %s)",
            (data["username"], data["name"], data["description"])
        )

        conn.commit()
        cursor.close()
        conn.close()

        bot.send_message(message.chat.id, "Тренер добавлен ✅")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

    # очистка состояния
    user_states.pop(message.chat.id, None)
    trainer_data.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: message.text == "Удалить пользователя")
def delete_trainer_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM trainers")
        trainers = cursor.fetchall()

        cursor.close()
        conn.close()

        if not trainers:
            bot.send_message(message.chat.id, "Список пуст")
            return

        markup = types.InlineKeyboardMarkup()

        for trainer in trainers:
            trainer_id, name = trainer
            btn = types.InlineKeyboardButton(
                text=name,
                callback_data=f"delete_{trainer_id}"
            )
            markup.add(btn)

        bot.send_message(message.chat.id, "Выбери тренера для удаления:", reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_trainer(call):
    if call.from_user.id != ADMIN_ID:
        return

    trainer_id = call.data.split("_")[1]
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM trainers WHERE id = %s", (trainer_id,))
        conn.commit()

        cursor.close()
        conn.close()

        bot.answer_callback_query(call.id, "Удалено ✅")
        bot.edit_message_text(
            "Тренер удалён",
            call.message.chat.id,
            call.message.message_id
        )

    except Exception as e:
        bot.answer_callback_query(call.id, "Ошибка")
        bot.send_message(call.message.chat.id, f"Ошибка: {e}")

# =========================
# 🚀 ЗАПУСК
# =========================
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
