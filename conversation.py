# conversation.py
"""
Sarunu pārvaldības modulis.
Saglabā un pārvalda lietotāju sarunas ar čatbotu.
"""
import time
import json
import logging
import requests
from config import Config, SYSTEM_MESSAGE, GENERIC_ANSWER
from search import search_engine, is_generic_question

logger = logging.getLogger(__name__)

class ConversationManager:
    """Klase sarunu pārvaldībai ar ierobežotu atmiņas patēriņu"""
    
    def __init__(self, max_users=Config.MAX_USERS, max_history_length=Config.MAX_HISTORY_LENGTH):
        """
        Inicializē sarunu pārvaldi
        
        Args:
            max_users (int): Maksimālais lietotāju skaits, kas tiek saglabāts atmiņā
            max_history_length (int): Maksimālais ziņojumu skaits, ko saglabāt katrai sarunai
        """
        self.conversations = {}
        self.max_users = max_users
        self.max_history_length = max_history_length
        self.current_time = time.time()
    
    def add_message(self, user_id, role, content):
        """
        Pievieno ziņojumu lietotāja sarunai
        
        Args:
            user_id (str): Lietotāja identifikators
            role (str): Ziņojuma loma ('user', 'assistant', 'system')
            content (str): Ziņojuma saturs
            
        Returns:
            bool: True, ja ziņojums pievienots veiksmīgi
        """
        # Inicializē lietotāja vēsturi, ja tā vēl nav
        if user_id not in self.conversations:
            # Ja sasniegts maksimālais lietotāju skaits, noņem vecāko lietotāju
            if len(self.conversations) >= self.max_users:
                self._remove_oldest_conversation()
            
            # Inicializē jaunu sarunu ar sistēmas ziņojumu
            self.conversations[user_id] = [
                {
                    "role": "system", 
                    "content": SYSTEM_MESSAGE, 
                    "timestamp": time.time()
                }
            ]
        
        # Pievieno ziņojumu ar laika zīmogu
        current_time = time.time()
        self.conversations[user_id].append({
            "role": role, 
            "content": content,
            "timestamp": current_time
        })
        
        # Ierobežojam vēstures garumu (saglabājam sistēmas ziņojumu + pēdējos N ziņojumus)
        if len(self.conversations[user_id]) > self.max_history_length + 1:
            # Saglabājam sistēmas ziņojumu un pēdējos ziņojumus
            self.conversations[user_id] = [self.conversations[user_id][0]] + self.conversations[user_id][-(self.max_history_length):]
        
        return True
    
    def get_conversation(self, user_id):
        """
        Atgriež lietotāja sarunu vēsturi
        
        Args:
            user_id (str): Lietotāja identifikators
            
        Returns:
            list: Sarunu vēstures ziņojumu saraksts bez laika zīmogiem
        """
        if user_id not in self.conversations:
            return [{"role": "system", "content": SYSTEM_MESSAGE}]
        
        # Atgriežam sarunu bez laika zīmogiem
        return [{"role": msg["role"], "content": msg["content"]} 
                for msg in self.conversations[user_id]]
    
    def reset_conversation(self, user_id):
        """
        Atiestata lietotāja sarunu, saglabājot tikai sistēmas ziņojumu
        
        Args:
            user_id (str): Lietotāja identifikators
            
        Returns:
            bool: True, ja atiestatīšana veiksmīga, citādi False
        """
        if user_id in self.conversations:
            current_time = time.time()
            self.conversations[user_id] = [
                {"role": "system", "content": SYSTEM_MESSAGE, "timestamp": current_time}
            ]
            return True
        return False
    
    def _remove_oldest_conversation(self):
        """
        Noņem vecāko sarunu, lai ietaupītu atmiņu
        
        Returns:
            bool: True, ja noņemšana veiksmīga, citādi False
        """
        if not self.conversations:
            return False
        
        # Atrod vecāko lietotāju, pamatojoties uz pēdējā ziņojuma laika zīmogu
        oldest_user = None
        oldest_timestamp = float('inf')
        
        for user_id, msgs in self.conversations.items():
            if msgs:
                last_timestamp = msgs[-1]["timestamp"]
                if last_timestamp < oldest_timestamp:
                    oldest_timestamp = last_timestamp
                    oldest_user = user_id
        
        # Noņem vecāko lietotāju
        if oldest_user:
            logger.info(f"Noņemam vecāko sarunu: {oldest_user} (pēdējā aktivitāte: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldest_timestamp))})")
            del self.conversations[oldest_user]
            return True
        
        return False

class ChatbotService:
    """Klase čatbota servisa funkcionalitātei"""
    
    def __init__(self, conversation_manager):
        """
        Inicializē čatbota servisu
        
        Args:
            conversation_manager: Sarunu pārvaldītāja instance
        """
        self.conversation_manager = conversation_manager
        self.query_processor = QueryProcessor(search_engine)
    
    def process_message(self, text, user_id="default_user"):
        """
        Apstrādā lietotāja ziņojumu un atgriež čatbota atbildi
        
        Args:
            text (str): Lietotāja ziņojums
            user_id (str): Lietotāja identifikators
            
        Returns:
            str: Čatbota atbilde
        """
        # Pārbauda, vai tas ir vispārīgs jautājums
        if is_generic_question(text):
            logger.info(f"Saņemts vispārīgs jautājums: {text}")
            return GENERIC_ANSWER
        
        # Pievieno lietotāja ziņojumu vēsturei
        self.conversation_manager.add_message(user_id, "user", text)
        
        # Iegūst kontekstu no meklēšanas
        context = self.query_processor.process_query(text)
        
        # Ja atrasts konteksts, pievieno to kā sistēmas ziņojumu
        if context:
            self.conversation_manager.add_message(user_id, "system", 
                f"""Šī ir informācija no MK noteikumiem Nr. 934, kas var palīdzēt atbildēt uz lietotāja jautājumu.
                
                ĪPAŠI PIEVĒRS UZMANĪBU sadaļām "Kodā X.XXX uzskaita:" un "Neuzskaita:". 
                Ja kāds izdevums atrodas "Neuzskaita:" sadaļā, nekādā gadījumā NEIETEIKT šo kodu!
                Ja redzi, ka prasītais izdevums pieminēts "Neuzskaita:" sadaļā kādā kodā, NEIESAKI šo kodu!
                
                Konteksts:
                {context}
                
                Atceries sniegt TIKAI precīzu atbildi ar konkrētu kodu, bez liekiem skaidrojumiem.
                """)
        
        # Iegūstam atbildi no GPT API
        response = self._get_gpt_response(user_id)
        
        # Pievieno asistenta atbildi vēsturei
        if response:
            self.conversation_manager.add_message(user_id, "assistant", response)
        
        return response
    
    def _get_gpt_response(self, user_id):
        """
        Iegūst atbildi no GPT API
        
        Args:
            user_id (str): Lietotāja identifikators
            
        Returns:
            str: GPT API atbilde vai kļūdas ziņojums
        """
        # Iegūstam visu sarunu vēsturi
        conversation_history = self.conversation_manager.get_conversation(user_id)
        
        headers = {
            "Authorization": f"Bearer {Config.GPT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": Config.GPT_MODEL,
            "messages": conversation_history,
            "max_tokens": Config.MAX_TOKENS,
            "temperature": Config.TEMPERATURE,
            "presence_penalty": 0.5,  # Palīdz izvairīties no atkārtošanās
            "frequency_penalty": 0.5   # Veicina dažādāku vārdu lietošanu
        }
        
        try:
            response = requests.post(Config.GPT_API_URL, headers=headers, json=payload, timeout=30)
            
            # Pārbauda, vai ir kļūda pieprasījumā
            if response.status_code != 200:
                try:
                    response_data = response.json()
                    logger.error(f"API kļūda: {response.status_code} - {json.dumps(response_data)}")
                    error_message = response_data.get("error", {}).get("message", "Nezināma kļūda")
                    return f"Diemžēl radās kļūda sazinoties ar asistentu: {error_message}. Lūdzu, mēģiniet vēlāk."
                except Exception:
                    logger.error(f"API kļūda: {response.status_code} - {response.text}", exc_info=True)
                    return f"Diemžēl radās kļūda sazinoties ar asistentu (Kods: {response.status_code}). Lūdzu, mēģiniet vēlāk."
            
            response_data = response.json()
            
            assistant_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if assistant_response:
                return assistant_response
            else:
                logger.warning("Tukša atbilde no API")
                return "Neizdevās saņemt atbildi. Lūdzu, mēģiniet vēlāk."
        
        except requests.exceptions.Timeout:
            logger.error("API pieprasījuma timeout")
            return "Pieprasījuma laiks beidzās. Lūdzu, mēģiniet vēlāk."
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Savienojuma kļūda: {e}", exc_info=True)
            return "Radās kļūda savienojoties ar asistentu. Lūdzu, pārbaudiet interneta savienojumu un mēģiniet vēlāk."
        
        except Exception as e:
            logger.error(f"Neparedzēta kļūda: {e}", exc_info=True)
            return "Radās neparedzēta kļūda. Lūdzu, mēģiniet vēlāk."

class QueryProcessor:
    """Klase, kas apvieno meklēšanu un vaicājumu apstrādi"""
    
    def __init__(self, search_engine):
        """
        Inicializē vaicājumu apstrādātāju
        
        Args:
            search_engine: Meklēšanas dzinēja instance
        """
        self.search_engine = search_engine
    
    def process_query(self, text):
        """
        Apstrādā vaicājumu un atgriež kontekstu
        
        Args:
            text (str): Vaicājuma teksts
            
        Returns:
            str: Konteksts atbildei vai tukša virkne, ja konteksts nav atrasts
        """
        # Pārbauda, vai tas ir vispārīgs jautājums
        if is_generic_question(text):
            logger.info(f"Saņemts vispārīgs jautājums: {text}")
            return ""
        
        # Meklējam relevantos fragmentus
        relevant_chunks = self.search_engine.search(text)
        
        if not relevant_chunks:
            logger.info("Nav atrasts neviens atbilstošs fragments kontekstam")
            return ""
        
        # Apvieno fragmentus vienā kontekstā
        context = "\n\n".join([chunk["content"] for chunk in relevant_chunks])
        logger.info(f"Pievienojam kontekstu no {len(relevant_chunks)} fragmentiem")
        
        return context

# Izveidojam sarunu pārvaldītāja instanci, kad modulis tiek importēts
conversation_manager = ConversationManager()

# Izveidojam čatbota servisa instanci, kad modulis tiek importēts
chatbot_service = ChatbotService(conversation_manager)
