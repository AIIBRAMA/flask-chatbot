# search.py
"""
Meklēšanas modulis aplikācijai.
Pārvalda teksta fragmentu meklēšanu un atbilstības noteikšanu.
"""
import os
import re
import logging
from config import Config, get_folder_path

logger = logging.getLogger(__name__)

class SearchEngine:
    """Klase teksta fragmentu meklēšanai un atbilstības noteikšanai"""
    
    def __init__(self):
        """Inicializē meklēšanas dzinēju"""
        # Mapju saraksti, kuros veikt meklēšanu
        self.primary_folders = ["pdf_chunks_part8", "pdf_chunks_part9"]
        self.cofog_folders = [
            "pdf_chunks_part1", "pdf_chunks_part2", "pdf_chunks_part3", 
            "pdf_chunks_part4", "pdf_chunks_part5", "pdf_chunks_part6", "pdf_chunks_part7"
        ]
    
    def search(self, query):
        """
        Meklē teksta fragmentus, kas atbilst vaicājumam
        
        Args:
            query (str): Meklēšanas vaicājums
            
        Returns:
            list: Atbilstošo fragmentu saraksts ar atbilstības reitingu
        """
        logger.info(f"Meklējam teksta fragmentos pēc vaicājuma: {query}")
        
        query_words = self._preprocess_query(query)
        results = []
        
        # Nosaka, vai jautājums saistīts ar COFOG salīdzinājumu
        is_cofog_comparison = self._is_cofog_related(query)
        logger.info(f"Jautājums prasa COFOG salīdzinājumu: {is_cofog_comparison}")
        
        try:
            # 1. Pārbaudām primārās mapes
            for folder in self.primary_folders:
                self._process_folder(folder, query_words, results)
            
            # 2. Ja jautājums saistīts ar COFOG vai nav atrasti rezultāti, meklējam COFOG mapēs
            if is_cofog_comparison or len(results) < 1:
                for folder in self.cofog_folders:
                    self._process_folder(folder, query_words, results)
            
            # Sakārtojam rezultātus pēc atbilstības
            results.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"Kopā atrasti {len(results)} atbilstoši fragmenti")
            # Atgriežam labākos 3 rezultātus
            return results[:3]
        
        except Exception as e:
            logger.error(f"Kļūda meklējot teksta fragmentos: {e}", exc_info=True)
            return []
    
    def _preprocess_query(self, query):
        """
        Apstrādā vaicājumu pirms meklēšanas
        
        Args:
            query (str): Sākotnējais vaicājums
            
        Returns:
            list: Apstrādātu vaicājuma vārdu saraksts
        """
        # Pārvērš vaicājumu mazajiem burtiem
        query = query.lower()
        
        # Noņem pieturzīmes
        query = re.sub(r'[^\w\s]', ' ', query)
        
        # Sadala vārdos
        words = query.split()
        
        # Atgriež unikālus vārdus (noņem dublējumus)
        return list(set(words))
    
    def _is_cofog_related(self, query):
        """
        Nosaka, vai vaicājums ir saistīts ar COFOG klasifikāciju
        
        Args:
            query (str): Meklēšanas vaicājums
            
        Returns:
            bool: True, ja vaicājums saistīts ar COFOG, citādi False
        """
        # Atslēgvārdi, kas norāda uz COFOG saistību
        cofog_keywords = [
            "cofog", "salīdzin", "salīdzināj", "salīdzināt", 
            "starptautisk", "klasifik", "standart", "funkciju", "kods"
        ]
        
        query_lower = query.lower()
        return any(word in query_lower for word in cofog_keywords)
    
    def _process_folder(self, folder_name, query_words, results):
        """
        Apstrādā visus teksta failus norādītajā mapē
        
        Args:
            folder_name (str): Mapes nosaukums
            query_words (list): Meklēšanas vārdu saraksts
            results (list): Rezultātu saraksts, kurā pievienot atradumus
        """
        folder_path = get_folder_path(folder_name)
        
        if not os.path.exists(folder_path):
            logger.warning(f"Mape {folder_path} netika atrasta, izlaižam")
            return
            
        logger.info(f"Meklējam mapē: {folder_path}")
        
        try:
            for filename in os.listdir(folder_path):
                if filename.endswith(".txt"):
                    filepath = os.path.join(folder_path, filename)
                    self._process_file(filepath, query_words, results)
        except Exception as e:
            logger.error(f"Kļūda lasot mapes {folder_path} saturu: {e}", exc_info=True)
    
    def _process_file(self, file_path, query_words, results):
        """
        Apstrādā vienu teksta failu, meklējot atbilstības
        
        Args:
            file_path (str): Ceļš līdz failam
            query_words (list): Meklēšanas vārdu saraksts
            results (list): Rezultātu saraksts, kurā pievienot atradumus
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().lower()
                
                # Uzlabota atbilstības noteikšana
                relevance_score = self._calculate_relevance(content, query_words)
                
                if relevance_score > 0:
                    results.append({
                        "file": file_path,
                        "content": content,
                        "score": relevance_score
                    })
                    logger.debug(f"Atrasts atbilstošs fragments: {file_path} (score: {relevance_score})")
        except Exception as e:
            logger.error(f"Kļūda lasot failu {file_path}: {e}", exc_info=True)
    
    def _calculate_relevance(self, content, query_words):
        """
        Aprēķina teksta atbilstību vaicājumam
        
        Args:
            content (str): Teksta saturs
            query_words (list): Meklēšanas vārdu saraksts
            
        Returns:
            float: Atbilstības reitings
        """
        if not query_words:
            return 0
        
        relevance_score = 0
        content_words = re.findall(r'\b\w+\b', content)
        
        # 1. Pārbauda precīzas vārdu sakritības
        for word in query_words:
            # Meklē precīzu vārdu (kā atsevišķu vārdu)
            exact_matches = len(re.findall(rf'\b{re.escape(word)}\b', content))
            if exact_matches > 0:
                relevance_score += 2 * exact_matches
            # Meklē vārdu kā daļu no garāka vārda
            elif word in content:
                relevance_score += 0.5
        
        # 2. Frāžu meklēšana (divu vārdu kombinācijas)
        # Vispirms atjaunojam sākotnējo vaicājumu, lai saglabātu vārdu secību
        original_query = ' '.join(query_words).lower()
        words_in_order = original_query.split()
        
        for i in range(len(words_in_order) - 1):
            phrase = f"{words_in_order[i]} {words_in_order[i+1]}"
            phrase_count = content.count(phrase)
            if phrase_count > 0:
                relevance_score += 3 * phrase_count
        
        # 3. Specifiska meklēšana pēc kodu formāta (piemēram, "09.620")
        code_patterns = re.findall(r'\d{2}\.\d{3}', original_query)
        for code in code_patterns:
            code_count = content.count(code)
            if code_count > 0:
                relevance_score += 5 * code_count  # Kodi ir ļoti svarīgi, tāpēc augstāks svars
        
        # 4. Konteksta atbilstība - cik % no vaicājuma vārdiem ir tekstā
        unique_query_words = set(query_words)
        content_word_set = set(content_words)
        word_overlap = len(unique_query_words.intersection(content_word_set))
        context_score = word_overlap / len(unique_query_words) if unique_query_words else 0
        
        relevance_score += context_score * 2
        
        # Normalizējam rezultātu, ņemot vērā vaicājuma garumu
        return relevance_score / len(query_words)

# Funkcija vispārīgu jautājumu atpazīšanai
def is_generic_question(text):
    """
    Nosaka, vai jautājums ir vispārīgs (nekonkrēts)
    
    Args:
        text (str): Jautājuma teksts
        
    Returns:
        bool: True, ja jautājums ir vispārīgs, citādi False
    """
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

# Izveidojam meklēšanas dzinēja instanci, kad modulis tiek importēts
search_engine = SearchEngine()
