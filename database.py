import sqlite3
import pandas as pd

DB_NAME = "fortune.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS comptes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, type_compte TEXT, solde_initial REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE, parent_id INTEGER, FOREIGN KEY(parent_id) REFERENCES categories(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, compte_id INTEGER, date TEXT, libelle TEXT, montant REAL, categorie_id INTEGER, enveloppe_id INTEGER, FOREIGN KEY(compte_id) REFERENCES comptes(id), FOREIGN KEY(categorie_id) REFERENCES categories(id), FOREIGN KEY(enveloppe_id) REFERENCES enveloppes(id))")
        
        # Mise à jour sécurisée de la table transactions si la colonne n'existe pas encore
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN enveloppe_id INTEGER REFERENCES enveloppes(id)")
        except Exception:
            pass

        cursor.execute("CREATE TABLE IF NOT EXISTS config (cle TEXT PRIMARY KEY, valeur TEXT)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS enveloppes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE, compte_id INTEGER, objectif REAL, FOREIGN KEY(compte_id) REFERENCES comptes(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS provisions (id INTEGER PRIMARY KEY AUTOINCREMENT, enveloppe_id INTEGER, date TEXT, montant REAL, FOREIGN KEY(enveloppe_id) REFERENCES enveloppes(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS regles_recurrentes (id INTEGER PRIMARY KEY AUTOINCREMENT, enveloppe_id INTEGER, montant REAL, prochaine_date TEXT, FOREIGN KEY(enveloppe_id) REFERENCES enveloppes(id))")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS abonnements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                libelle TEXT,
                montant REAL,
                frequence TEXT,
                compte_id INTEGER,
                categorie_id INTEGER,
                FOREIGN KEY(compte_id) REFERENCES comptes(id),
                FOREIGN KEY(categorie_id) REFERENCES categories(id)
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_cats = {
                "REVENUS": ["Salaire", "Retraite", "Dividendes", "Ventes/Extras"],
                "LOGEMENT": ["Loyer/Prêt", "Charges/Énergie", "Travaux", "Assurance Habitation"],
                "ALIMENTATION": ["Courses", "Restaurants/Bars", "Cafétéria"],
                "TRANSPORT": ["Carburant", "Entretien Véhicule", "Transports en commun", "Assurance Auto"],
                "LOISIRS": ["Abonnements", "Sorties/Culture", "Voyages/Vacances", "Sport"],
                "SANTÉ": ["Pharmacie/Médecin", "Mutuelle"],
                "IMPÔTS": ["Impôt sur le revenu", "Taxes Locales"]
            }
            for parent, subs in default_cats.items():
                cursor.execute("INSERT INTO categories (nom, parent_id) VALUES (?, NULL)", (parent,))
                p_id = cursor.lastrowid
                for sub in subs:
                    cursor.execute("INSERT INTO categories (nom, parent_id) VALUES (?, ?)", (sub, p_id))
        conn.commit()

def get_data(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(query, conn, params=params)

def execute_query(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            print(f"Erreur SQL : {e}")
            return False

def get_config(key):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valeur FROM config WHERE cle = ?", (key,))
        res = cursor.fetchone()
        return res[0] if res else None

def set_config(key, value):
    execute_query("INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)", (key, value))