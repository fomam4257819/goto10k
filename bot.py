import os
import telebot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем переменные из Render
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')  # например: -100123456789

# Инициализируем бот
bot = telebot.TeleBot(BOT_TOKEN)

# Счетчик отправленных смс (в реальном приложении лучше использовать БД)
message_count = 0

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    text = f"👋 Привет, {message.from_user.first_name}!\n\n"
    text += "Напишите команду в формате: +число\n"
    text += "Например: +20 (отправит 20 смс в канал)\n"
    text += f"📊 Всего смс отправлено: {message_count}"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda message: message.text.startswith('+'))
def handle_plus_command(message):
    """Обработчик команд вида +число"""
    global message_count
    
    # Проверяем, является ли пользователь админом
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(
            message,
            f"❌ Вы не админ!\n\n"
            f"📊 В нашем канале уже отправлено: {message_count} смс\n"
            f"🔗 Ссылка на канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
        )
        return
    
    # Парсим число из команды
    try:
        count = int(message.text[1:])  # Убираем '+' и преобразуем в число
        
        if count <= 0:
            bot.reply_to(message, "⚠️ Число должно быть положительным!")
            return
        
        if count > 10000:
            bot.reply_to(message, "⚠️ Максимум 10000 смс за раз!")
            return
        
        # Отправляем смс в канал
        bot.reply_to(message, f"⏳ Начинаю отправку {count} смс в канал...")
        
        for i in range(count):
            try:
                bot.send_message(CHANNEL_ID, "+1")
                message_count += 1
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ Ошибка при отправке смс #{i+1}: {str(e)}"
                )
                break
        
        # Отправляем отчет
        bot.send_message(
            message.chat.id,
            f"✅ Успешно отправлено {count} смс в канал!\n"
            f"📊 Всего отправлено: {message_count}"
        )
        
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат! Используйте: +число\nНапример: +20")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Обработчик команды /stats - показывает статистику"""
    bot.reply_to(
        message,
        f"📊 Статистика:\n\n"
        f"Всего смс отправлено: {message_count}\n"
        f"🔗 Канал: https://t.me/{CHANNEL_ID.replace('-100', '')}"
    )

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Обработчик остальных сообщений"""
    bot.reply_to(
        message,
        "Я понимаю только команды вида +число\n"
        "Например: +20"
    )

if __name__ == '__main__':
    print("🤖 Бот запущен...")
    bot.infinity_polling()