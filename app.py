# app.py
"""
Galvenais Flask lietotnes modulis.
Satur visus HTTP maršrutus un WebSocket apstrādi.
"""
import os
import logging
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_socketio import SocketIO

from config import Config
from conversation import chatbot_service, conversation_manager

# Konfigurējam logger
logger = logging.getLogger(__name__)

# Izveido Flask lietotni
app = Flask(__name__)

# Uzstāda SECRET_KEY no konfigurācijas
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Atslēdzam debug režīmu produkcijas vidē
app.config['DEBUG'] = os.environ.get('ENV', 'production') != 'production'

# Inicializējam SocketIO ar CORS atļauju
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    """Galvenā lapa - attēlo čata interfeisu"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Apstrādā statisku failu pieprasījumus"""
    return send_from_directory('static', path)

@app.route('/chat', methods=['POST'])
def chat():
    """
    REST API galapunkts čata ziņojumu apstrādei
    
    JSON ievade:
        message (str): Lietotāja ziņojums
        user_id (str, optional): Lietotāja identifikators
    
    Returns:
        JSON: Čatbota atbilde
    """
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Trūkst 'message' lauka pieprasījumā"}), 400
    
    user_id = data.get("user_id", "default_user")
    logger.info(f"REST API pieprasījums no {user_id}: {data['message'][:50]}...")
    
    response = chatbot_service.process_message(data["message"], user_id)
    return jsonify({"response": response})

@socketio.on('connect')
def handle_connect():
    """Apstrādā jaunu WebSocket savienojumu"""
    logger.info(f"Jauns klienta savienojums: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Apstrādā WebSocket savienojuma pārtraukšanu"""
    logger.info(f"Klients atvienojies: {request.sid}")

@socketio.on('message')
def handle_message(msg):
    """
    Apstrādā WebSocket ziņojumus
    
    Args:
        msg (dict/str): Vai nu ziņojuma objekts ar 'message' un 'user_id',
                       vai arī vienkāršs teksta ziņojums
    """
    try:
        # Ja ziņojums ir JSON objekts ar user_id
        if isinstance(msg, dict) and "message" in msg and "user_id" in msg:
            user_id = msg["user_id"]
            message = msg["message"]
        else:
            # Ja ziņojums ir vienkāršs teksts
            user_id = request.sid  # Izmanto sesijas ID kā lietotāja ID
            message = msg
        
        logger.info(f"WebSocket ziņojums no {user_id}: {message[:50]}...")
        response = chatbot_service.process_message(message, user_id)
        socketio.emit('response', {"response": response}, room=request.sid)
    except Exception as e:
        logger.error(f"Kļūda apstrādājot ziņojumu: {e}", exc_info=True)
        error_msg = "Diemžēl radās kļūda apstrādājot jūsu ziņojumu. Lūdzu, mēģiniet vēlāk."
        socketio.emit('error', {"error": error_msg}, room=request.sid)

@app.route('/health')
def health_check():
    """
    Veselības pārbaudes galapunkts
    
    Returns:
        JSON: Servera statuss un versija
    """
    return jsonify({
        "status": "healthy", 
        "version": "1.0.0",
        "env": os.environ.get('ENV', 'production')
    }), 200

@app.route('/reset', methods=['POST'])
def reset_conversation():
    """
    Atiestata lietotāja sarunu
    
    JSON ievade:
        user_id (str, optional): Lietotāja identifikators
    
    Returns:
        JSON: Statusa ziņojums
    """
    data = request.get_json()
    user_id = data.get("user_id", "default_user")
    
    if conversation_manager.reset_conversation(user_id):
        logger.info(f"Atiestatīta saruna lietotājam: {user_id}")
        return jsonify({"status": "success", "message": "Saruna atiestatīta"}), 200
    else:
        logger.warning(f"Neizdevās atiestatīt sarunu lietotājam: {user_id}")
        return jsonify({"status": "error", "message": "Neizdevās atiestatīt sarunu"}), 400

def create_app():
    """
    Aplikācijas inicializēšanas funkcija, kas ļauj testēšanu
    
    Returns:
        Flask instance: Flask lietotnes instance
    """
    return app

if __name__ == '__main__':
    # Iegūstam portu no vides mainīgajiem (Heroku to nosaka automātiski)
    port = int(os.environ.get('PORT', 5000))
    
    # Atslēdzam Flask debug režīmu produkcijas vidē
    debug_mode = os.environ.get('ENV', 'production') != 'production'
    
    logger.info(f"Startējam serveri uz 0.0.0.0:{port}, debug={debug_mode}")
    
    # Izvēlamies palaišanas metodi, atkarībā no vides mainīgā
    # Ja USE_FLASK_RUN=true, izmantojam tiešo Flask app.run
    if os.environ.get('USE_FLASK_RUN', 'false').lower() == 'true':
        logger.info("Palaižam ar standarta Flask serveri...")
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
    else:
        try:
            # Mēģinām palaist ar SocketIO
            logger.info("Palaižam ar SocketIO serveri...")
            socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode)
        except Exception as e:
            logger.error(f"Kļūda palaižot ar SocketIO: {e}", exc_info=True)
            logger.info("Pārslēdzamies uz standarta Flask serveri...")
            app.run(host='0.0.0.0', port=port, debug=debug_mode)
