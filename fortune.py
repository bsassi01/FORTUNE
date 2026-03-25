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
        # Table Comptes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comptes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nom TEXT, 
                type_compte TEXT, 
                solde_initial REAL
            )
        """)
        
        # Table Categories
        try:
            cursor.execute("SELECT parent_id FROM categories LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("DROP TABLE IF EXISTS categories")
            cursor.execute("""
                CREATE TABLE categories (
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
    query = """
    SELECT c.nom, c.type_compte, (c.solde_initial + IFNULL(SUM(t.montant), 0)) as solde 
    FROM comptes c LEFT JOIN transactions t ON c.id = t.compte_id GROUP BY c.id
    """
    df_bilan = get_data(query)
    if not df_bilan.empty:
        total = df_bilan['solde'].sum()
        st.metric("Fortune Totale", f"{total:,.2f} €".replace(',', ' ').replace('.', ','))
        st.dataframe(df_bilan, use_container_width=True, hide_index=True)
    else:
        st.info("Configure tes comptes pour voir ton patrimoine.")

# --- PAGE : COMPTES ---
elif menu == "Comptes & Enveloppes":
    st.title("Gestion des Comptes")
    with st.form("new_compte", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Nom du compte")
        t = c2.selectbox("Type", ["Courant", "Livret", "PEA", "Assurance Vie", "Espèces"])
        s = c3.number_input("Solde Initial (€)", value=0.0)
        if st.form_submit_button("Créer"):
            if n.strip():
                execute_query("INSERT INTO comptes (nom, type_compte, solde_initial) VALUES (?,?,?)", (n.strip(), t, s))
                st.rerun()

    st.markdown("---")
    df_c = get_data("SELECT id, nom, type_compte, solde_initial FROM comptes")
    if not df_c.empty:
        st.dataframe(df_c[['nom', 'type_compte', 'solde_initial']], use_container_width=True)
        with st.expander("🗑️ Supprimer un compte"):
            opt = {r['nom']: r['id'] for _, r in df_c.iterrows()}
            cible = st.selectbox("Compte à effacer", list(opt.keys()))
            if st.button("Confirmer la suppression"):
                execute_query("DELETE FROM transactions WHERE compte_id = ?", (opt[cible],))
                execute_query("DELETE FROM comptes WHERE id = ?", (opt[cible],))
                st.rerun()

# --- PAGE : TRANSACTIONS ---
elif menu == "Transactions (Imports)":
    st.title("Imports & Triage")
    df_c = get_data("SELECT id, nom FROM comptes")
    if df_c.empty:
        st.warning("Crée un compte avant d'importer.")
    else:
        mapping_c = {r['nom']: r['id'] for _, r in df_c.iterrows()}
        c_nom = st.selectbox("Compte cible", list(mapping_c.keys()))
        c_id = mapping_c[c_nom]
        
        if st.button(f"⚠️ Vider l'historique de {c_nom}"):
            execute_query("DELETE FROM transactions WHERE compte_id = ?", (c_id,))
            st.rerun()

        up = st.file_uploader("Charger un CSV", type="csv")
        if up:
            df = pd.read_csv(up, sep=';', encoding='utf-8')
            st.dataframe(df.head(3))
            cols = df.columns.tolist()
            c1, c2, c3, c4 = st.columns(4)
            sel_date = c1.selectbox("Date", cols, index=0)
            sel_lib = c2.selectbox("Libellé", cols, index=2)
            sel_deb = c3.selectbox("Débit", cols, index=8)
            sel_cre = c4.selectbox("Crédit", cols, index=9)

            if st.button("Importer les données"):
                def clean(v):
                    if pd.isna(v) or v == '': return 0.0
                    return float(str(v).replace(',', '.').replace('+', '').replace(' ', '').strip())
                
                for _, row in df.iterrows():
                    m = clean(row[sel_cre]) + clean(row[sel_deb])
                    execute_query(
                        "INSERT INTO transactions (compte_id, date, libelle, montant) VALUES (?,?,?,?)",
                        (c_id, str(row[sel_date]), str(row[sel_lib]), m)
                    )
                st.success("Import terminé.")
                st.rerun()

# --- PAGE : PARAMÈTRES (EDITION CATÉGORIES) ---
elif menu == "Paramètres":
    st.title("Configuration")
    t1, t2 = st.tabs(["Catégories", "IA & API"])
    
    with t1:
        st.subheader("Structure des catégories")
        
        with st.form("add_cat_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            new_name = col_a.text_input("Nom de la catégorie")
            df_p = get_data("SELECT id, nom FROM categories WHERE parent_id IS NULL")
            parent_opts = {"--- PRINCIPALE ---": None}
            for _, r in df_p.iterrows(): parent_opts[r['nom']] = r['id']
            p_nom = col_b.selectbox("Ranger sous", list(parent_opts.keys()))
            
            if st.form_submit_button("Ajouter"):
                if new_name:
                    execute_query("INSERT INTO categories (nom, parent_id) VALUES (?, ?)", (new_name, parent_opts[p_nom]))
                    st.rerun()

        st.markdown("---")
        st.write("### Référentiel actuel")
        df_list = get_data("""
            SELECT c1.id, c1.nom, IFNULL(c2.nom, 'PRINCIPALE') as parent_nom 
            FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id
            ORDER BY parent_nom DESC, c1.nom ASC
        """)

        if not df_list.empty:
            h1, h2, h3 = st.columns([2, 2, 1])
            h1.write("**Nom**"); h2.write("**Parent**"); h3.write("**Action**")

            for _, row in df_list.iterrows():
                row_id = row['id']
                c1, c2, c3 = st.columns([2, 2, 1])
                
                # Gestion de l'état d'édition par ligne
                edit_key = f"edit_mode_{row_id}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                if st.session_state[edit_key]:
                    # Mode ÉDITION
                    new_val = c1.text_input("Edit", value=row['nom'], key=f"in_{row_id}", label_visibility="collapsed")
                    if c3.button("💾", key=f"save_{row_id}"):
                        execute_query("UPDATE categories SET nom = ? WHERE id = ?", (new_val, row_id))
                        st.session_state[edit_key] = False
                        st.rerun()
                else:
                    # Mode LECTURE
                    c1.write(row['nom'])
                    c2.write(f"*{row['parent_nom']}*")
                    if c3.button("📝", key=f"ed_{row_id}"):
                        st.session_state[edit_key] = True
                        st.rerun()
        
        st.markdown("---")
        if st.button("Effacer toutes les catégories"):
            execute_query("DELETE FROM categories")
            st.rerun()