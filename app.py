import subprocess
import sys
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, send
import requests
import os
from dotenv import load_dotenv
from werkzeug.serving import run_simple

# Funkcija, kas pārbauda un instalē nepieciešamās bibliotēkas
def install_requirements():
    try:
        import flask
        import flask_socketio
        import requests
        import dotenv
    except ImportError:
        print("Nepieciešamās bibliotēkas netika atrastas. Instalējam tās...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Visas nepieciešamās bibliotēkas ir instalētas!")

install_requirements()

# Ielādē vides mainīgos no .env faila
load_dotenv()

# Iegūst API atslēgu no .env faila
GPT_API_KEY = os.getenv("GPT_API_KEY")
GPT_API_URL = "https://api.openai.com/v1/chat/completions"

# Pārbauda, vai API atslēga ir pieejama
if not GPT_API_KEY:
    print("❌ API Key not found! Check your .env file and make sure GPT_API_KEY is set.")
    exit(1)

# Izveido Flask lietotni
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Pievienots cors_allowed_origins

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Trūkst 'message' lauka pieprasījumā"}), 400
    return jsonify({"response": chatbot_response(data["message"])})

@socketio.on('message')
def handle_message(msg):
    response = chatbot_response(msg)
    send(response, broadcast=True)

def chatbot_response(text):
    headers = {
        "Authorization": f"Bearer {GPT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 100,
        "temperature": 0.7
    }
    try:
        response = requests.post(GPT_API_URL, headers=headers, json=payload)
        response_data = response.json()
        if response.status_code != 200:
            print(f"API Error: {response_data}")  # Pievienota kļūdu reģistrēšana
            return "API kļūda!"
        return response_data.get("choices", [{}])[0].get("message", {}).get("content", "Neizdevās saņemt atbildi.")
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")  # Pievienota kļūdu reģistrēšana
        return "Savienojuma kļūda ar API."

if __name__ == '__main__':
    try:
        port = int(os.getenv('PORT', 5000))
        socketio.run(app, 
                    host='0.0.0.0',
                    port=port,
                    allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Error starting server: {e}")