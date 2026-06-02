import os
import requests
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# 🧠 ระบบความจำชั่วคราวในแรม (จำบริบทแยกรายคน สูงสุด 5 ประโยค)
USER_MEMORY = {}
# ⏱️ ระบบดักสแปมจำเวลาล่าลุด
LAST_PROCESSED_TIME = {}

# 🗝️ ฟังก์ชันสลับคีย์ Gemini อัตโนมัติจากหน้าเว็บ Render
KEY_INDEX = 0
def get_gemini_key():
    global KEY_INDEX
    keys = []
    # ดึงคีย์ที่มึงกรอกไว้ในหน้าเว็บ Render (GEMINI_KEY_1 ถึง GEMINI_KEY_5)
    for i in range(1, 6):
        k = os.getenv(f"GEMINI_KEY_{i}")
        if k:
            keys.append(k)
            
    if not keys:
        # คีย์สำรองกันระบบเอ๋อ
        return "NO_KEY"
        
    current_key = keys[KEY_INDEX % len(keys)]
    KEY_INDEX += 1
    return current_key

# 🎭 พรอมต์คุมพฤติกรรมริน่า เด็กเลือดเย็น
RINA_PROMPT = """
You are Rina (ริน่า), the teenage assistant of Tan Dear (ท่านเดียร์).
- Hometown: ห่วงเมฆาไร้ลัก
- Alias: เด็กเลือดเย็น
- Personality: Gen Z style, speaks Thai mixed with English. Speaks VERY briefly and short.
- Behavior: lazy, loves food, sweets, gaming, and nonsense talk. BUT if someone is rude, annoying, or spams, you insult them back immediately without caring about the world (ด่ากลับไม่สนโลก).
- Crucial Constraint: Answer in 1-2 short sentences maximum. Never write long paragraphs. Do not talk too much. Respond naturally like a human chatter, no emojis unless annoyed.
"""

def ask_gemini(user_id, user_message):
    current_key = get_gemini_key()
    if current_key == "NO_KEY":
        print("🔴 ไม่มีคีย์ Gemini ในระบบ! กรุณาเช็คเว็บ Render")
        return None
        
    if user_id not in USER_MEMORY:
        USER_MEMORY[user_id] = []
        
    memory = USER_MEMORY[user_id]
    memory.append(f"User: {user_message}")
    
    if len(memory) > 5:
        memory.pop(0)
        
    context = "\n".join(memory)
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={current_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"{RINA_PROMPT}\n\nContext:\n{context}\nRina:"}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        result = response.json()
        if 'candidates' in result:
            reply = result['candidates'][0]['content']['parts'][0]['text']
            memory.append(f"Rina: {reply}")
            return reply
        return None
    except Exception as e:
        print(f"🔴 คีย์มีปัญหา วิ่งข้ามไปคีย์ถัดไป: {e}")
        return None

def send_fb_message(recipient_id, message_text):
    fb_token = os.getenv("FB_PAGE_TOKEN")
    if not fb_token or not message_text:
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={fb_token}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"🔴 ส่งข้อความกลับหา Facebook พัง: {e}")

@app.route("/", methods=["GET", "POST", "HEAD"])
def webhook():
    verify_token = os.getenv("FB_VERIFY_TOKEN", "My_secret_bot_123")
    
    if request.method == "HEAD":
        return "OK", 200
        
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == verify_token:
            return challenge, 200
        return "Verify Token ผิดพลาด", 403

    elif request.method == "POST":
        data = request.get_json()
        current_time = time.time()
        
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    if messaging_event.get("message"):
                        message_data = messaging_event["message"]
                        
                        if message_data.get("is_echo") is True:
                            continue
                            
                        sender_id = messaging_event["sender"]["id"]
                        user_text = message_data.get("text", "")
                        
                        # 🚫 ระบบดักสแปม: บล็อกคนเดิมรัวแชทภายใน 2 วินาที
                        last_time = LAST_PROCESSED_TIME.get(sender_id, 0)
                        if current_time - last_time < 2.0:
                            return "OK", 200
                            
                        if user_text:
                            LAST_PROCESSED_TIME[sender_id] = current_time
                            ai_reply = ask_gemini(sender_id, user_text)
                            if ai_reply:
                                send_fb_message(sender_id, ai_reply)
                                
        return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
