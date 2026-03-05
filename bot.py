import os
import logging
from flask import Flask, request
import telebot

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Загрузка переменных окружения ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))  # Значение по умолчанию 0
CHANNEL_ID = os.environ.get('CHANNEL_ID')

# Проверяем обязательные параметры
if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID:
    logger.error("❌ Параметры окружения не заданы!")
    raise ValueError("BOT_TOKEN, ADMIN_ID или CHANNEL_ID не установлен!")

# Инициализация бота и Flask
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)

# Глобальная переменная для подсчета отправленных сообщений
message_count = 0

# === Flask Маршруты ===

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка обработки Webhook: {e}")
        return "error", 500

# === Хэндлеры бота ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    global message_count
    name = message.from_user.first_name or "пользователь"
    bot.reply_to(
        message,
        f"👋 Привет, {name}!\n\n"
        f"📊 Отправлено сообщений: {message_count}\n"
        f"Используйте команды:\n"
        f"  ➡️ +число — чтобы отправить сообщения\n"
        f"  ➡️ /stats — статистика"
    )

@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    try:
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ Только администратор может использовать эту команду!")
            return

        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000 сообщений за раз!")
            return

        for i in range(1, count + 1):
            bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}")
            message_count += 1

        bot.reply_to(
            message,
            f"✅ Отправлено {count} сообщений!\n"
            f"📊 Всего отправлено: {message_count}"
        )
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат! Используйте: +число")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    bot.reply_to(
        message,
        f"📊 Статистика:\n"
        f"Всего отправлено сообщений: {message_count}"
    )

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.reply_to(
        message,
        "❌ Неизвестная команда. Используйте:\n"
        "/start — информация о боте\n"
        "/stats — статистика\n"
        "+число — чтобы отправить сообщения"
    )

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен и готов к работе!")
    app.run(host="0.0.0.0", port=5000)
