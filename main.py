import os
import requests
from fastapi import FastAPI, Request
import telebot

# --- कॉन्फ़िगरेशन ---
# @BotFather से मिला हुआ टोकन यहाँ डालें
BOT_TOKEN = "8835412290:AAESGmVJ6Km9xCiPBiJgrCP0xQO-q48kjmA"
# आपकी Vercel डिप्लॉयमेंट लिंक (बिना आखिरी slash के) - उदा: https://your-project.vercel.app
# नोट: डिप्लॉय होने के बाद आपको यह URL यहाँ अपडेट करना होगा
WEBHOOK_URL = "https://your-project-name.vercel.app" 

API_URL = "https://jwt-id-token.vercel.app/api/token"

# बोट और एपीआई इनिशियलाइजेशन
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = FastAPI()

# टोकन जनरेट करने और फाइल भेजने का कॉमन फंक्शन
def process_and_send_token(message, uid, password):
    uid = uid.strip()
    password = password.strip()
    
    # यूजर को स्टेटस बताना
    status_msg = bot.reply_to(message, "⏳ टोकन जनरेट किया जा रहा है, कृपया प्रतीक्षा करें...")
    
    params = {'uid': uid, 'password': password}
    
    try:
        response = requests.get(API_URL, params=params, timeout=15)
        
        if response.status_code == 200:
            token_data = response.text.strip()
            
            if token_data:
                file_name = f"token_{uid}.txt"
                
                # टोकन को फाइल में सेव करना (/tmp/ फोल्डर का उपयोग Vercel के लिए ज़रूरी है)
                temp_path = os.path.join("/tmp", file_name)
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(token_data)
                
                # फाइल भेजना
                with open(temp_path, "rb") as f:
                    bot.send_document(
                        message.chat.id, 
                        f, 
                        caption=f"✅ **टोकन सफलतापूर्वक जनरेट हो गया है!**\n\n👤 UID: `{uid}`",
                        reply_to_message_id=message.message_id
                    )
                
                # फाइल डिलीट करना
                os.remove(temp_path)
                bot.delete_message(message.chat.id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ API से खाली रिस्पॉन्स मिला।", message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text(f"❌ API एरर! स्टेटस कोड: {response.status_code}", message.chat.id, status_msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ समस्या आई: {str(e)}", message.chat.id, status_msg.message_id)

# Webhook रूट (Vercel इसी पर टेलीग्राम के मैसेज रिसीव करेगा)
@app.post("/webhook")
async def webhook(request: Request):
    json_str = await request.body()
    update = telebot.types.Update.de_json(json_str.decode('utf-8'))
    bot.process_new_updates([update])
    return {"status": "ok"}

# Webhook सेट करने के लिए एक सीक्रेट रूट (इसे ब्राउज़र में एक बार खोलना होगा)
@app.get("/set_webhook")
def set_webhook():
    webhook_path = f"{WEBHOOK_URL}/webhook"
    ready = bot.set_webhook(url=webhook_path)
    if ready:
        return {"status": "success", "message": f"Webhook successfully set to {webhook_path}"}
    return {"status": "failed", "message": "Webhook setup failed."}

# होम रूट (चेक करने के लिए कि सर्वर लाइव है या नहीं)
@app.get("/")
def read_root():
    return {"message": "Telegram Token Bot is Running on Vercel!"}

# --- 1. फाइल अपलोड हैंडलर ---
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.document.file_name.endswith(('.txt', '.json')):
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        content = downloaded_file.decode('utf-8')
        uid, password = None, None
        
        for line in content.split('\n'):
            line_lower = line.lower()
            if "uid=" in line_lower or "uid:" in line_lower:
                uid = line.split("=")[1].strip() if "=" in line else line.split(":")[1].strip()
            elif "password=" in line_lower or "password:" in line_lower:
                password = line.split("=")[1].strip() if "=" in line else line.split(":")[1].strip()
            elif len(line.split()) == 2 and not uid:
                parts = line.split()
                uid, password = parts[0], parts[1]

        if uid and password:
            process_and_send_token(message, uid, password)
        else:
            bot.reply_to(message, "❌ फाइल में सही फॉर्मेट नहीं मिला। कृपया फाइल में `uid=आपका_यूआईडी` और `password=आपका_पासवर्ड` लिखें।")

# --- 2. डायरेक्ट टेक्स्ट/लिंक हैंडलर ---
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    text = message.text
    uid, password = None, None
    
    if "jwt-id-token.vercel.app" in text and "uid=" in text and "password=" in text:
        try:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(text)
            captured_params = parse_qs(parsed_url.query)
            uid = captured_params.get('uid')[0]
            password = captured_params.get('password')[0]
        except:
            pass
            
    elif len(text.split()) == 2:
        parts = text.split()
        uid, password = parts[0], parts[1]
        
    elif "uid=" in text.lower() and "password=" in text.lower():
        for item in text.split('\n'):
            if "uid=" in item.lower():
                uid = item.split('=')[1].strip()
            if "password=" in item.lower():
                password = item.split('=')[1].strip()

    if uid and password:
        process_and_send_token(message, uid, password)
    else:
        if text != "/start":
            bot.reply_to(message, "ℹ️ फॉर्मेट समझ नहीं आया! आप `uid password` टेक्स्ट भेज सकते हैं या `.txt` फाइल अपलोड कर सकते हैं।")
