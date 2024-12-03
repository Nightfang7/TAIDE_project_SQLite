from flask import Flask, render_template, request, jsonify
import speech_recognition as sr
from pydub import AudioSegment
import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import subprocess
from peft import PeftModel
import torch
from datetime import datetime, timedelta
import sqlite3
import json
from huggingface_hub import login

def init_huggingface():
    try:
        # Get token from environment variable or prompt user
        token = os.getenv('HUGGINGFACE_TOKEN')
        if not token:
            token = input("Please enter your Hugging Face token: ")
        
        # Login to Hugging Face
        login(token)
        print("Successfully logged in to Hugging Face")
    except Exception as e:
        print(f"Failed to login to Hugging Face: {e}")
        return False
    return True

# SQLite database setup
DATABASE = 'taide_records.db'

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food TEXT,
            food_quantity TEXT,
            exercise TEXT,
            exercise_quantity TEXT,
            other_info TEXT,
            record_date DATE,
            record_time TIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# FFmpeg settings remain the same
AudioSegment.converter = "C:/Users/NT/Documents/ffmpeg/bin/ffmpeg.exe"
AudioSegment.ffprobe = "C:/Users/NT/Documents/ffmpeg/bin/ffprobe.exe"

# TAIDE model initialization remains the same
BASE_MODEL = "taide/Llama3-TAIDE-LX-8B-Chat-Alpha1"
LORA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trained_extraction_model_03')
print("Model directory exists:", os.path.exists(LORA_PATH))
print("Directory contents:", os.listdir(LORA_PATH))

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

try:
    print("Loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        load_in_8bit=True,
        device_map="auto",
        use_auth_token=True  # This will use the logged in credentials
    )
except Exception as e:
    print(f"Error loading model: {e}")
    print("Please check your Hugging Face credentials and internet connection.")

print("Loading LoRA weights...")
model = PeftModel.from_pretrained(
    base_model,
    LORA_PATH,
    device_map="auto",
)
model.eval()

app = Flask(__name__)

def get_db_connection():
    """建立資料庫連接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Text processing functions remain the same
def clean_json_text(text: str) -> str:
    """清理文本中的JSON字符串"""
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1 or end == 0:
        return "{}"
    
    json_text = text[start:end]
    json_text = json_text.replace('。', '').strip()
    while '}}' in json_text:
        json_text = json_text.replace('}}', '}')
    return json_text

def extract_info_from_text(text: str) -> dict:
    """從文本中提取信息"""
    result = {
        "食物": "-",
        "食物數量": "-",
        "運動": "-",
        "運動量": "-",
        "其他關鍵資訊": "-"
    }
    
    lines = text.split('\n')
    for line in lines:
        if '"食物"' in line:
            value = line.split('"食物":')[1].strip().strip('",').strip('"')
            if value and value != "無" and value != "無法識別":
                result['食物'] = value
        elif '"食物數量"' in line:
            value = line.split('"食物數量":')[1].strip().strip('",').strip('"')
            if value and value != "無" and value != "無法識別":
                result['食物數量'] = value
        elif '"運動"' in line:
            value = line.split('"運動":')[1].strip().strip('",').strip('"')
            if value and value != "無" and value != "無法識別":
                result['運動'] = value
        elif '"運動量"' in line:
            value = line.split('"運動量":')[1].strip().strip('",').strip('"')
            if value and value != "無" and value != "無法識別":
                result['運動量'] = value
        elif '"其他關鍵資訊"' in line:
            value = line.split('"其他關鍵資訊":')[1].strip().strip('",').strip('"')
            if value and value != "無" and value != "無法識別":
                result['其他關鍵資訊'] = value
    
    return result

def process_with_model(text: str) -> dict:
    """使用微調後的模型處理文本"""
    prompt = (
        "請從以下句子中提取飲食和運動信息，並按照指定格式輸出。\n"
        f"句子：{text}\n"
        "請提取以下信息：\n"
        "1. 食物（如有多項用頓號、分隔）\n"
        "2. 食物數量\n"
        "3. 運動種類\n"
        "4. 運動時間\n"
        "5. 其他關鍵信息\n"
        "輸出格式：\n"
    )
    
    inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=1024,
            num_return_sequences=1,
            temperature=0.1,
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    try:
        json_text = clean_json_text(decoded)
        result = json.loads(json_text)
    except json.JSONDecodeError:
        print(f"JSON解析失敗，原始輸出: {decoded}")
        result = extract_info_from_text(decoded)
    
    final_result = {
        "Food": result.get("食物", "-").replace("無", "-"),
        "Food Quantity": result.get("食物數量", "-").replace("無", "-"),
        "Exercise": result.get("運動", "-").replace("無", "-"),
        "Exercise Quantity": result.get("運動量", "-").replace("無", "-"),
        "Other Key Info": result.get("其他關鍵資訊", "-").replace("無", "-")
    }
    
    return final_result

def save_to_db(data):
    """保存記錄到SQLite資料庫"""
    conn = get_db_connection()
    
    record_date = data.get('record_date', datetime.now().date())
    current_time = datetime.now().time()
    
    query = """
    INSERT INTO records (
        food, food_quantity, exercise, exercise_quantity, 
        other_info, record_date, record_time
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        data['Food'],
        data['Food Quantity'],
        data['Exercise'],
        data['Exercise Quantity'],
        data['Other Key Info'],
        record_date,
        current_time.strftime('%H:%M:%S')
    )
    
    try:
        conn.execute(query, values)
        conn.commit()
    except Exception as err:
        print(f"Error saving to database: {err}")
        raise
    finally:
        conn.close()

# Routes remain largely the same, just updating the database operations
@app.route('/')
def index():
    return render_template('index4.html')

@app.route('/recognize', methods=['POST'])
def recognize_audio():
    if 'audio' not in request.files:
       return jsonify({'error': 'No audio file uploaded'}), 400

    audio_file = request.files['audio']
    webm_path = "temp_audio.webm"
    wav_path = "temp_audio.wav"
    
    with open(webm_path, "wb") as f:
        f.write(audio_file.read())

    try:
        subprocess.run([
            "C:/Users/NT/Documents/ffmpeg/bin/ffmpeg.exe",
            "-i", webm_path,
            "-ar", "16000",
            "-ac", "1",
            wav_path
        ], check=True)

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-TW")
            return jsonify({'text': text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(webm_path):
            os.remove(webm_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)


@app.route('/process_taide', methods=['POST'])
def process_taide():
    print("Received request data:", request.get_data())  # Debug raw request data
    data = request.get_json()
    print("Parsed JSON data:", data)  # Debug parsed data
    user_text = data.get('text', '')

    print("Extracted text:", user_text)  # for debugging
    
    if not user_text:
        print("Empty text received")  # for debugging
        return jsonify({'error': '請輸入文字'}), 400

    try:
        result = process_with_model(user_text)
        print("Processing result:", result)  # for debugging
        return jsonify({'output': result})
    except Exception as e:
        print("Processing error:", str(e))  # for debugging
        return jsonify({'error': f'處理錯誤: {str(e)}'}), 500

@app.route('/save_record', methods=['POST'])
def save_record():
    """保存編輯後的記錄"""
    try:
        data = request.get_json()
        save_to_db(data)
        return jsonify({'message': '記錄保存成功'})
    except Exception as e:
        return jsonify({'error': f'保存錯誤: {str(e)}'}), 500

@app.route('/get_records_by_date/<date>')
def get_records_by_date(date):
    """獲取指定日期的記錄"""
    conn = get_db_connection()
    
    try:
        query = """
        SELECT id, food, food_quantity, exercise, exercise_quantity, 
               other_info, record_date, record_time 
        FROM records 
        WHERE DATE(record_date) = ? 
        ORDER BY record_time DESC
        """
        cursor = conn.execute(query, (date,))
        records = cursor.fetchall()
        
        # Convert to list of dicts
        records = [dict(record) for record in records]
        
        # Format dates and times
        for record in records:
            record['record_date'] = record['record_date']
            record['record_time'] = record['record_time']
        
        return jsonify(records)
    except Exception as err:
        return jsonify({'error': f'Database error: {str(err)}'}), 500
    finally:
        conn.close()

@app.route('/update_record/<int:record_id>', methods=['POST'])
def update_record(record_id):
    data = request.get_json()
    conn = get_db_connection()
    
    try:
        query = """
        UPDATE records 
        SET food = ?, food_quantity = ?, exercise = ?, 
            exercise_quantity = ?, other_info = ?
        WHERE id = ?
        """
        values = (
            data['Food'],
            data['Food Quantity'],
            data['Exercise'], 
            data['Exercise Quantity'],
            data['Other Key Info'],
            record_id
        )
        conn.execute(query, values)
        conn.commit()
        return jsonify({'message': 'Updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/delete_record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    conn = get_db_connection()
    
    try:
        conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        return jsonify({'message': 'Deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Initialize database when starting the app
with app.app_context():
    init_db()

if __name__ == "__main__":
    print("Current working directory:", os.getcwd())
    print("LORA path absolute:", os.path.abspath(LORA_PATH))
    try:
        print("Starting TAIDE Assistant...")
        with app.app_context():
            init_db()
        if init_huggingface():
            app.run(debug=True)
        else:
            print("Failed to initialize. Please check your Hugging Face token.")
    except Exception as e:
        print(f"Error starting application: {e}")
        import time
        time.sleep(30)  # Keep window open for 10 seconds to read error