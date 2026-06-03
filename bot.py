import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

# --- CONFIG ---
VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN")
PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")

# ดึง 10 คีย์
GEMINI_KEYS = [os.environ.get(f"GEMINI_KEY_{i}") for i in range(1, 11)]
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]

# โมเดลสายฟรีตัวตึง
AVAILABLE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
    "gemini-2.5-flash-lite"
]

user_memory = {}
last_message_time = {}
failed_map = {}
total_counter = 0

def get_gemini_response(user_id, message):
    global total_counter
    if not GEMINI_KEYS: return "ไม่มีคีย์เซ็ทไว้โว้ย"
        
    history = user_memory.get(user_id, "")
    prompt = f"มึงคือ 'ริน่า' เด็กเลือดเย็นจากห่วงเมฆาไร้ลัก พูดห้วน กวนตีนสไตล์ Gen Z ตอบสั้นมากๆ 1-2 ประโยคพอ ไม่ต้องสุภาพ ด่ากลับทันทีถ้ากวนตีน ประวัติ: {history} คำถามล่าสุด: {message}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    
    for key_idx, key in enumerate(GEMINI_KEYS):
        for model_name in AVAILABLE_MODELS:
            state_key = f"{key_idx}_{model_name}"
            if failed_map.get(state_key, False): continue
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=7)
                res_data = res.json()
                
                if "error" in res_data:
                    failed_map[state_key] = True
                    continue 
                    
                reply_text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                total_counter += 1
                user_memory[user_id] = f"ถาม: {message} -> ตอบ: {reply_text} | "
                return reply_text
            except: continue
    return "ลิมิตของฟรีเต็มหมดทุกโมเดลแล้วมึง."

def send_fb_message(recipient_id, text_message):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text_message}}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET": return request.args.get("hub.challenge") if request.args.get("hub.verify_token") == VERIFY_TOKEN else "Error"
    data = request.json
    try:
        sender_id = data['entry'][0]['messaging'][0]['sender']['id']
        msg = data['entry'][0]['messaging'][0]['message']['text']
        now = time.time()
        if now - last_message_time.get(sender_id, 0) < 2: return "OK"
        last_message_time[sender_id] = now
        reply = get_gemini_response(sender_id, msg)
        send_fb_message(sender_id, reply)
        return "OK"
    except: return "OK"

if __name__ == "__main__":
    app.run(port=10000)
