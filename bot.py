import os
import sys
import logging
import traceback
from flask import Flask, request, jsonify
import telebot

# ==========================
# Настройка логирования
# ==========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("telegram_bot")

# ==========================
# Переменные окружения
# ==========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
except Exception:
    ADMIN_ID = 0
CHANNEL_ID = os.environ.get("CHANNEL_ID")            # пример: -1001234567890
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")          # опционально: https://your-domain/webhook
LOG_PATH = os.environ.get("WEBHOOK_LOG_PATH", "/tmp/webhook_incoming.log")
PORT = int(os.environ.get("PORT", 5000))
RUN_MODE = os.environ.get("RUN_MODE", "").lower()    # if "polling" -> use polling for debug

# ==========================
# Проверка обязательных переменных
# ==========================
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не задан! Установите переменную окружения BOT_TOKEN.")
    raise ValueError("BOT_TOKEN required")
if not CHANNEL_ID:
    logger.error("CHANNEL_ID не задан! Установите переменную окружения CHANNEL_ID.")
    raise ValueError("CHANNEL_ID required")
if ADMIN_ID == 0:
    logger.error("ADMIN_ID не задан или равен 0! Установите переменную окружения ADMIN_ID.")
    raise ValueError("ADMIN_ID required and must be non-zero")

# ==========================
# Инициализация TeleBot и Flask
# ==========================
bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True, threaded=True)
app = Flask(__name__)

# Счётчик отправленных сообщений (жизнь процесса)
message_count = 0

# ==========================
# Утилиты
# ==========================
def safe_write_log(path: str, text: str) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        logger.error(f"Не удалось записать в {path}: {e}")

def tail(path: str, n: int = 200) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except FileNotFoundError:
        return ""
    except Exception as e:
        logger.error(f"tail error: {e}")
        return ""

# ==========================
# Лог стартапа (показывает, что развернули нужный релиз)
# ==========================
logger.info("STARTUP: бот загружен. PID=%s WEBHOOK_URL=%s RUN_MODE=%s", os.getpid(), WEBHOOK_URL or "not-set", RUN_MODE)

# ==========================
# Flask маршруты
# ==========================
@app.route("/", methods=["GET"])
def index():
    logger.info("GET / - проверка состояния")
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Основной endpoint для Telegram Webhook.
    Логируем входящие, сохраняем в файл и передаём в telebot.
    """
    try:
        remote = request.remote_addr
        headers = dict(request.headers)
        raw = request.get_data()
        if not raw:
            logger.warning("Webhook: пустое тело запроса")
            # Возвращаем 200, чтобы Telegram не повторял бесконечно
            return "ok", 200

        try:
            text = raw.decode("utf-8")
        except Exception:
            text = str(raw)

        logger.info("Webhook: received from %s User-Agent=%s len=%d", remote, headers.get("User-Agent", ""), len(raw))
        logger.info("Webhook: payload: %s", text)

        # Сохраняем входящие для отладки
        safe_write_log(LOG_PATH, text)

        # Попытка распарсить Update
        try:
            update = telebot.types.Update.de_json(text)
        except Exception as e:
            logger.error("Webhook: не удалось распарсить JSON -> Update: %s", e)
            logger.debug(traceback.format_exc())
            # Возвращаем 200, чтобы Telegram не зацикливал попытки при некорректном теле
            return "ok", 200

        # Передаём обновление в TeleBot
        try:
            bot.process_new_updates([update])
            logger.info("Webhook: update передано telebot для обработки")
        except Exception as e:
            logger.error("Webhook: ошибка при process_new_updates: %s", e)
            logger.debug(traceback.format_exc())
            # Возвращаем 200, чтобы Telegram не отрубил webhook; можно изменить стратегию
            return "ok", 200

        return "ok", 200

    except Exception as e:
        logger.error("Webhook: непредвиденная ошибка: %s", e)
        logger.debug(traceback.format_exc())
        return "error", 500

@app.route("/debug/logs", methods=["GET"])
def debug_logs():
    """
    Возвращает preview входящих webhook payload'ов.
    Не оставляйте публичным без защиты в продакшене.
    """
    content = tail(LOG_PATH, 500)
    return jsonify({
        "webhook_url": WEBHOOK_URL or "not-set",
        "log_preview": content,
    }), 200

@app.route("/admin/send_test", methods=["POST"])
def admin_send_test():
    """
    Отправляет тестовое сообщение администратору. Удобно для проверки исходящих сообщений.
    """
    try:
        bot.send_message(ADMIN_ID, "Тестовое сообщение от бота (check outgoing)")
        return "sent", 200
    except Exception as e:
        logger.error("admin_send_test error: %s", e)
        logger.debug(traceback.format_exc())
        return f"error: {e}", 500

@app.route("/admin/set_webhook", methods=["POST"])
def admin_set_webhook():
    """
    Устанавливает webhook в Telegram по WEBHOOK_URL (если задан).
    """
    if not WEBHOOK_URL:
        return "WEBHOOK_URL not set", 400
    try:
        bot.remove_webhook()
        ok = bot.set_webhook(url=WEBHOOK_URL)
        logger.info("set_webhook -> %s : %s", WEBHOOK_URL, ok)
        return jsonify({"result": ok}), 200
    except Exception as e:
        logger.error("set_webhook error: %s", e)
        logger.debug(traceback.format_exc())
        return f"error: {e}", 500

# ==========================
# Handlers (telebot)
# ==========================
@bot.message_handler(commands=["start"])
def handle_start(message):
    try:
        user_id = message.from_user.id
        logger.info("/start from %s", user_id)
        bot.reply_to(message, f"Привет, {message.from_user.first_name or ''}! Ваш id: {user_id}")
    except Exception as e:
        logger.error("handle_start error: %s", e)
        logger.debug(traceback.format_exc())

@bot.message_handler(commands=["stats"])
def handle_stats(message):
    try:
        bot.reply_to(message, f"Всего отправлено сообщений (за время работы процесса): {message_count}")
    except Exception as e:
        logger.error("handle_stats error: %s", e)
        logger.debug(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text and m.text.strip().startswith("+"))
def handle_plus(m):
    global message_count
    try:
        user_id = m.from_user.id
        text = m.text.strip()
        logger.info("+ command from %s: %s", user_id, text)
        if user_id != ADMIN_ID:
            bot.reply_to(m, "У вас нет прав для этой команды.")
            return
        try:
            cnt = int(text[1:])
        except ValueError:
            bot.reply_to(m, "Неверный формат. Используйте +число")
            return
        if cnt <= 0:
            bot.reply_to(m, "Число должно быть > 0")
            return
        if cnt > 10000:
            bot.reply_to(m, "Максимум 10000")
            return
        bot.reply_to(m, f"Отправляю {cnt} сообщений...")
        sent = 0
        for i in range(1, cnt + 1):
            try:
                bot.send_message(CHANNEL_ID, f"Сообщение {i} из {cnt}")
                sent += 1
                message_count += 1
            except Exception as e:
                logger.error("send_message error #%d: %s", i, e)
                try:
                    bot.send_message(m.chat.id, f"Ошибка отправки #{i}: {e}")
                except Exception:
                    logger.error("Не удалось отправить сообщение об ошибке пользователю")
                break
        try:
            bot.send_message(m.chat.id, f"Отправлено {sent} из {cnt}. Всего: {message_count}")
        except Exception:
            logger.error("Не удалось отправить итоговое сообщение администратору")
    except Exception as e:
        logger.error("handle_plus unexpected: %s", e)
        logger.debug(traceback.format_exc())

@bot.message_handler(func=lambda m: True)
def handle_unknown(m):
    try:
        uid = getattr(m.from_user, "id", None)
        text = getattr(m, "text", "<no-text>")
        logger.info("unknown message from %s: %s", uid, text)
        bot.reply_to(m, "Я понимаю /start, /stats и команды вида +число (только админ).")
    except Exception as e:
        logger.error("handle_unknown error: %s", e)
        logger.debug(traceback.format_exc())

# ==========================
# Точка запуска — polling (debug) или webhook (prod)
# ==========================
if __name__ == "__main__":
    # Если задан режим polling — используем его для теста (переменная RUN_MODE=polling)
    if RUN_MODE == "polling":
        logger.info("Запуск в polling-режиме для теста. Убедитесь, что WEBHOOK_URL не установлен или webhook удалён.")
        try:
            bot.remove_webhook()
        except Exception:
            pass
        # infinity_polling блокирует поток и запускает обработчики напрямую
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    else:
        # Попытка автоматической установки webhook при старте (если задан WEBHOOK_URL)
        if WEBHOOK_URL:
            try:
                bot.remove_webhook()
                ok = bot.set_webhook(url=WEBHOOK_URL)
                logger.info("Авто-установка webhook при старте: %s -> %s", WEBHOOK_URL, ok)
            except Exception as e:
                logger.error("Ошибка авто-установки webhook: %s", e)
                logger.debug(traceback.format_exc())

        logger.info("Запуск Flask dev server (для продакшена используйте gunicorn): app.run on %s", PORT)
        app.run(host="0.0.0.0", port=PORT)
