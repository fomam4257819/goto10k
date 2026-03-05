import os
import logging
from flask import Flask, request
import telebot
from dotenv import load_dotenv

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Проверяем все переменные
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    raise ValueError("BOT_TOKEN required")

try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
except ValueError:
    logger.error("❌ ADMIN_ID должен быть числом!")
    raise

CHANNEL_ID = os.getenv('CHANNEL_ID')
if not CHANNEL_ID:
    logger.error("❌ CHANNEL_ID не установлен!")
    raise ValueError("CHANNEL_ID required")

WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # например: https://mybot.com

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)  # ✅ Исправлено

message_count = 0

logger.info("✅ Бот инициализирован успешно")

# === Webhook ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    global message_count
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "error", 500

@app.before_first_request
def setup_webhook():
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
            logger.info(f"✅ Webhook установлен: {WEBHOOK_URL}/{BOT_TOKEN}")
        except Exception as e:
            logger.error(f"❌ Ошибка при установке webhook: {e}")

# === Хэндлеры ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        name = message.from_user.first_name or "пользователь"
        text = f"👋 Привет, {name}!\n\n"
        text += "Напишите команду в формате: +число\n"
        text += "Например: +20 (отправит 20 смс в канал)\n"
        text += f"📊 Всего смс отправлено: {message_count}"
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Error in send_welcome: {e}")
        bot.reply_to(message, "❌ Ошибка при обработке команды")

@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 Всего отправлено: {message_count} смс\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть положительным!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000!")
            return

        bot.reply_to(message, f"⏳ Отправляю {count} сообщений...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"+1 ({i}/{count})")
                message_count += 1
            except Exception as e:
                logger.error(f"Error sending message #{i}: {e}")
                bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
                break

        bot.send_message(
            message.chat.id,
            f"✅ Отправлено {count}!\n📊 Всего: {message_count}"
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат! Используйте: +20")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    try:
        bot.reply_to(
            message,
            f"📊 Статистика:\n"
            f"Всего отправлено: {message_count} смс"
        )
    except Exception as e:
        logger.error(f"Error in stats: {e}")

@bot.message_handler(func=lambda message: True)
def handle_other(message):
    try:
        bot.reply_to(message, "Используйте: +число")
    except Exception as e:
        logger.error(f"Error handling message: {e}")

# === Запуск ===
if __name__ == "__main__":  # ✅ Исправлено
    logger.info("🤖 Бот запущен на 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
