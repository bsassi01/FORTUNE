import sqlite3
import os

DB_NAME = "fortune.db"

def get_connection():
    """Établit et retourne une connexion à la base de données SQLite."""
    conn = sqlite3.connect(DB_NAME)
    # Permet de renvoyer les requêtes sous forme de dictionnaires plutôt que de simples tuples
    conn.row_factory = sqlite3.Row 
    return conn

def initialiser_base_de_donnees():
    """Crée les tables de la base de données si elles n'existent pas encore."""
    print(f"Initialisation de l'architecture de {DB_NAME}...")
    conn = get_connection()
    cursor = conn.cursor()

    # Table des Catégories (Le plan comptable)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        type_flux TEXT NOT NULL CHECK(type_flux IN ('Revenu', 'Depense', 'Transfert')),
        mots_cles TEXT -- Mots-clés séparés par des virgules pour le ciblage auto
    )
    ''')

    # Table des Comptes physiques
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comptes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        type_compte TEXT NOT NULL, -- Courant, Epargne, Bourse, etc.
        solde_initial REAL DEFAULT 0.0
    )
    ''')

    # Table des Sous-comptes virtuels (Enveloppes fléchées)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sous_comptes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compte_parent_id INTEGER NOT NULL,
        nom TEXT NOT NULL,
        cible_epargne REAL DEFAULT 0.0,
        FOREIGN KEY (compte_parent_id) REFERENCES comptes(id)
    )
    ''')

    # Table des Crédits (Passifs)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS credits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        capital_emprunte REAL NOT NULL,
        taux_interet REAL NOT NULL,
        mensualite REAL NOT NULL,
        assurance REAL DEFAULT 0.0,
        date_debut DATE,
        duree_mois INTEGER NOT NULL
    )
    ''')

    # Table centrale des Transactions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compte_id INTEGER NOT NULL,
        categorie_id INTEGER,
        date DATE NOT NULL,
        libelle TEXT NOT NULL,
        montant REAL NOT NULL,
        pointe BOOLEAN DEFAULT 0, -- 0 = non pointé, 1 = pointé
        notes TEXT,
        FOREIGN KEY (compte_id) REFERENCES comptes(id),
        FOREIGN KEY (categorie_id) REFERENCES categories(id)
    )
    ''')

    conn.commit()
    
    # Injection des catégories de base pour éviter de démarrer à blanc
    categories_base = [
        ('Salaire', 'Revenu', 'VIREMENT SALAIRE, SALAIRE'),
        ('Alimentation', 'Depense', 'CARREFOUR, LECLERC, AUCHAN, LIDL, ASUKA'),
        ('Logement', 'Depense', 'LOYER, EDF, ENGIE, EAU, ASSURANCE HABITATION'),
        ('Transport', 'Depense', 'SNCF, TOTAL, ESSO, UBER, PEAGE'),
        ('Abonnements', 'Depense', 'NETFLIX, SPOTIFY, FREE, ORANGE, BOUYGUES'),
        ('Virement Interne', 'Transfert', 'VIREMENT COMPTE, VIR SEPA')
    ]
    
    for nom, type_flux, mots_cles in categories_base:
        try:
            cursor.execute('''
            INSERT INTO categories (nom, type_flux, mots_cles) 
            VALUES (?, ?, ?)
            ''', (nom, type_flux, mots_cles))
        except sqlite3.IntegrityError:
            # La catégorie existe déjà, on ignore
            pass

    conn.commit()
    conn.close()
    print("Base de données 'Fortune' opérationnelle.")

if __name__ == "__main__":
    initialiser_base_de_donnees()