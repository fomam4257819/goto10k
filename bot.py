import os
import logging
from flask import Flask, request
import telebot

# Настройка логирования для диагностики
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# === Загрузка переменных окружения ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))  # Админ ID, по умолчанию 0 для проверки
CHANNEL_ID = os.environ.get('CHANNEL_ID')

# Проверяем обязательные параметры
if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID:
    logger.error("❌ Не заданы переменные окружения BOT_TOKEN, ADMIN_ID или CHANNEL_ID!")
    raise ValueError("Обязательные параметры окружения отсутствуют!")

# Инициализация Telegram API и Flask
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)  # Пропускаем старые обновления
app = Flask(__name__)

# Глобальная переменная для подсчета отправленных сообщений
message_count = 0

# === Маршруты для Flask ===

@app.route("/", methods=["GET"])
def index():
    """Диагностический маршрут."""
    logger.info("Запрос проверки состояния сервера.")
    return "Сервер работает!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Обработка обновлений от Telegram."""
    try:
        # Читаем JSON из запроса Telegram.
        json_str = request.get_data().decode('utf-8')
        logger.info(f"Получено обновление: {json_str}")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])  # Передаем обновления в библиотеку Telebot
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка в обработке Webhook: {e}")
        return "error", 500

# === Обработчики команд ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветственная команда."""
    global message_count
    user_id = message.from_user.id
    logger.info(f"Запрос команды /start от {user_id}")
    bot.reply_to(
        message,
        f"👋 Привет, {message.from_user.first_name or 'друг'}!\n\n"
        f"📊 Всего отправлено сообщений: {message_count}.\n\n"
        f"Используй команды:\n"
        f"  ➡️ Добавить сообщения: +число\n"
        f"  ➡️ Статистика: /stats"
    )

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Команда для отображения статистики."""
    logger.info(f"Запрос команды /stats от {message.from_user.id}")
    bot.reply_to(
        message,
        f"📊 Всего отправлено сообщений: {message_count}.\n"
        f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
    )

@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    """Обработка команды +число для отправки сообщений в канал."""
    global message_count
    user_id = message.from_user.id
    logger.info(f"Запрос команды {message.text} от {user_id}")

    try:
        if user_id != ADMIN_ID:
            logger.warning(f"Доступ запрещен для пользователя {user_id} (команда {message.text})")
            bot.reply_to(
                message,
                f"❌ Вы не админ!\n\n"
                f"📊 Всего отправлено сообщений: {message_count}.\n"
                f"🔗 Тут наш канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
            )
            return

        # Парсим количество сообщений из команды
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимальное количество сообщений за раз: 10000!")
            return

        bot.reply_to(message, f"⏳ Отправляю {count} сообщений в канал...")
        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}.")
                message_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения #{i}: {e}")
                bot.send_message(message.chat.id, f"❌ Ошибка при отправке сообщения #{i}: {e}")
                break

        bot.reply_to(
            message,
            f"✅ Успешно отправлено {count} сообщений!\n"
            f"📊 Всего отправлено: {message_count}."
        )
    except ValueError:
        logger.error(f"Неверный формат команды: {message.text}")
        bot.reply_to(message, "❌ Неверный формат команды! Используйте команду в формате: +число")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды {message.text}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Попробуйте позже.")

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Обработчик неизвестных сообщений."""
    logger.info(f"Неизвестная команда от {message.from_user.id}: {message.text}")
    bot.reply_to(
        message,
        "❌ Я понял только команды:\n"
        "/start — информация о боте\n"
        "/stats — статистика\n"
        "+число — отправить сообщения в канал"
    )

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен!")
    app.run(host="0.0.0.0", port=5000)
