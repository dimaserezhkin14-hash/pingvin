# -*- coding: utf-8 -*-
import telebot
import time
import requests
import base64
import uuid
import os
import urllib3
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

urllib3.disable_warnings()

# БЕЗОПАСНО - берём из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GIGACHAT_AUTH = os.getenv('GIGACHAT_AUTH')
GROUP_ID = int(os.getenv('GROUP_ID', '-1003914504408'))

# Проверяем, что все переменные загружены
if not all([API_TOKEN, GEMINI_API_KEY, GIGACHAT_AUTH]):
    print("❌ ОШИБКА: Не все переменные окружения загружены!")
    print("Проверьте файл .env")
    exit(1)

bot = telebot.TeleBot(API_TOKEN)
session = requests.Session()
session.verify = False

SYSTEM_PROMPT = "Ты нейросеть Пингвин. Отвечай естественно и по делу."

gigachat_token = None
gigachat_token_expire = 0

def ask_gemini(prompt, image_data=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    parts = [{"text": prompt}]
    if image_data:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_data).decode('utf-8')}})
    data = {"contents": [{"parts": parts, "role": "user"}], "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        pass
    return None

def get_gigachat_token():
    global gigachat_token, gigachat_token_expire
    if gigachat_token and time.time() < gigachat_token_expire:
        return gigachat_token
    try:
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {"Authorization": f"Basic {GIGACHAT_AUTH}", "RqUID": str(uuid.uuid4()), "Content-Type": "application/x-www-form-urlencoded"}
        response = session.post(url, headers=headers, data={"scope": "GIGACHAT_API_PERS"}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            gigachat_token = result["access_token"]
            gigachat_token_expire = time.time() + 1800
            return gigachat_token
    except:
        pass
    return None

def ask_gigachat(prompt):
    token = get_gigachat_token()
    if not token:
        return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = {"model": "GigaChat", "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 1000}
        response = session.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

def ask_ai(prompt, image_data=None):
    response = ask_gemini(prompt, image_data)
    if response:
        return response
    response = ask_gigachat(prompt)
    if response:
        return response
    return "❌ Нейросети временно недоступны. Попробуйте позже."

def log_to_group(text):
    try:
        bot.send_message(GROUP_ID, text, parse_mode="HTML")
    except:
        pass

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🐧 Привет! Я Пингвин! Отправь мне сообщение или фото.")
    log_to_group(f"🟢 Новый пользователь: @{message.from_user.username}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.send_chat_action(message.chat.id, "typing")
        caption = message.caption or "Опиши это фото"
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        file_content = bot.download_file(file_info.file_path)
        response = ask_ai(caption, file_content)
        bot.send_message(message.chat.id, response)
        log_to_group(f"📸 Фото от @{message.from_user.username}")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Попробуйте позже.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    try:
        bot.send_chat_action(message.chat.id, "typing")
        response = ask_ai(message.text)
        bot.send_message(message.chat.id, response)
        log_to_group(f"💬 @{message.from_user.username}: {message.text[:50]}...")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Попробуйте позже.")

print("🐧 Бот Пингвин запущен!")
bot.polling()
