import telebot
from telebot import types
import psycopg2
import os
from datetime import datetime

# =========================
# 🔐 НАСТРОЙКИ
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "chess_school"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

bot = telebot.TeleBot(TOKEN)

# =========================
# 📊 СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ
# =========================
user_states = {}  # Отслеживание статуса пользователя
user_form = {}    # Форма данных пользователя
trainer_data = {} # Данные тренера при добавлении
admin_chats = {}  # {user_id: admin_id} - активные чаты с админом

# =========================
# 🗄️ ПОДКЛЮЧЕНИЕ К БД
# =========================

def get_db_connection():
    """Подключение к БД"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

def init_db():
    """Инициализация таблиц БД"""
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Таблица тренеров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainers (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# =========================
# 🏁 СТАРТ БОТА
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    """Главное меню пользователя"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Выбрать тренера", "Связаться с администратором")
    
    bot.send_message(
        message.chat.id,
        "♟️ Добро пожаловать в шахматную школу!\nВыберите действие:",
        reply_markup=markup
    )
    user_states[message.chat.id] = "main_menu"

# =========================
# 👨‍💼 АДМИН-ПАНЕЛЬ
# =========================

@bot.message_handler(func=lambda message: message.text == "Edit")
def admin_panel(message):
    """Доступ в админ-панель (только для администратора)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет доступа")
        return
    
    user_states[message.chat.id] = "admin_panel"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить тренера", "➖ Удалить тренера")
    markup.add("📋 Список тренеров")
    
    bot.send_message(
        message.chat.id,
        "👨‍💼 Администраторская панель:",
        reply_markup=markup
    )

# ===== ДОБАВЛЕНИЕ ТРЕНЕРА =====

@bot.message_handler(func=lambda message: message.text == "➕ Добавить тренера")
def add_trainer_start(message):
    """Начало процесса добавления тренера"""
    if message.from_user.id != ADMIN_ID:
        return
    
    user_states[message.chat.id] = "waiting_trainer_username"
    bot.send_message(
        message.chat.id,
        "Введи @username тренера (с собачкой):\n(Пример: @chess_coach_ivan)"
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_trainer_username")
def get_trainer_username(message):
    """Получение username тренера"""
    username = message.text.strip()
    
    # Проверка формата @username
    if not username.startswith("@"):
        bot.send_message(message.chat.id, "❌ Username должен начинаться с @\nПопробуй снова:")
        return
    
    trainer_data[message.chat.id] = {"username": username}
    user_states[message.chat.id] = "waiting_trainer_name"
    bot.send_message(message.chat.id, "Введи имя тренера:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_trainer_name")
def get_trainer_name(message):
    """Получение имени тренера"""
    trainer_data[message.chat.id]["name"] = message.text
    user_states[message.chat.id] = "waiting_trainer_description"
    bot.send_message(message.chat.id, "Введи описание тренера (опыт, квалификация и т.д.):")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_trainer_description")
def get_trainer_description(message):
    """Получение описания и сохранение тренера в БД"""
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
        
        bot.send_message(
            message.chat.id,
            f"✅ Тренер {data['name']} успешно добавлен!"
        )
        
    except psycopg2.IntegrityError:
        bot.send_message(
            message.chat.id,
            f"❌ Тренер с username {data['username']} уже существует"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    user_states.pop(message.chat.id, None)
    trainer_data.pop(message.chat.id, None)

# ===== УДАЛЕНИЕ ТРЕНЕРА =====

@bot.message_handler(func=lambda message: message.text == "➖ Удалить тренера")
def delete_trainer_start(message):
    """Показ списка тренеров для удаления"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM trainers ORDER BY name")
        trainers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not trainers:
            bot.send_message(message.chat.id, "📭 Список тренеров пуст")
            return
        
        markup = types.InlineKeyboardMarkup()
        
        for trainer_id, name in trainers:
            btn = types.InlineKeyboardButton(
                text=f"❌ {name}",
                callback_data=f"delete_trainer_{trainer_id}"
            )
            markup.add(btn)
        
        bot.send_message(message.chat.id, "Выбери тренера для удаления:", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_trainer_"))
def delete_trainer_confirm(call):
    """Удаление тренера"""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Нет доступа", show_alert=True)
        return
    
    trainer_id = call.data.split("_")[2]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM trainers WHERE id = %s", (trainer_id,))
        trainer = cursor.fetchone()
        
        if not trainer:
            bot.answer_callback_query(call.id, "❌ Тренер не найден", show_alert=True)
            return
        
        cursor.execute("DELETE FROM trainers WHERE id = %s", (trainer_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ Удалено!", show_alert=False)
        bot.edit_message_text(
            f"✅ Тренер '{trainer[0]}' удалён из системы",
            call.message.chat.id,
            call.message.message_id
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}", show_alert=True)

# ===== СПИСОК ТРЕНЕРОВ =====

@bot.message_handler(func=lambda message: message.text == "📋 Список тренеров")
def list_trainers(message):
    """Показ всех тренеров"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, username, description FROM trainers ORDER BY name")
        trainers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not trainers:
            bot.send_message(message.chat.id, "📭 Список тренеров пуст")
            return
        
        text = "📋 **Список тренеров:**\n\n"
        for idx, (tid, name, username, desc) in enumerate(trainers, 1):
            text += f"{idx}. **{name}** ({username})\n"
            text += f"   _{desc}_\n\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# =========================
# 👤 ВЫБОР ТРЕНЕРА (ПОЛЬЗОВАТЕЛЬ)
# =========================

@bot.message_handler(func=lambda message: message.text == "Выбрать тренера")
def choose_trainer_start(message):
    """Начало процесса выбора тренера"""
    user_states[message.chat.id] = "waiting_phone"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📱 Отправить номер", request_contact=True)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id,
        "Поделись своим номером телефона:",
        reply_markup=markup
    )

@bot.message_handler(content_types=['contact'])
def get_phone(message):
    """Получение номера телефона"""
    if user_states.get(message.chat.id) != "waiting_phone":
        return
    
    user_form[message.chat.id] = {}
    user_form[message.chat.id]["phone"] = message.contact.phone_number
    
    user_states[message.chat.id] = "waiting_user_name"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("◀️ Отмена")
    
    bot.send_message(
        message.chat.id,
        "Спасибо! Теперь введи своё имя:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_user_name")
def get_user_name(message):
    """Получение имени пользователя"""
    if message.text == "◀️ Отмена":
        cancel_selection(message)
        return
    
    user_form[message.chat.id]["name"] = message.text
    user_states[message.chat.id] = "waiting_level"
    
    bot.send_message(
        message.chat.id,
        "Опиши свой уровень игры в шахматы:\n(Например: Начинающий, Среднее, Продвинутый)"
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_level")
def get_level(message):
    """Получение уровня и показ списка тренеров"""
    if message.text == "◀️ Отмена":
        cancel_selection(message)
        return
    
    user_form[message.chat.id]["level"] = message.text
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, description FROM trainers ORDER BY name")
        trainers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not trainers:
            bot.send_message(
                message.chat.id,
                "❌ К сожалению, сейчас нет доступных тренеров. Попробуй позже."
            )
            cancel_selection(message)
            return
        
        markup = types.InlineKeyboardMarkup()
        
        for trainer_id, name, desc in trainers:
            btn = types.InlineKeyboardButton(
                text=f"👨‍🏫 {name}",
                callback_data=f"choose_trainer_{trainer_id}"
            )
            markup.add(btn)
        
        bot.send_message(
            message.chat.id,
            "Выбери своего тренера:",
            reply_markup=markup
        )
        user_states[message.chat.id] = "trainer_selected"
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
        cancel_selection(message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("choose_trainer_"))
def send_request_to_trainer(call):
    """Отправка заявки выбранному тренеру"""
    trainer_id = call.data.split("_")[2]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT username, name FROM trainers WHERE id = %s",
            (trainer_id,)
        )
        trainer = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not trainer:
            bot.answer_callback_query(call.id, "❌ Тренер не найден", show_alert=True)
            return
        
        username, trainer_name = trainer
        data = user_form.get(call.message.chat.id)
        
        if not data:
            bot.answer_callback_query(call.id, "❌ Ошибка данных", show_alert=True)
            return
        
        # Отправка уведомления тренеру
        notification_text = f"""
🎯 **Новая заявка на занятие!**

👤 **Имя:** {data['name']}
📱 **Телефон:** {data['phone']}
♟️ **Уровень:** {data['level']}

Тренер, свяжись с учеником!
        """
        
        try:
            bot.send_message(username, notification_text, parse_mode="Markdown")
            bot.answer_callback_query(call.id, "✅ Заявка отправлена тренеру!", show_alert=False)
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"⚠️ Не удалось отправить заявку тренеру. Проверь контакты администратора."
            )
        
        # Подтверждение пользователю
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Выбрать другого тренера", "Связаться с администратором")
        
        bot.edit_message_text(
            f"✅ Твоя заявка отправлена тренеру {trainer_name}!\nОн свяжется с тобой в ближайшее время.",
            call.message.chat.id,
            call.message.message_id
        )
        
        bot.send_message(
            call.message.chat.id,
            "Что дальше?",
            reply_markup=markup
        )
        
        # Очистка данных
        user_states.pop(call.message.chat.id, None)
        user_form.pop(call.message.chat.id, None)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}", show_alert=True)

def cancel_selection(message):
    """Отмена выбора тренера"""
    user_states.pop(message.chat.id, None)
    user_form.pop(message.chat.id, None)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Выбрать тренера", "Связаться с администратором")
    
    bot.send_message(message.chat.id, "Отменено. Главное меню:", reply_markup=markup)

# =========================
# 💬 ЧАТС АДМИНИСТРАТОРОМ
# =========================

@bot.message_handler(func=lambda message: message.text == "Связаться с администратором")
def contact_admin_start(message):
    """Инициация чата с администратором"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛑 Завершить чат")
    
    bot.send_message(
        message.chat.id,
        "⏳ Ожидайте ответа администратора...\nАдминистратор скоро с вами свяжется!",
        reply_markup=markup
    )
    
    user_states[message.chat.id] = "waiting_admin_response"
    
    # Отправка уведомления администратору
    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.add(
        types.InlineKeyboardButton(
            "✅ Принять чат",
            callback_data=f"accept_chat_{message.chat.id}"
        )
    )
    admin_markup.add(
        types.InlineKeyboardButton(
            "❌ Отклонить",
            callback_data=f"reject_chat_{message.chat.id}"
        )
    )
    
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.chat.id}"
    
    bot.send_message(
        ADMIN_ID,
        f"📞 **Запрос на чат от пользователя**\n\nПользователь: {user_info}\nИмя: {message.from_user.first_name}",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_chat_"))
def accept_chat(call):
    """Администратор принимает чат"""
    user_id = int(call.data.split("_")[2])
    
    # Проверка, не активен ли чат
    if user_id in admin_chats:
        bot.answer_callback_query(call.id, "⚠️ Чат уже активен с другим админом", show_alert=True)
        return
    
    admin_chats[user_id] = call.from_user.id
    user_states[user_id] = "in_admin_chat"
    
    # Уведомления
    bot.edit_message_text(
        "✅ Чат принят! Начинаем общение.",
        call.message.chat.id,
        call.message.message_id
    )
    
    try:
        bot.send_message(
            user_id,
            "✅ Администратор принял вашу заявку!\n💬 Теперь вы можете общаться с ним напрямую.",
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_chat_"))
def reject_chat(call):
    """Администратор отклоняет чат"""
    user_id = int(call.data.split("_")[2])
    
    bot.edit_message_text(
        "❌ Чат отклонён.",
        call.message.chat.id,
        call.message.message_id
    )
    
    user_states[user_id] = "main_menu"
    
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Выбрать тренера", "Связаться с администратором")
        
        bot.send_message(
            user_id,
            "❌ Администратор отклонил вашу заявку. Попробуйте позже.",
            reply_markup=markup
        )
    except:
        pass

@bot.message_handler(func=lambda message: message.text == "🛑 Завершить чат")
def end_chat(message):
    """Завершение чата (пользователь)"""
    if message.chat.id not in admin_chats:
        return
    
    admin_id = admin_chats[message.chat.id]
    
    # Уведомления
    bot.send_message(
        message.chat.id,
        "👋 Чат завершён. Спасибо за обращение!"
    )
    
    try:
        bot.send_message(
            admin_id,
            f"👤 Пользователь завершил чат (ID: {message.chat.id})"
        )
    except:
        pass
    
    # Очистка
    admin_chats.pop(message.chat.id, None)
    user_states[message.chat.id] = "main_menu"
    
    # Возврат в главное меню
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Выбрать тренера", "Связаться с администратором")
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.chat.id in admin_chats and user_states.get(message.chat.id) == "in_admin_chat")
def relay_user_message(message):
    """Пересылка сообщения от пользователя к админу"""
    if message.text == "🛑 Завершить чат":
        end_chat(message)
        return
    
    admin_id = admin_chats[message.chat.id]
    
    try:
        bot.send_message(
            admin_id,
            f"💬 Сообщение от пользователя:\n\n{message.text}"
        )
    except:
        pass

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID)
def relay_admin_message(message):
    """Пересылка сообщения от админа к пользователю"""
    # Проверка, активен ли чат
    user_id = None
    for uid, aid in admin_chats.items():
        if aid == message.from_user.id:
            user_id = uid
            break
    
    if not user_id:
        bot.send_message(message.chat.id, "❌ Нет активного чата")
        return
    
    if message.text == "🛑 Завершить чат":
        try:
            bot.send_message(user_id, "👋 Администратор завершил чат.")
        except:
            pass
        admin_chats.pop(user_id, None)
        return
    
    try:
        bot.send_message(
            user_id,
            f"💬 Администратор:\n\n{message.text}"
        )
    except:
        bot.send_message(message.chat.id, f"❌ Не удалось отправить сообщение пользователю")

# =========================
# 🚀 ЗАПУСК БОТА
# =========================

if __name__ == "__main__":
    print("🚀 Бот запущен...")
    init_db()
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
