import os
import logging
from flask import Flask, request
import telebot
from dotenv import load_dotenv

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Проверяем наличие всех необходимых переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
except ValueError:
    logger.error("❌ ADMIN_ID должен быть числом!")
    raise

CHANNEL_ID = os.getenv('CHANNEL_ID')
if not CHANNEL_ID:
    logger.error("❌ CHANNEL_ID не установлен!")
    raise ValueError("CHANNEL_ID не найден в переменных окружения")

WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # URL для доступа к вашему вебхуку

# Инициализация бота и Flask-приложения
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)

# Глобальная переменная для подсчета отправленных сообщений (обновляется в реальном времени)
message_count = 0

# === Регистрация Webhook ===
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
        logger.info(f"✅ Webhook успешно установлен: {WEBHOOK_URL}/{BOT_TOKEN}")
    except Exception as e:
        logger.error(f"❌ Ошибка при установке Webhook: {e}")
else:
    logger.error("❌ Переменная окружения WEBHOOK_URL не задана!")

# === Flask endpoint для обработки Webhook ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка обработки Webhook: {e}")
        return "error", 500

# === Команды ===

# Команда /start — Приветствие бота
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global message_count
    try:
        name = message.from_user.first_name or "пользователь"
        text = f"👋 Привет, {name}!\n\n"
        text += "Напишите команду в формате: +число\n"
        text += "Например: +20 (отправит 20 сообщений в канал)\n"
        text += f"📊 Всего сообщений отправлено: {message_count}"
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Пожалуйста, попробуйте снова.")

# Команда для отправки сообщений (формат +число)
@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 В канале уже отправлено: {message_count} сообщений\n"
            f"🔗 Ссылка на канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть положительным!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000 сообщений за раз!")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i}/{count}")
                message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке сообщения #{i}: {e}"
                )
                break

        bot.send_message(
            message.chat.id,
            f"✅ Отправлено {count} сообщений успешно!\n📊 Всего отправлено: {message_count}"
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат! Используйте: +число\nНапример: +20")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды +число: {e}")
        bot.reply_to(message, "Произошла ошибка при выполнении команды!")

# Команда /stats — Показ статистики
@bot.message_handler(commands=['stats'])
def send_stats(message):
    try:
        bot.reply_to(
            message,
            f"📊 Статистика:\n\n"
            f"Всего сообщений отправлено: {message_count}\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде /stats: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении статистики.")

# Обработка всех остальных сообщений
@bot.message_handler(func=lambda message: True)
def handle_other(message):
    bot.reply_to(
        message,
        "Я понимаю только команды в формате:\n/start, /stats, +число\nНапример: +20"
    )

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен и готов к работе на 0.0.0.0!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
