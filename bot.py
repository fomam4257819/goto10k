import os
import logging
from flask import Flask, request
import telebot

# Настроим логирование для диагностики
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# === Параметры окружения ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))  # Установить значение по умолчанию 0 (если переменной нет)
CHANNEL_ID = os.environ.get('CHANNEL_ID')

# Проверяем обязательные параметры
if not BOT_TOKEN or not CHANNEL_ID or ADMIN_ID == 0:
    logger.error("❌ Обязательные параметры окружения не установлены: BOT_TOKEN, ADMIN_ID или CHANNEL_ID.")
    raise ValueError("Один из параметров окружения отсутствует!")

# === Инициализация бота и Flask ===
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)

# === Глобальная переменная ===
message_count = 0

# === Flask маршруты ===

@app.route("/", methods=["GET"])
def index():
    """Эндпоинт для проверки работы сервера."""
    logger.info("Проверка состояния сервера: всё в норме.")
    return "Сервер работает корректно!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Эндпоинт для обработки Webhook."""
    try:
        json_str = request.get_data().decode('utf-8')
        logger.info(f"Получено обновление от Telegram: {json_str}")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка обработки Webhook: {e}")
        return "error", 500

# === Хэндлеры команд бота ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start."""
    global message_count
    logger.info(f"/start вызван пользователем {message.from_user.id}")
    bot.reply_to(
        message,
        f"🤖 Привет, {message.from_user.first_name}!\n\n"
        "Вот что я умею:\n"
        "1. Команда +число отправляет сообщения в канал.\n"
        "2. /stats — покажет статистику отправки сообщений.\n\n"
        f"📊 На данный момент отправлено сообщений: {message_count}"
    )

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Обработчик команды /stats."""
    global message_count
    logger.info(f"/stats вызван пользователем {message.from_user.id}")
    bot.reply_to(
        message,
        f"📊 Статистика:\n"
        f"- Сообщений отправлено в канал: {message_count}\n"
        f"- Ссылка на канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
    )

@bot.message_handler(func=lambda message: message.text.startswith('+'))
def handle_plus_command(message):
    """Обработчик команды +число."""
    global message_count
    user_id = message.from_user.id
    command = message.text

    logger.info(f"Команда {command} вызвана пользователем {user_id}")

    if user_id != ADMIN_ID:
        bot.reply_to(message, f"❌ У вас нет прав для выполнения этой команды!")
        logger.warning(f"Пользователь {user_id} попытался вызвать {command}, но не является админом.")
        return

    try:
        count = int(command[1:])  # Берём число после знака '+'
        
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000 сообщений за раз!")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений в канал...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}")
                message_count += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения #{i}: {e}")
                bot.send_message(message.chat.id, f"❌ Ошибка при отправке сообщения номер {i}: {e}")
                break

        bot.reply_to(
            message,
            f"✅ Отправлено {count} сообщений в канал успешно!\n"
            f"📊 Всего сообщений: {message_count}"
        )
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат команды! Используйте +число.")
    except Exception as e:
        logger.error(f"Неожиданное исключение в обработке команды {command}: {e}")
        bot.reply_to(message, "❌ Что-то пошло не так... Попробуйте позже!")

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Обработчик неизвестных команд."""
    logger.info(f"Неизвестное сообщение: {message.text} от {message.from_user.id}")
    bot.reply_to(
        message,
        "❌ Я не понимаю эту команду. Попробуйте:\n"
        "/start — для информации\n"
        "/stats — для статистики\n"
        "+число — для отправки сообщений в канал"
    )

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен и готов к работе!")
    app.run(host="0.0.0.0", port=5000)
