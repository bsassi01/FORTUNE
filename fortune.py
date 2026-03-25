import streamlit as st
import sqlite3
import pandas as pd

# --- Configuration du rendu visuel ---
st.set_page_config(page_title="Fortune", page_icon="🏦", layout="wide")

# --- Moteur de base de données ---
DB_NAME = "fortune.db"

def get_data(query, params=()):
    """Exécute une requête de lecture et retourne un DataFrame Pandas."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_query(query, params=()):
    """Exécute une requête d'écriture (INSERT, UPDATE, DELETE)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        success = True
    except sqlite3.Error as e:
        st.error(f"Erreur SQL : {e}")
        success = False
    finally:
        conn.close()
    return success

# --- Navigation ---
st.sidebar.title("Fortune")
st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "Modules de gestion",
    ["Tableau de bord", "Comptes & Enveloppes", "Transactions (Imports)", "Crédits", "Paramètres"]
)

# --- Routage des écrans ---
if menu == "Tableau de bord":
    st.title("Tableau de bord patrimonial")
    st.write("La synthèse de ta fortune nette, tes graphiques de répartition et tes alertes budgétaires s'afficheront ici.")
    
    st.markdown("### État actuel de la base (Test de connexion)")
    df_comptes = get_data("SELECT id, nom, type_compte, solde_initial FROM comptes")
    
    if df_comptes.empty:
        st.info("La base est vide. Le premier point d'action est de créer tes comptes dans l'onglet 'Comptes & Enveloppes'.")
    else:
        st.dataframe(df_comptes, use_container_width=True, hide_index=True)

elif menu == "Comptes & Enveloppes":
    st.title("Gestion des Comptes")
    
    # Zone de création d'un compte physique
    st.markdown("### Ajouter un nouveau compte")
    with st.form("form_nouveau_compte", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            nom_compte = st.text_input("Nom du compte (ex: Courant LCL)")
        with col2:
            type_compte = st.selectbox("Type d'enveloppe", ["Compte Courant", "Livret d'Épargne", "PEA", "Assurance Vie", "Espèces"])
        with col3:
            solde_init = st.number_input("Solde initial (€)", value=0.0, step=100.0)
            
        submit_compte = st.form_submit_button("Créer le compte")
        
        if submit_compte:
            if nom_compte.strip() == "":
                st.warning("Le nom du compte est obligatoire.")
            else:
                # Injection dans SQLite
                if execute_query("INSERT INTO comptes (nom, type_compte, solde_initial) VALUES (?, ?, ?)", (nom_compte.strip(), type_compte, solde_init)):
                    st.success(f"Compte '{nom_compte}' créé avec succès.")
                    st.rerun()

    # Affichage dynamique des comptes existants
    st.markdown("### Tes comptes actuels")
    df_comptes = get_data("SELECT id, nom, type_compte, solde_initial FROM comptes")
    if not df_comptes.empty:
        st.dataframe(df_comptes, use_container_width=True, hide_index=True)
        
        # Zone de suppression d'un compte
        st.markdown("### Supprimer un compte")
        with st.form("form_suppression_compte"):
            options_comptes = {row['nom']: row['id'] for _, row in df_comptes.iterrows()}
            compte_a_supprimer = st.selectbox("Sélectionne le compte à effacer", options_comptes.keys())
            submit_suppression = st.form_submit_button("Supprimer définitivement")
            
            if submit_suppression:
                id_cible = int(options_comptes[compte_a_supprimer])
                if execute_query("DELETE FROM comptes WHERE id = ?", (id_cible,)):
                    st.success(f"Le compte '{compte_a_supprimer}' a été supprimé.")
                    st.rerun()
    else:
        st.write("Aucun compte configuré pour le moment.")

elif menu == "Transactions (Imports)":
    st.title("Ingestion et Ventilation")
    st.write("Ce module contiendra la zone de téléversement des fichiers CSV et le tableau de catégorisation manuelle des flux orphelins.")

elif menu == "Crédits":
    st.title("Tableaux d'Amortissement")
    st.write("Ce module calculera le capital restant dû en temps réel pour l'imputer sur ta fortune nette.")

elif menu == "Paramètres":
    st.title("Configuration du Moteur")
    st.write("Ce module te permettra d'éditer le plan comptable (catégories) et d'affiner les mots-clés d'attribution automatique.")