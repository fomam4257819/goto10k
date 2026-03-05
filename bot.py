import os
import logging
from flask import Flask, request
import telebot
import traceback

# === Логирование для диагностики ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("telegram_bot")

# === Загрузка переменных окружения ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))  # Обязательно укажите в Render
CHANNEL_ID = os.environ.get('CHANNEL_ID')      # Например: -1001234567890
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')    # Необязательно: https://your-domain/webhook

# Проверяем п��ременные окружения
if not BOT_TOKEN or not CHANNEL_ID or ADMIN_ID == 0:
    logger.error("❌ Ошибка: BOT_TOKEN, ADMIN_ID или CHANNEL_ID не заданы корректно!")
    raise ValueError("Не заданы обязательные переменные окружения: BOT_TOKEN, ADMIN_ID, CHANNEL_ID")

# === Инициализация TeleBot и Flask ===
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)
app = Flask(__name__)

# === Глобальная статистика ===
message_count = 0

# === Вспомогательные функции ===
def safe_write_log(path: str, text: str) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        logger.error(f"Не удалось записать в {path}: {e}")

# === Flask маршруты ===

@app.route("/", methods=["GET"])
def index():
    """Маршрут для проверки работоспособности сервера."""
    logger.info("Проверка состояния сервера: GET /")
    return "Сервер работает корректно!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Маршрут для обработки Webhook от Telegram."""
    try:
        raw = request.get_data()
        if not raw:
            logger.warning("Webhook: пустое тело запроса")
            # Чтобы Telegram не перестал слать вебхуки — возвращаем 200
            return "ok", 200

        try:
            json_str = raw.decode('utf-8')
        except Exception:
            json_str = str(raw)
        logger.info(f"Webhook: получено обновление: {json_str}")

        # Сохраняем входящее обновление в файл для отладки
        safe_write_log("/tmp/webhook_incoming.log", json_str)

        try:
            update = telebot.types.Update.de_json(json_str)
        except Exception as e:
            logger.error(f"Webhook: не удалось распарсить JSON в Update: {e}")
            logger.debug(traceback.format_exc())
            return "ok", 200  # не хотим, чтобы Telegram повторял бесконечно при некорректном теле

        # Передаём обновление в TeleBot
        try:
            bot.process_new_updates([update])
            logger.info("Webhook: обновление передано TeleBot для обработки")
        except Exception as e:
            logger.error(f"Webhook: TeleBot.process_new_updates выбросил исключение: {e}")
            logger.debug(traceback.format_exc())
            # Возвращаем 200, чтобы Telegram не отрезал вебхук; можно вернуть 500 для повторной отправки
            return "ok", 200

        return "ok", 200

    except Exception as e:
        logger.error(f"Webhook: неожиданная ошибка: {e}")
        logger.debug(traceback.format_exc())
        return "error", 500

# === Хэндлеры команд ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Ответ на команду /start."""
    global message_count
    try:
        user_id = message.from_user.id
        logger.info(f"Команда /start от {user_id}")
        bot.reply_to(message, "Привет! Я твой бот. Попробуй /stats или +число (только админ).")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        logger.debug(traceback.format_exc())

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Ответ на команду /stats."""
    try:
        logger.info(f"Команда /stats от {message.from_user.id}")
        bot.reply_to(
            message,
            f"📊 Всего отправлено сообщений: {message_count}\n"
            f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
    except Exception as e:
        logger.error(f"Ошибка в обработчике /stats: {e}")
        logger.debug(traceback.format_exc())

@bot.message_handler(func=lambda message: message.text and message.text.strip().startswith('+'))
def handle_plus_command(message):
    """Обработка команды +число для отправки сообщений в канал (только админ)."""
    global message_count
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        logger.info(f"Команда {text} от {user_id}")

        if user_id != ADMIN_ID:
            logger.warning(f"Пользователь {user_id} не админ, попытка выполнить {text}")
            bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")
            return

        try:
            count = int(text[1:])
        except ValueError:
            bot.reply_to(message, "❌ Неверный формат. Используйте +число, например +5.")
            return

        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть больше 0.")
            return
        if count > 10000:
            bot.reply_to(message, "⚠️ Слишком много. Максимум 10000.")
            return

        bot.reply_to(message, f"⏳ Начинаю отправку {count} сообщений в канал...")
        sent = 0
        for i in range(1, count + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {count}")
                sent += 1
                message_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения #{i}: {e}")
                bot.send_message(message.chat.id, f"❌ Ошибка при отправке сообщения #{i}: {e}")
                break

        bot.reply_to(message, f"✅ Отправлено {sent} из {count} сообщений. Всего: {message_count}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике +число: {e}")
        logger.debug(traceback.format_exc())
        try:
            bot.reply_to(message, "❌ Внутренняя ошибка обработчика. Смотрите логи.")
        except Exception:
            pass

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Обработчик всех прочих сообщений."""
    try:
        logger.info(f"Неизвестное сообщение от {message.from_user.id}: {getattr(message, 'text', '<no-text>')}")
        bot.reply_to(message, "Я понимаю /start, /stats и +число (только админ).")
    except Exception as e:
        logger.error(f"Ошибка в handle_unknown: {e}")
        logger.debug(traceback.format_exc())

# === (Опционально) Установка webhook из кода, если указан WEBHOOK_URL ===
if WEBHOOK_URL:
    try:
        # Устанавливаем webhook при старте, если задан WEBHOOK_URL
        bot.remove_webhook()
        success = bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Попытка установки webhook: {WEBHOOK_URL} -> {success}")
    except Exception as e:
        logger.error(f"Не удалось установить webhook автоматически: {e}")
        logger.debug(traceback.format_exc())

# === Запуск приложения ===
if __name__ == "__main__":
    logger.info("🤖 Бот запущен (app.run). На проде использйте gunicorn: gunicorn bot:app")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
