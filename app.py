import subprocess
import sys
import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, send
import requests
from dotenv import load_dotenv
from werkzeug.serving import run_simple

# Konfigurē reģistrēšanu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Funkcija, kas pārbauda un instalē nepieciešamās bibliotēkas
def install_requirements():
    try:
        import flask
        import flask_socketio
        import requests
        import dotenv
        logger.info("Visas nepieciešamās bibliotēkas ir jau instalētas.")
    except ImportError as e:
        logger.warning(f"Nepieciešamās bibliotēkas netika atrastas: {e}")
        try:
            logger.info("Instalējam nepieciešamās bibliotēkas...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            logger.info("Visas nepieciešamās bibliotēkas ir instalētas!")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kļūda instalējot bibliotēkas: {e}")
            sys.exit(1)

# Instalējam bibliotēkas, ja nepieciešams
install_requirements()

# Ielādē vides mainīgos no .env faila
load_dotenv()

# Iegūst API atslēgu un citus iestatījumus no .env faila
GPT_API_KEY = os.getenv("GPT_API_KEY")
GPT_API_URL = os.getenv("GPT_API_URL", "https://api.openai.com/v1/chat/completions")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-3.5-turbo")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 150))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

# Pārbauda, vai API atslēga ir pieejama
if not GPT_API_KEY:
    logger.error("❌ API Key not found! Check your .env file and make sure GPT_API_KEY is set.")
    sys.exit(1)

# Sarunas vēstures saglabāšana
conversation_history = {}

# Funkcija teksta fragmentu meklēšanai atsevišķās mapēs
def search_in_text_files(query):
    logger.info(f"Meklējam teksta fragmentos pēc vaicājuma: {query}")
    query_words = query.lower().split()
    results = []
    
    # Mapju saraksts, kurās meklēt
    folders = [
        "pdf_chunks_part1", 
        "pdf_chunks_part2", 
        "pdf_chunks_part3", 
        "pdf_chunks_part4", 
        "pdf_chunks_part5",
        "pdf_chunks_part6",
        "pdf_chunks_part7",
        "pdf_chunks_part8",
        "pdf_chunks_part9"
    ]
    
    try:
        # Meklējam katrā mapē
        for folder in folders:
            folder_path = os.path.join(os.getcwd(), folder)
            
            if not os.path.exists(folder_path):
                logger.warning(f"Mape {folder_path} netika atrasta, izlaižam")
                continue
                
            logger.info(f"Meklējam mapē: {folder_path}")
            
            # Meklējam visos teksta failos šajā mapē
            for filename in os.listdir(folder_path):
                if filename.endswith(".txt"):
                    filepath = os.path.join(folder_path, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read().lower()
                            
                            # Vienkārša atbilstības noteikšana - skaitām atbilstošos vārdus
                            match_count = sum(1 for word in query_words if word in content)
                            
                            if match_count > 0:
                                results.append({
                                    "file": f"{folder}/{filename}",
                                    "content": content,
                                    "score": match_count / len(query_words)
                                })
                                logger.debug(f"Atrasts atbilstošs fragments: {folder}/{filename} (score: {match_count / len(query_words)})")
                    except Exception as e:
                        logger.error(f"Kļūda lasot failu {filepath}: {e}")
        
        # Sakārtojam rezultātus pēc atbilstības
        results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Kopā atrasti {len(results)} atbilstoši fragmenti")
        # Atgriežam labākos 3 rezultātus
        return results[:3]
    except Exception as e:
        logger.error(f"Kļūda meklējot teksta fragmentos: {e}")
        return []

# Izveido Flask lietotni
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Trūkst 'message' lauka pieprasījumā"}), 400
    
    user_id = data.get("user_id", "default_user")
    response = chatbot_response(data["message"], user_id)
    return jsonify({"response": response})

@socketio.on('message')
def handle_message(msg):
    try:
        # Ja ziņojums ir JSON objekts ar user_id
        if isinstance(msg, dict) and "message" in msg and "user_id" in msg:
            user_id = msg["user_id"]
            message = msg["message"]
        else:
            # Ja ziņojums ir vienkāršs teksts
            user_id = request.sid  # Izmanto sesijas ID kā lietotāja ID
            message = msg
        
        response = chatbot_response(message, user_id)
        send(response, broadcast=False, room=request.sid)
    except Exception as e:
        logger.error(f"Kļūda apstrādājot ziņojumu: {e}")
        send("Diemžēl radās kļūda apstrādājot jūsu ziņojumu.", broadcast=False, room=request.sid)

def chatbot_response(text, user_id="default_user"):
    # Meklējam relevantos fragmentus
    relevant_chunks = search_in_text_files(text)
    context = "\n\n".join([chunk["content"] for chunk in relevant_chunks])
    
    # Inicializē lietotāja vēsturi, ja tā vēl nav
    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {"role": "system", "content": "Jūs esat COFOG asistents, kas palīdz ar jautājumiem par valsts funkciju klasifikāciju. Izmantojiet tikai sniegto kontekstu, lai atbildētu uz jautājumiem par COFOG. Ja atbilde nav atrodama kontekstā, jūs varat izmantot savas vispārīgās zināšanas, bet norādiet, ka tas nebalstās uz COFOG dokumentiem."}
        ]
    
    # Pievieno lietotāja ziņojumu vēsturei
    conversation_history[user_id].append({"role": "user", "content": text})
    
    # Ierobežojam vēstures garumu (saglabājam sistēmas ziņojumu + pēdējos 10 ziņojumus)
    if len(conversation_history[user_id]) > 11:
        conversation_history[user_id] = [conversation_history[user_id][0]] + conversation_history[user_id][-10:]
    
    # Ja atrasti fragmenti, pievieno tos kā kontekstu
    if context:
        logger.info(f"Pievienojam kontekstu no {len(relevant_chunks)} fragmentiem")
        conversation_history[user_id].append({"role": "system", "content": 
            f"Šī ir informācija no mūsu COFOG dokumentiem, kas var palīdzēt atbildēt uz lietotāja jautājumu. "
            f"Izmantojiet šo kontekstu, lai sniegtu precīzu atbildi:\n\n{context}"})
    else:
        logger.info("Nav atrasts neviens atbilstošs fragments kontekstam")
    
    headers = {
        "Authorization": f"Bearer {GPT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": GPT_MODEL,
        "messages": conversation_history[user_id],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }
    
    try:
        response = requests.post(GPT_API_URL, headers=headers, json=payload, timeout=30)
        response_data = response.json()
        
        if response.status_code != 200:
            logger.error(f"API kļūda: {response_data}")
            return "Diemžēl radās kļūda sazinoties ar asistentu. Lūdzu, mēģiniet vēlāk."
        
        assistant_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if assistant_response:
            # Pievieno asistenta atbildi vēsturei
            conversation_history[user_id].append({"role": "assistant", "content": assistant_response})
            return assistant_response
        else:
            logger.warning("Tukša atbilde no API")
            return "Neizdevās saņemt atbildi. Lūdzu, mēģiniet vēlāk."
    
    except requests.exceptions.Timeout:
        logger.error("API pieprasījuma timeout")
        return "Pieprasījuma laiks beidzās. Lūdzu, mēģiniet vēlāk."
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Savienojuma kļūda: {e}")
        return "Radās kļūda savienojoties ar asistentu. Lūdzu, pārbaudiet interneta savienojumu un mēģiniet vēlāk."
    
    except Exception as e:
        logger.error(f"Neparedzēta kļūda: {e}")
        return "Radās neparedzēta kļūda. Lūdzu, mēģiniet vēlāk."

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/reset', methods=['POST'])
def reset_conversation():
    data = request.get_json()
    user_id = data.get("user_id", "default_user")
    
    if user_id in conversation_history:
        # Saglabājam tikai sistēmas ziņojumu
        system_message = next((msg for msg in conversation_history[user_id] if msg["role"] == "system"), None)
        if system_message:
            conversation_history[user_id] = [system_message]
        else:
            conversation_history[user_id] = [{"role": "system", "content": "Jūs esat COFOG asistents, kas palīdz ar jautājumiem par valsts funkciju klasifikāciju."}]
    
    return jsonify({"status": "success", "message": "Saruna atiestatīta"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    
    logger.info(f"Startējam serveri uz {host}:{port}, debug={debug}")
    socketio.run(app, host=host, port=port, debug=debug)
