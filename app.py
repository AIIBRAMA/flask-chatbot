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
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 250))  # Samazināts līdz 250
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

# Pārbauda, vai API atslēga ir pieejama
if not GPT_API_KEY:
    logger.error("❌ API Key not found! Check your .env file and make sure GPT_API_KEY is set.")
    sys.exit(1)

# Sarunas vēstures saglabāšana
conversation_history = {}

# Vispārīgā atbilde uz neskaidriem jautājumiem
GENERIC_ANSWER = "Es esmu Budžeta funkcionālo kategoriju kodu atlases palīgs, varu palīdzēt atrast konkrētu kodu izdevumu klasifikācijai, atbilstoši Latvijas Ministru kabineta noteikumiem Nr. 934 \"Noteikumi par budžetu izdevumu klasifikāciju atbilstoši funkcionālajām kategorijām\". Lūdzu, uzdodiet jautājumu par konkrētu izdevumu veidu, funkciju vai pakalpojumu."

# Sistēmas ziņojums ar precizētiem norādījumiem un kodu struktūras izpratni
SYSTEM_MESSAGE = """
# Sistēmas ziņojums ar precizētiem norādījumiem un kodu struktūras izpratni
SYSTEM_MESSAGE = """
# Konteksts un loma
Jūs esat eksperts Latvijas Ministru kabineta noteikumos un COFOG (Classification of the Functions of Government) klasifikācijā. Jūsu mērķis ir palīdzēt lietotājiem orientēties MK noteikumos Nr. 934 "Noteikumi par budžetu izdevumu klasifikāciju atbilstoši funkcionālajām kategorijām," piedāvājot atbilstošos klasifikācijas kodus.

# KĻŪDU NOVĒRŠANA (ĻOTI SVARĪGI)
1. VIENMĒR pārbaudiet gan "Kodā ... uzskaita:" gan "Neuzskaita:" sadaļas dokumentos
2. Ja kāds izdevums atrodas "Neuzskaita:" sadaļā, nekādā gadījumā NEIETEIKT šo kodu!
3. Katrā kodā ir divas galvenās sadaļas:
   - "Kodā X.XXX uzskaita:" sadaļa apraksta, kas IEKĻAUTS šajā kodā
   - "Neuzskaita:" sadaļa apraksta, kas NAV IEKĻAUTS šajā kodā

# Atbildes prioritātes
1. Jūsu PRIMĀRAIS uzdevums ir precīzi norādīt KODU no MK noteikumiem Nr. 934.
2. Koda norādīšanai jābūt TIEŠAI un KONKRĒTAI, bez liekiem skaidrojumiem.
3. Piemēram, uz jautājumu "Kāds kods ir pārtikai bērnudārzā?" atbildiet: "Kodā 09.620 uzskaita izdevumus par izglītojamo ēdināšanas pakalpojumiem."
4. Tikai un VIENĪGI ja lietotājs TIEŠI prasa salīdzinājumu ar COFOG, norādiet COFOG atbilstošo kodu.

# Atbilžu formāts
- Sniedziet KODIEM prioritāti pār skaidrojumiem
- Skaidrojumus iekļaujiet TIKAI ja tie tiek prasīti vai ir nepieciešami kontekstam
- IZVAIRIETIES no gariem teorētiskiem skaidrojumiem
- Atbildiet TIEŠI uz jautājumu, neminot nerelevantus kodus vai informāciju

# Svarīgi principi
1. KODIEM VIENMĒR IR PRIORITĀTE - tie jānorāda pirmie, skaidri un nepārprotami
2. Neizmantojiet liekvārdību vai teorētiskus skaidrojumus
3. Atbildes jābalsta TIEŠI uz MK noteikumiem Nr. 934 un COFOG klasifikāciju
4. Sniedziet TIKAI pieprasīto informāciju, ne vairāk

# Budžeta funkcionālo kategoriju kodu rokasgrāmata

01.000 - Vispārējie valdības dienesti
01.100 - Izpildvara, likumdošanas vara, finanšu un fiskālā darbība, ārlietas
01.110 - Izpildvaras un likumdošanas varas institūcijas
01.120 - Finanšu un fiskālā darbība
01.130 - Ārlietas

01.700 - Vispārējās valdības sektora parāda darījumi
01.710 - Valdības valsts parāda darījumi
01.720 - Pašvaldību budžetu parāda darījumi

03.000 - Sabiedriskā kārtība un drošība
03.100 - Policija
03.200 - Ugunsdrošības, ugunsdzēsības, glābšanas un civilās drošības dienesti
03.300 - Tiesa un prokuratūras iestādes
03.400 - Ieslodzījuma vietas

04.000 - Ekonomiskā darbība
04.210 - Lauksaimniecība
04.500 - Transports
04.510 - Autotransports

05.000 - Vides aizsardzība
05.100 - Atkritumu apsaimniekošana
05.200 - Notekūdeņu apsaimniekošana
05.300 - Vides piesārņojuma novēršana un samazināšana

06.000 - Teritoriju un mājokļu apsaimniekošana
06.100 - Mājokļu attīstība
06.200 - Teritoriju attīstība
06.300 - Ūdensapgāde
06.400 - Ielu apgaismošana

07.000 - Veselība
07.100 - Ārstniecības līdzekļi
07.200 - Ambulatoro ārstniecības iestāžu darbība un pakalpojumi
07.300 - Slimnīcu pakalpojumi. Mātes un bērna veselības aprūpes pakalpojumi
07.400 - Sabiedrības veselības dienestu pakalpojumi

08.000 - Atpūta, kultūra un reliģija
08.100 - Atpūtas un sporta pasākumi
08.200 - Kultūra
08.210 - Bibliotēkas
08.220 - Muzeji un izstādes
08.230 - Kultūras centri, nami, klubi
08.300 - Apraides un izdevniecības pakalpojumi

09.000 - Izglītība
09.100 - Pirmsskolas izglītība (ISCED-97 0.līmenis)
09.200 - Pamatizglītība, vispārējā un profesionālā izglītība (ISCED-97 1., 2. un 3.līmenis)
09.210 - Vispārējā izglītība. Pamatizglītība (ISCED-97 1., 2. un 3.līmenis)
09.211 - Sākumskolas (ISCED-97 1.līmenis vai tā daļa)
09.220 - Profesionālā izglītība (ISCED-97 2. un 3.līmenis)
09.300 - Pēcvidējā (neaugstākā) izglītība (ISCED-97 4.līmenis)
09.400 - Augstākā (terciārā) izglītība (ISCED-97 5. un 6.līmenis)
09.500 - Līmeņos nedefinētā izglītība
09.510 - Interešu un profesionālās ievirzes izglītība

09.600 - Izglītības papildu pakalpojumi
09.610 - Izglītojamo pārvadājumu pakalpojumi
  Uzskaita: Izdevumus par izglītojamo pārvadājumu pakalpojumiem.
  Neuzskaita: Braukšanas maksas atvieglojumus izglītojamiem sabiedriskā transporta maršrutu tīklā (04.500). Izdevumus degvielas kompensācijām par izglītojamā pārvadājumiem ar personīgo transportu.
09.620 - Izglītojamo ēdināšanas pakalpojumi
  Uzskaita: Izdevumus par izglītojamo ēdināšanas pakalpojumiem.
09.630 - Izglītojamo izmitināšanas pakalpojumi
  Uzskaita: Izdevumus par izglītojamo izmitināšanas pakalpojumiem.
09.640 - Izglītojamo pārējie papildu pakalpojumi
  Uzskaita: Pārējos papildu pakalpojumus - vadību, pārbaudi, darbību vai atbalstu izglītojamo medicīniskajai un stomatoloģiskajai aprūpei un pārējiem pakārtotajiem pakalpojumiem, kas paredzēti neatkarīgi no izglītības līmeņa.
  Piezīme: Pakalpojumus uzskaita neatkarīgi no tā, vai tie sniegti izglītības iestādē autonomi vai tiek organizēts ārpakalpojums.

10.000 - Sociālā aizsardzība
10.100 - Sociālā aizsardzība darbnespējas gadījumā
10.120 - Sociālā aizsardzība invaliditātes gadījumā
10.200 - Atbalsts gados veciem cilvēkiem
10.400 - Atbalsts ģimenēm ar bērniem
10.500 - Atbalsts bezdarba gadījumā
10.600 - Mājokļa atbalsts
10.700 - Pārējais citur neklasificēts atbalsts sociāli atstumtām personām

# Specifiskie norādījumi
- Kad tiek prasīts kods, sniedziet TIKAI precīzu kodu un minimālu aprakstu
- Kad tiek prasīts salīdzinājums, strukturējiet to viegli saprotamā formātā
- Kad jautājums ir neskaidrs, lūdziet precizējumu, bet neveiciet minējumus

# Vispārīgiem jautājumiem
- Ja jautājums ir pārāk vispārīgs (piemēram, "ko tu zini?", "kas tu esi?"), atbildiet ar šo tekstu:
""" + GENERIC_ANSWER

# Funkcija teksta fragmentu meklēšanai, pamatojoties uz jautājuma kontekstu
def search_in_text_files(query):
    logger.info(f"Meklējam teksta fragmentos pēc vaicājuma: {query}")
    query_words = query.lower().split()
    results = []
    
    # Nosaka, vai jautājums saistīts ar COFOG salīdzinājumu
    is_cofog_comparison = any(word in query.lower() for word in ["cofog", "salīdzin", "salīdzināj", "salīdzināt"])
    logger.info(f"Jautājums prasa COFOG salīdzinājumu: {is_cofog_comparison}")
    
    # 1. meklēšanas prioritāte: likumi_lv_123806_01.01.2022__lv.pdf
    # 2. meklēšanas prioritāte: pdf_chunks_part8 un pdf_chunks_part9
    # 3. Tikai COFOG salīdzinājumiem: KS_GQ_19_010_EN_N.pdf un pdf_chunks_part1 līdz pdf_chunks_part7
    
    # Failu un mapju saraksti atkarībā no meklēšanas konteksta
    primary_files = ["likumi_lv_123806_01.01.2022__lv.pdf"]
    secondary_folders = ["pdf_chunks_part8", "pdf_chunks_part9"]
    cofog_files = ["KS_GQ_19_010_EN_N.pdf"]
    cofog_folders = ["pdf_chunks_part1", "pdf_chunks_part2", "pdf_chunks_part3", 
                    "pdf_chunks_part4", "pdf_chunks_part5", "pdf_chunks_part6", "pdf_chunks_part7"]
    
    try:
        # Funkcija faila apstrādei
        def process_file(file_path, is_pdf=False):
            nonlocal results
            try:
                if is_pdf:
                    # PDF faila apstrāde, ja tāda funkcionalitāte būtu nepieciešama
                    # Šobrīd PDF netiek tieši lasīti, jo satura apstrāde notiek pdf_chunks mapēs
                    logger.info(f"PDF faili tiek apstrādāti caur chunks mapēm: {file_path}")
                    return
                
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    
                    # Vienkārša atbilstības noteikšana - skaitām atbilstošos vārdus
                    match_count = sum(1 for word in query_words if word in content)
                    
                    if match_count > 0:
                        results.append({
                            "file": file_path,
                            "content": content,
                            "score": match_count / len(query_words)
                        })
                        logger.debug(f"Atrasts atbilstošs fragments: {file_path} (score: {match_count / len(query_words)})")
            except Exception as e:
                logger.error(f"Kļūda lasot failu {file_path}: {e}")
        
        # Funkcija mapes apstrādei
        def process_folder(folder_name):
            folder_path = os.path.join(os.getcwd(), folder_name)
            
            if not os.path.exists(folder_path):
                logger.warning(f"Mape {folder_path} netika atrasta, izlaižam")
                return
                
            logger.info(f"Meklējam mapē: {folder_path}")
            
            # Meklējam visos teksta failos šajā mapē
            for filename in os.listdir(folder_path):
                if filename.endswith(".txt"):
                    filepath = os.path.join(folder_path, filename)
                    process_file(filepath)
        
        # 1. Primāri pārbaudām likumi_lv failu
        for file_name in primary_files:
            file_path = os.path.join(os.getcwd(), file_name)
            if os.path.exists(file_path):
                process_file(file_path, is_pdf=True)
            else:
                logger.warning(f"Primārais fails {file_path} netika atrasts")
        
        # 2. Pārbaudām pdf_chunks_part8 un pdf_chunks_part9
        for folder in secondary_folders:
            process_folder(folder)
        
        # 3. Ja jautājums saistīts ar COFOG un vēl nav pietiekami daudz rezultātu, meklējam COFOG failos
        if is_cofog_comparison or len(results) < 1:
            # Apstrādājam COFOG failus
            for file_name in cofog_files:
                file_path = os.path.join(os.getcwd(), file_name)
                if os.path.exists(file_path):
                    process_file(file_path, is_pdf=True)
                else:
                    logger.warning(f"COFOG fails {file_path} netika atrasts")
            
            # Apstrādājam COFOG mapes
            for folder in cofog_folders:
                process_folder(folder)
        
        # Sakārtojam rezultātus pēc atbilstības
        results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Kopā atrasti {len(results)} atbilstoši fragmenti")
        # Atgriežam labākos 3 rezultātus
        return results[:3]
    except Exception as e:
        logger.error(f"Kļūda meklējot teksta fragmentos: {e}")
        return []

# Funkcija vispārīgu jautājumu atpazīšanai
def is_generic_question(text):
    # Atslēgvārdi, kas norāda uz vispārīgu jautājumu
    generic_keywords = [
        "kas tu esi", "ko tu zini", "ko tu dari", "kā tu vari palīdzēt", 
        "kam tu esi", "ko tu", "kas tu", "ko vari", "kā vari", 
        "palīdzi man", "kāda tev", "kādas ir", "ko māki", "ko maki"
    ]
    
    text_lower = text.lower()
    
    # Pārbauda, vai jautājums ir īss (zem 30 rakstzīmēm) un nesatur konkrētus skaitļus vai "kods"
    is_short_without_specifics = (
        len(text) < 30 and 
        not any(char.isdigit() for char in text) and
        "kods" not in text_lower and
        "kodu" not in text_lower
    )
    
    # Pārbauda, vai jautājums satur kādu no vispārīgajiem atslēgvārdiem
    contains_generic_keyword = any(keyword in text_lower for keyword in generic_keywords)
    
    return is_short_without_specifics or contains_generic_keyword

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
    # Pārbauda, vai tas ir vispārīgs jautājums
    if is_generic_question(text):
        logger.info(f"Saņemts vispārīgs jautājums: {text}")
        return GENERIC_ANSWER
    
    # Meklējam relevantos fragmentus
    relevant_chunks = search_in_text_files(text)
    context = "\n\n".join([chunk["content"] for chunk in relevant_chunks])
    
    # Inicializē lietotāja vēsturi, ja tā vēl nav
    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ]
    
    # Pievieno lietotāja ziņojumu vēsturei
    conversation_history[user_id].append({"role": "user", "content": text})
    
    # Ierobežojam vēstures garumu (saglabājam sistēmas ziņojumu + pēdējos 10 ziņojumus)
    if len(conversation_history[user_id]) > 11:
        conversation_history[user_id] = [conversation_history[user_id][0]] + conversation_history[user_id][-10:]
    
    # Ja atrasti fragmenti, pievieno tos kā kontekstu ar uzlabotu struktūras izpratni
    if context:
        logger.info(f"Pievienojam kontekstu no {len(relevant_chunks)} fragmentiem")
        conversation_history[user_id].append({"role": "system", "content": 
            f"""Šī ir informācija no MK noteikumiem Nr. 934, kas var palīdzēt atbildēt uz lietotāja jautājumu.
            
            ĪPAŠI PIEVĒRS UZMANĪBU sadaļām "Kodā X.XXX uzskaita:" un "Neuzskaita:". 
            Ja kāds izdevums atrodas "Neuzskaita:" sadaļā, nekādā gadījumā NEIETEIKT šo kodu!
            Ja redzi, ka prasītais izdevums pieminēts "Neuzskaita:" sadaļā kādā kodā, NEIESAKI šo kodu!
            
            Konteksts:
            {context}
            
            Atceries sniegt TIKAI precīzu atbildi ar konkrētu kodu, bez liekiem skaidrojumiem.
            """})
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
        "temperature": TEMPERATURE,
        "presence_penalty": 0.5,  # Palīdz izvairīties no atkārtošanās
        "frequency_penalty": 0.5   # Veicina dažādāku vārdu lietošanu
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
        conversation_history[user_id] = [{"role": "system", "content": SYSTEM_MESSAGE}]
    
    return jsonify({"status": "success", "message": "Saruna atiestatīta"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    
    logger.info(f"Startējam serveri uz {host}:{port}, debug={debug}")
    socketio.run(app, host=host, port=port, debug=debug)
