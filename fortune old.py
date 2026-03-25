import streamlit as st
import sqlite3
import pandas as pd

# --- Configuration ---
st.set_page_config(page_title="Fortune", page_icon="🏦", layout="wide")
DB_NAME = "fortune.db"

# --- Initialisation et Migrations ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS comptes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, type_compte TEXT, solde_initial REAL)")
        
        # Table Categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nom TEXT UNIQUE, 
                parent_id INTEGER, 
                FOREIGN KEY(parent_id) REFERENCES categories(id)
            )
        """)
        
        # Table Transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                compte_id INTEGER, 
                date TEXT, 
                libelle TEXT, 
                montant REAL, 
                categorie_id INTEGER, 
                FOREIGN KEY(compte_id) REFERENCES comptes(id),
                FOREIGN KEY(categorie_id) REFERENCES categories(id)
            )
        """)

        # Injection des catégories par défaut si la table est vide
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_cats = {
                "REVENUS": ["Salaire", "Retraite", "Dividendes", "Ventes/Extras"],
                "LOGEMENT": ["Loyer/Prêt", "Charges/Énergie", "Travaux", "Assurance Habitation"],
                "ALIMENTATION": ["Courses", "Restaurants/Bars", "Cafétéria"],
                "TRANSPORT": ["Carburant", "Entretien Véhicule", "Transports en commun", "Assurance Auto"],
                "LOISIRS": ["Abonnements (Netflix...)", "Sorties/Culture", "Voyages/Vacances", "Sport"],
                "SANTÉ": ["Pharmacie/Médecin", "Mutuelle"],
                "IMPÔTS": ["Impôt sur le revenu", "Taxes Locales"]
            }
            for parent, subs in default_cats.items():
                cursor.execute("INSERT INTO categories (nom, parent_id) VALUES (?, NULL)", (parent,))
                p_id = cursor.lastrowid
                for sub in subs:
                    cursor.execute("INSERT INTO categories (nom, parent_id) VALUES (?, ?)", (sub, p_id))
        conn.commit()

init_db()

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
            st.error(f"Erreur SQL : {e}")
            return False

# --- Navigation ---
st.sidebar.title("Fortune")
menu = st.sidebar.radio("Modules", ["Tableau de bord", "Comptes & Enveloppes", "Transactions (Imports)", "Paramètres"])

# --- PAGE : TABLEAU DE BORD ---
if menu == "Tableau de bord":
    st.title("Tableau de bord patrimonial")
    query = "SELECT c.nom, (c.solde_initial + IFNULL(SUM(t.montant), 0)) as solde FROM comptes c LEFT JOIN transactions t ON c.id = t.compte_id GROUP BY c.id"
    df_bilan = get_data(query)
    if not df_bilan.empty:
        st.metric("Fortune Totale", f"{df_bilan['solde'].sum():,.2f} €".replace('.', ','))
        st.dataframe(df_bilan, use_container_width=True, hide_index=True)

# --- PAGE : COMPTES ---
elif menu == "Comptes & Enveloppes":
    st.title("Comptes")
    with st.form("new_compte", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n, t, s = c1.text_input("Nom"), c2.selectbox("Type", ["Courant", "Livret", "PEA", "Assurance Vie"]), c3.number_input("Solde Initial", 0.0)
        if st.form_submit_button("Créer"):
            execute_query("INSERT INTO comptes (nom, type_compte, solde_initial) VALUES (?,?,?)", (n, t, s))
            st.rerun()
    st.dataframe(get_data("SELECT nom, type_compte, solde_initial FROM comptes"), use_container_width=True)

# --- PAGE : TRANSACTIONS ---
elif menu == "Transactions (Imports)":
    st.title("Imports CSV")
    # Logique d'import (inchangée)
    st.info("Utilise cet onglet pour charger tes relevés bancaires.")

# --- PAGE : PARAMÈTRES ---
elif menu == "Paramètres":
    st.title("Référentiel des Catégories")
    t1, t2 = st.tabs(["Hiérarchie & Édition", "IA Configuration"])
    
    with t1:
        # 1. AJOUT
        with st.form("add_cat"):
            st.subheader("Nouvelle catégorie")
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom")
            parents = get_data("SELECT id, nom FROM categories WHERE parent_id IS NULL")
            p_opts = {"--- PRINCIPALE ---": None}
            for _, r in parents.iterrows(): p_opts[r['nom']] = r['id']
            p_choice = c2.selectbox("Parent", list(p_opts.keys()))
            if st.form_submit_button("Ajouter"):
                execute_query("INSERT INTO categories (nom, parent_id) VALUES (?, ?)", (name, p_opts[p_choice]))
                st.rerun()

        st.markdown("---")
        
        # 2. LISTE ET MODIFICATION
        df_cat = get_data("""
            SELECT c1.id, c1.nom, c1.parent_id, IFNULL(c2.nom, 'PRINCIPALE') as parent_nom 
            FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id
            ORDER BY parent_nom DESC, c1.nom ASC
        """)

        if not df_cat.empty:
            cols = st.columns([2, 2, 1, 1])
            cols[0].write("**Nom**"); cols[1].write("**Parent**"); cols[2].write("**Éditer**"); cols[3].write("**Supprimer**")
            
            for _, row in df_cat.iterrows():
                c_nom, c_par, c_edit, c_del = st.columns([2, 2, 1, 1])
                e_key = f"edit_{row['id']}"
                
                if st.session_state.get(e_key, False):
                    # MODE EDITION
                    new_n = c_nom.text_input("Nom", value=row['nom'], key=f"n_{row['id']}", label_visibility="collapsed")
                    # Choix du nouveau parent
                    p_opts_edit = {"PRINCIPALE": None}
                    for _, r in parents.iterrows(): 
                        if r['id'] != row['id']: p_opts_edit[r['nom']] = r['id']
                    
                    new_p = c_par.selectbox("Parent", list(p_opts_edit.keys()), index=list(p_opts_edit.values()).index(row['parent_id']) if row['parent_id'] in p_opts_edit.values() else 0, key=f"p_{row['id']}", label_visibility="collapsed")
                    
                    if c_edit.button("💾", key=f"s_{row['id']}"):
                        execute_query("UPDATE categories SET nom = ?, parent_id = ? WHERE id = ?", (new_n, p_opts_edit[new_p], row['id']))
                        st.session_state[e_key] = False
                        st.rerun()
                else:
                    # MODE LECTURE
                    c_nom.write(row['nom'])
                    c_par.write(f"`{row['parent_nom']}`")
                    if c_edit.button("📝", key=f"e_{row['id']}"):
                        st.session_state[e_key] = True
                        st.rerun()
                    
                    if c_del.button("🗑️", key=f"d_{row['id']}"):
                        # Sécurité : Si on supprime, on remet les transactions liées à NULL (À trier)
                        execute_query("UPDATE transactions SET categorie_id = NULL WHERE categorie_id = ?", (row['id'],))
                        execute_query("DELETE FROM categories WHERE id = ?", (row['id'],))
                        st.rerun()