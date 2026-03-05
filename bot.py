import os
import logging
from flask import Flask, request
import telebot

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Загрузка переменных окружения ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Токен бота
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))  # ID администратора бота, 0 по умолчанию
CHANNEL_ID = os.environ.get('CHANNEL_ID')  # ID канала в Telegram (например: -1001234567890)

# Проверяем обязательные параметры
if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID:
    logger.error("❌ Параметры окружения не заданы или некорректны!")
    raise ValueError("Один из параметров окружения (BOT_TOKEN, ADMIN_ID, CHANNEL_ID) не установлен!")

# Инициализация бота и Flask
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)

# Глобальная переменная для подсчета отправленных сообщений
message_count = 0

# === Удаление старого Webhook и настройка нового ===
try:
    bot.remove_webhook()
    bot.set_webhook(url="https://<ВАШ-ДОМЕН>/webhook")  # ⚠️ Укажите ваш публичный домен
    logger.info("✅ Webhook успешно установлен.")
except Exception as e:
    logger.error(f"❌ Ошибка при установке Webhook: {e}")
    raise e

# === Маршруты ===

# Маршрут для проверки состояния сервера
@app.route("/", methods=["GET"])
def index():
    return "Сервер запущен и работает!", 200

# Обработка данных, поступающих на Webhook
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

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global message_count
    try:
        name = message.from_user.first_name or "пользователь"
        text = (
            f"👋 Привет, {name}!\n\n"
            "Напишите команду в формате: +число\n"
            "Например: +20 (отправит 20 сообщений в канал).\n\n"
            f"📊 Всего отправлено сообщений: {message_count}"
        )
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Ошибка в обработке команды /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Обработка команды вида "+число"
@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 На данный момент отправлено: {message_count} сообщений.\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимальное количество сообщений за раз: 10000.")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений в канал...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}.")
                message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке сообщения #{i}: {e}"
                )
                break

        bot.send_message(
            message.chat.id,
            f"✅ Успешная отправка {count} сообщений!\n"
            f"📊 Всего отправлено: {message_count}."
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат команды! Используйте: +число.")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды +число: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Команда /stats
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
        logger.error(f"Ошибка в обработке команды /stats: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Обработка неизвестных сообщений
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.reply_to(
        message,
        "Неизвестная команда. Доступные команды:\n"
        "/start — приветствие\n"
        "/stats — статистика\n"
        "+число — отправить сообщения в канал"
    )

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен!")
    app.run(host="0.0.0.0", port=5000)  # Убедитесь, что порт совпадает с Render@app.route("/", methods=["GET"])
def index():
    return "Сервер запущен и работает!", 200

# === Маршрут для обработки Webhook от Telegram ===
@app.route("/webhook", methods=["POST"])  # Фиксируем путь /webhook
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])  # Передаём обновление боту для обработки
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка обработки Webhook: {e}")
        return "error", 500

# === Хэндлеры бота ===

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global message_count
    try:
        name = message.from_user.first_name or "пользователь"
        text = (
            f"👋 Привет, {name}!\n\n"
            "Напишите команду в формате: +число\n"
            "Например: +20 (отправит 20 сообщений в канал).\n\n"
            f"📊 Всего отправлено сообщений: {message_count}"
        )
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Ошибка в обработке команды /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Команда для отправки сообщений (формат +число)
@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 На данный момент отправлено: {message_count} сообщений.\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимальное количество сообщений за раз: 10000.")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений в канал...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}.")
                message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке сообщения #{i}: {e}"
                )
                break

        bot.send_message(
            message.chat.id,
            f"✅ Успешная отправка {count} сообщений!\n"
            f"📊 Всего отправлено: {message_count}."
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат команды! Используйте: +число.")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды +число: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Команда /stats
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
        logger.error(f"Ошибка в обработке команды /stats: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Обработка остальных сообщений
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.reply_to(
        message,
        "Неизвестная команда. Используйте:\n"
        "/start — увидеть приветствие.\n"
        "/stats — узнать статистику.\n"
        "+число — отправить сообщения в канал."
    )

# === Запуск бота на Flask ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен!")
    app.run(host="0.0.0.0", port=5000)def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Ошибка обработки Webhook: {e}")
        return "error", 500

# === Хэндлеры бота ===

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global message_count
    try:
        name = message.from_user.first_name or "пользователь"
        text = (
            f"👋 Привет, {name}!\n\n"
            "Напишите команду в формате: +число\n"
            "Например: +20 (отправит 20 сообщений в канал).\n\n"
            f"📊 Всего отправлено сообщений: {message_count}"
        )
        bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Ошибка в обработке команды /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Команда для отправки сообщений (формат +число)
@bot.message_handler(func=lambda message: message.text and message.text.startswith('+'))
def handle_plus_command(message):
    global message_count
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 На данный момент отправлено: {message_count} сообщений.\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return

    try:
        count = int(message.text[1:])
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0!")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимальное количество сообщений за раз: 10000.")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений в канал...")

        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}.")
                message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке сообщения #{i}: {e}"
                )
                break

        bot.send_message(
            message.chat.id,
            f"✅ Успешная отправка {count} сообщений!\n"
            f"📊 Всего отправлено: {message_count}."
        )

    except ValueError:
        bot.reply_to(message, "❌ Неверный формат команды! Используйте: +число.")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды +число: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Команда /stats
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
        logger.error(f"Ошибка в обработке команды /stats: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Повторите попытку позже.")

# Обработка остальных сообщений
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.reply_to(
        message,
        "Неизвестная команда. Используйте:\n"
        "/start — увидеть приветствие.\n"
        "/stats — узнать статистику.\n"
        "+число — отправить сообщения в канал."
    )

# === Запуск бота на Flask ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен!")
    app.run(host="0.0.0.0", port=5000)  # Порт зафиксирован на 5000
