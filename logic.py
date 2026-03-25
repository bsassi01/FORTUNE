import pandas as pd
import database as db
from google import genai
import json
import re
import datetime

def clean_amount(val):
    if pd.isna(val) or val == '': return 0.0
    try:
        s = str(val).replace(',', '.').replace('+', '').replace(' ', '').strip()
        return float(s)
    except:
        return 0.0

def get_keyword(libelle):
    clean = re.sub(r'[^A-Za-z\s]', ' ', str(libelle).upper())
    noise = r'\b(PRLV|SEPA|CARTE|CB|FACTURE|PAIEMENT|VIR|VIREMENT|RETRAIT|DAB|PRELEVEMENT|COTISATION|ECHEANCE|CHEQUE|ECH|REF|ID)\b'
    clean = re.sub(noise, ' ', clean)
    mots = [m for m in clean.split() if len(m) >= 3]
    if mots:
        return mots[0]
    return ""

def process_automatismes():
    """Vérifie et exécute les règles d'épargne virtuelles échues."""
    today = datetime.date.today()
    regles = db.get_data("SELECT * FROM regles_recurrentes WHERE prochaine_date <= ?", (today.isoformat(),))
    
    for _, r in regles.iterrows():
        # Exécuter le virement virtuel
        db.execute_query("INSERT INTO provisions (enveloppe_id, date, montant) VALUES (?, ?, ?)", 
                         (r['enveloppe_id'], today.isoformat(), r['montant']))
        
        # Calculer la prochaine occurrence (+30 jours pour une mensualisation fluide)
        curr_date = datetime.date.fromisoformat(r['prochaine_date'])
        next_date = curr_date + datetime.timedelta(days=30)
        
        # Rattrapage automatique en cas d'absence prolongée de l'utilisateur
        while next_date <= today:
            db.execute_query("INSERT INTO provisions (enveloppe_id, date, montant) VALUES (?, ?, ?)", 
                             (r['enveloppe_id'], next_date.isoformat(), r['montant']))
            next_date += datetime.timedelta(days=30)

        db.execute_query("UPDATE regles_recurrentes SET prochaine_date = ? WHERE id = ?", 
                         (next_date.isoformat(), r['id']))

def suggest_categories():
    api_key = db.get_config("GEMINI_API_KEY")
    if not api_key: return -1 

    try:
        client = genai.Client(api_key=api_key)
        df_un = db.get_data("SELECT id, libelle, montant FROM transactions WHERE categorie_id IS NULL LIMIT 10")
        if df_un.empty: return 0

        df_cats = db.get_data("SELECT id, nom FROM categories")
        cat_list = "\n".join([f"ID:{r['id']}:{r['nom']}" for _, r in df_cats.iterrows()])
        trans_list = "\n".join([f"TID:{r['id']}:{r['libelle']}" for _, r in df_un.iterrows()])

        prompt = f"""Classe ces transactions (TID) dans ces IDs de categories.
        CATS: {cat_list}
        TRANS: {trans_list}
        Reponds en JSON pur: {{"TID:1": ID_CAT}}"""

        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        
        raw_text = response.text.strip().replace('```json', '').replace('```', '')
        mapping = json.loads(raw_text)
        
        count = 0
        for tid_str, cat_id in mapping.items():
            pure_id = int(tid_str.split(':')[-1])
            if db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_id, pure_id)):
                count += 1
        return count

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg: return -3
        return -2