# app_run.py
# Šis fails ir paredzēts darbināšanai Heroku vidē
# Tas importē app.py un konfigurē dažus parametrus

import os
import eventlet
eventlet.monkey_patch()  # Monkey patch vispirms

from app import app, socketio

if __name__ == '__main__':
    # Iegūstam portu no vides mainīgajiem (Heroku to nosaka automātiski)
    port = int(os.environ.get('PORT', 5000))
    
    # Palaiž SocketIO serveri ar atbilstošo portu
    # Heroku vidē izmanto 0.0.0.0 adresi, lai klausītos visus savienojumus
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
