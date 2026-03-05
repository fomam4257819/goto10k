import os
import json
import threading
from flask import Flask, request
import telebot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in environment")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)  # ✅ Исправлено

# Счетчик отправленных сообщений
message_count = 0
message_lock = threading.Lock()

def load_count():
    try:
        with open('message_count.json', 'r') as f:
            return json.load(f)['count']
    except:
        return 0

def save_count(count):
    with open('message_count.json', 'w') as f:
        json.dump({'count': count}, f)

message_count = load_count()

# === Webhook ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# === Хэндлеры ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = f"👋 Привет, {message.from_user.first_name}!\n\n"
    text += "Напишите команду в формате: +число\n"
    text += "Например: +20 (отправит 20 смс в канал)\n"
    text += f"📊 Всего смс отправлено: {message_count}"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda message: message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 В нашем канале уже отправлено: {message_count} смс\n"
            f"🔗 Ссылка на канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть положительным!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000 смс за раз!")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} смс в канал...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"+1 ({i}/{count})")
                with message_lock:
                    message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке смс #{i}: {str(e)}"
                )
                break

        save_count(message_count)
        bot.send_message(
            message.chat.id,
            f"✅ Успешно отправлено {count} смс в канал!\n"
            f"📊 Всего отправлено: {message_count}"
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат! Используйте: +число\nНапример: +20")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    bot.reply_to(
        message,
        f"📊 Статистика:\n\n"
        f"Всего смс отправлено: {message_count}\n"
        f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
    )

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    bot.reply_to(
        message,
        "Я понимаю только команды вида +число\nНапример: +20"
    )

# === Главный запуск для локального теста ===
if __name__ == "__main__":  # ✅ Исправлено
    print("🤖 Бот Flask запущен...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
