import streamlit as st
import database as db
import logic
import pandas as pd
import plotly.express as px
import datetime

st.set_page_config(page_title="Fortune", page_icon="🏦", layout="wide")
db.init_db()
logic.process_automatismes() # Le moteur d'enveloppes s'active silencieusement au démarrage

# --- FENÊTRES MODALES ---
@st.dialog("Catégorisation groupée")
def dialog_similaires(tx_id, libelle, mot_cle, cat_id, cat_nom):
    st.write(f"J'ai trouvé d'autres transactions contenant **{mot_cle}**.")
    st.write(f"Classer également dans `{cat_nom}` ?")
    similaires = db.get_data("SELECT id, date, libelle, montant FROM transactions WHERE libelle LIKE ? AND categorie_id IS NULL AND id != ?", (f"%{mot_cle}%", tx_id))
    selection = {}
    for _, r in similaires.iterrows():
        selection[r['id']] = st.checkbox(f"{r['date']} | {r['libelle']} | {r['montant']}€", value=True, key=f"chk_{r['id']}")
    st.markdown("---")
    col1, col2 = st.columns(2)
    if col1.button("✅ Valider le groupe"):
        db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_id, tx_id))
        for s_id, is_checked in selection.items():
            if is_checked: db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_id, s_id))
        st.rerun()
    if col2.button("❌ Juste l'initiale"):
        db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_id, tx_id))
        st.rerun()

@st.dialog("🏷️ Sélection des catégories")
def dialog_filtre_categories(liste_parents):
    st.write("Coche les catégories à inclure dans l'analyse :")
    tout_cocher = st.checkbox("Tout sélectionner", value=True)
    nouvelle_selection = []
    for p in liste_parents:
        if st.checkbox(p, value=tout_cocher, key=f"filt_{p}"):
            nouvelle_selection.append(p)
    if st.button("Appliquer les filtres"):
        st.session_state['parents_selectionnes'] = nouvelle_selection
        st.rerun()

@st.dialog("⚠️ Vérification de l'import (Doublons potentiels)", width="large")
def dialog_doublons():
    st.warning("Passe en revue l'import. Les transactions déjà présentes en base sont décochées par défaut.")
    df_pending = pd.DataFrame(st.session_state['pending_imports'])
    edited_df = st.data_editor(df_pending[['Importer', 'date', 'libelle', 'montant', 'Doublon']], hide_index=True, disabled=['date', 'libelle', 'montant', 'Doublon'], use_container_width=True)
    if st.button("✅ Confirmer l'importation de la sélection"):
        lignes_a_importer = df_pending[edited_df['Importer']]
        for _, row in lignes_a_importer.iterrows():
            db.execute_query("INSERT INTO transactions (compte_id, date, libelle, montant) VALUES (?,?,?,?)", (row['compte_id'], row['date'], row['libelle'], row['montant']))
        del st.session_state['pending_imports']
        st.success(f"{len(lignes_a_importer)} transactions importées avec succès.")
        st.rerun()
    if st.button("❌ Annuler l'import"):
        del st.session_state['pending_imports']
        st.rerun()

# Navigation latérale
st.sidebar.title("Fortune")
menu = st.sidebar.radio("Modules", ["Tableau de bord", "Comptes & Enveloppes", "Transactions", "Paramètres"])

# --- PAGE : TABLEAU DE BORD ---
if menu == "Tableau de bord":
    st.title("Tableau de bord patrimonial")
    query_tx = """
        SELECT t.date, t.libelle, t.montant, c.nom as compte, 
               IFNULL(cat.nom, 'À trier') as categorie, 
               IFNULL(p_cat.nom, IFNULL(cat.nom, 'À trier')) as parent
        FROM transactions t JOIN comptes c ON t.compte_id = c.id
        LEFT JOIN categories cat ON t.categorie_id = cat.id
        LEFT JOIN categories p_cat ON cat.parent_id = p_cat.id
    """
    df_tx = db.get_data(query_tx)

    if df_tx.empty: st.info("Aucune transaction enregistrée.")
    else:
        df_tx['date'] = pd.to_datetime(df_tx['date'], format='%d/%m/%Y', errors='coerce')
        df_tx = df_tx.dropna(subset=['date'])
        df_tx['Mois-Année'] = df_tx['date'].dt.to_period('M').astype(str)

        st.markdown("### 🎛️ Filtres d'analyse")
        col_f1, col_f2, col_f3 = st.columns(3)
        liste_comptes = df_tx['compte'].unique().tolist()
        comptes_selectionnes = col_f1.multiselect("Comptes", liste_comptes, default=liste_comptes)
        min_date, max_date = df_tx['date'].min(), df_tx['date'].max()
        dates_selectionnees = col_f2.date_input("Période", [min_date, max_date], min_value=min_date, max_value=max_date)
        liste_parents = df_tx['parent'].unique().tolist()
        
        if 'parents_selectionnes' not in st.session_state: st.session_state['parents_selectionnes'] = liste_parents
        col_f3.write(""); 
        if col_f3.button("🏷️ Sélectionner les catégories"): dialog_filtre_categories(liste_parents)
        parents_actifs = st.session_state['parents_selectionnes']

        if len(dates_selectionnees) == 2:
            start_date, end_date = pd.to_datetime(dates_selectionnees[0]), pd.to_datetime(dates_selectionnees[1])
            df_filtre = df_tx[(df_tx['compte'].isin(comptes_selectionnes)) & (df_tx['date'] >= start_date) & (df_tx['date'] <= end_date) & (df_tx['parent'].isin(parents_actifs))]
        else: df_filtre = df_tx

        st.markdown("---")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        total_entrees = df_filtre[df_filtre['montant'] > 0]['montant'].sum()
        total_sorties = df_filtre[df_filtre['montant'] < 0]['montant'].sum()
        cash_flow = total_entrees + total_sorties
        
        df_bilan = db.get_data("SELECT (c.solde_initial + IFNULL(SUM(t.montant), 0)) as solde FROM comptes c LEFT JOIN transactions t ON c.id = t.compte_id")
        fortune_totale = df_bilan['solde'].sum() if not df_bilan.empty else 0

        kpi1.metric("Fortune Nette Globale", f"{fortune_totale:,.2f} €".replace(',', ' '))
        kpi2.metric("Entrées (période)", f"+{total_entrees:,.2f} €".replace(',', ' '))
        kpi3.metric("Sorties (période)", f"{total_sorties:,.2f} €".replace(',', ' '))
        kpi4.metric("Capacité d'épargne (Cashflow)", f"{cash_flow:,.2f} €".replace(',', ' '))

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Répartition des Dépenses")
            df_depenses = df_filtre[df_filtre['montant'] < 0].copy()
            df_depenses['montant_abs'] = df_depenses['montant'].abs()
            if not df_depenses.empty:
                fig_pie = px.sunburst(df_depenses, path=['parent', 'categorie'], values='montant_abs', color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_traces(textinfo="label+percent parent")
                st.plotly_chart(fig_pie, width='stretch')
                with st.expander("📊 Afficher les montants détaillés"):
                    df_resume = df_depenses.groupby('parent')['montant_abs'].sum().reset_index().sort_values(by='montant_abs', ascending=False)
                    df_resume['montant_abs'] = df_resume['montant_abs'].apply(lambda x: f"{x:,.2f} €".replace(',', ' '))
                    df_resume.rename(columns={'parent': 'Catégorie', 'montant_abs': 'Total'}, inplace=True)
                    st.dataframe(df_resume, hide_index=True, width='stretch')
            else: st.write("Aucune dépense sur cette période.")

        with col_g2:
            st.subheader("Flux de trésorerie mensuel")
            if not df_filtre.empty:
                df_flux = df_filtre.copy()
                df_flux['Type'] = df_flux['montant'].apply(lambda x: 'Entrée' if x > 0 else 'Sortie')
                df_flux['montant_abs'] = df_flux['montant'].abs()
                df_group = df_flux.groupby(['Mois-Année', 'Type'])['montant_abs'].sum().reset_index()
                fig_bar = px.bar(df_group, x='Mois-Année', y='montant_abs', color='Type', barmode='group', color_discrete_map={'Entrée': '#2ecc71', 'Sortie': '#e74c3c'})
                st.plotly_chart(fig_bar, width='stretch')
            else: st.write("Aucun flux sur cette période.")

# --- PAGE : COMPTES & ENVELOPPES ---
elif menu == "Comptes & Enveloppes":
    st.title("Gestion des Fonds")
    t_comptes, t_env, t_auto = st.tabs(["🏦 Comptes Physiques", "✉️ Projets & Enveloppes", "⚙️ Automatismes d'Épargne"])

    with t_comptes:
        c_ajout, c_supp = st.columns(2)
        with c_ajout:
            st.subheader("Ajouter un compte")
            with st.form("new_compte", clear_on_submit=True):
                n = st.text_input("Nom du compte")
                t = st.selectbox("Type", ["Courant", "Livret", "PEA", "Assurance Vie", "Espèces"])
                s = st.number_input("Solde Initial (€)", value=0.0)
                if st.form_submit_button("Créer"):
                    if n: db.execute_query("INSERT INTO comptes (nom, type_compte, solde_initial) VALUES (?,?,?)", (n, t, s)); st.rerun()
        with c_supp:
            st.subheader("Supprimer")
            df_c = db.get_data("SELECT id, nom FROM comptes")
            if not df_c.empty:
                c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
                compte_supp = st.selectbox("Compte à retirer", list(c_opts.keys()))
                st.warning("⚠️ Les transactions liées seront effacées.")
                if st.button("🗑️ Confirmer"):
                    id_supp = c_opts[compte_supp]
                    db.execute_query("DELETE FROM transactions WHERE compte_id = ?", (id_supp,))
                    db.execute_query("DELETE FROM comptes WHERE id = ?", (id_supp,))
                    st.rerun()

        st.markdown("---")
        st.dataframe(db.get_data("SELECT nom, type_compte, solde_initial FROM comptes"), width='stretch')

    with t_env:
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if df_c.empty:
            st.warning("Crée d'abord un compte physique.")
        else:
            c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
            with st.form("new_env", clear_on_submit=True):
                st.subheader("Ouvrir une nouvelle enveloppe virtuelle")
                col1, col2, col3 = st.columns(3)
                nom_env = col1.text_input("Nom du projet (ex: Vacances Été)")
                c_parent = col2.selectbox("Compte support", list(c_opts.keys()))
                objectif = col3.number_input("Objectif financier (€)", value=0.0)
                if st.form_submit_button("Créer"):
                    if nom_env: db.execute_query("INSERT INTO enveloppes (nom, compte_id, objectif) VALUES (?,?,?)", (nom_env, c_opts[c_parent], objectif)); st.rerun()

            st.markdown("---")
            st.subheader("État des provisions")
            q_env = """
                SELECT e.nom as Projet, c.nom as Support, e.objectif as Objectif, IFNULL(SUM(p.montant), 0) as Provisionné
                FROM enveloppes e JOIN comptes c ON e.compte_id = c.id
                LEFT JOIN provisions p ON e.id = p.enveloppe_id GROUP BY e.id
            """
            df_env = db.get_data(q_env)
            if not df_env.empty:
                df_env['Manquant'] = df_env['Objectif'] - df_env['Provisionné']
                st.dataframe(df_env, hide_index=True, width='stretch')

    with t_auto:
        df_env_list = db.get_data("SELECT id, nom FROM enveloppes")
        if df_env_list.empty:
            st.warning("Crée d'abord une enveloppe.")
        else:
            e_opts = {r['nom']: r['id'] for _, r in df_env_list.iterrows()}
            with st.form("new_rule", clear_on_submit=True):
                st.subheader("Programmer un virement virtuel mensuel")
                colA, colB, colC = st.columns(3)
                cible = colA.selectbox("Vers l'enveloppe", list(e_opts.keys()))
                m_auto = colB.number_input("Montant mensuel (€)", step=10.0)
                d_auto = colC.date_input("Date de premier virement")
                if st.form_submit_button("Activer l'automatisme"):
                    if m_auto > 0:
                        db.execute_query("INSERT INTO regles_recurrentes (enveloppe_id, montant, prochaine_date) VALUES (?,?,?)", (e_opts[cible], m_auto, d_auto.isoformat()))
                        st.rerun()
            
            st.markdown("---")
            q_regles = "SELECT r.id, e.nom as Enveloppe, r.montant as Mensualité, r.prochaine_date as Prochaine_Échéance FROM regles_recurrentes r JOIN enveloppes e ON r.enveloppe_id = e.id"
            df_regles = db.get_data(q_regles)
            if not df_regles.empty:
                st.write("Règles actives :")
                st.table(df_regles[['Enveloppe', 'Mensualité', 'Prochaine_Échéance']])
                if st.button("🗑️ Supprimer toutes les règles"):
                    db.execute_query("DELETE FROM regles_recurrentes")
                    st.rerun()

# --- PAGE : TRANSACTIONS ---
elif menu == "Transactions":
    st.title("Gestion des flux")
    tab_import, tab_manuel, tab_triage = st.tabs(["📥 Import CSV", "✍️ Saisie Manuelle", "⚖️ Triage"])

    with tab_import:
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if not df_c.empty:
            mapping_c = {r['nom']: r['id'] for _, r in df_c.iterrows()}
            c_nom = st.selectbox("Compte cible", list(mapping_c.keys()))
            up = st.file_uploader("Charger un CSV", type="csv")
            if up:
                df_csv = pd.read_csv(up, sep=';', encoding='utf-8')
                cols = df_csv.columns.tolist()
                c1, c2, c3, c4 = st.columns(4)
                sel_date = c1.selectbox("Date", cols)
                sel_lib = c2.selectbox("Libellé", cols, index=2)
                sel_deb = c3.selectbox("Débit", cols, index=8 if len(cols)>8 else 0)
                sel_cre = c4.selectbox("Crédit", cols, index=9 if len(cols)>9 else 0)
                if st.button("Lancer l'analyse"):
                    pending = []
                    for _, row in df_csv.iterrows():
                        m = logic.clean_amount(row[sel_cre]) + logic.clean_amount(row[sel_deb])
                        d = str(row[sel_date])
                        l = str(row[sel_lib])
                        exist = db.get_data("SELECT id FROM transactions WHERE compte_id=? AND date=? AND libelle=? AND montant=?", (mapping_c[c_nom], d, l, m))
                        is_dup = not exist.empty
                        pending.append({'Importer': not is_dup, 'Doublon': '⚠️ Oui' if is_dup else 'Non', 'date': d, 'libelle': l, 'montant': m, 'compte_id': mapping_c[c_nom]})
                    st.session_state['pending_imports'] = pending
                    st.rerun()

        if 'pending_imports' in st.session_state: dialog_doublons()

    with tab_manuel:
        st.subheader("Nouvelle transaction unitaire")
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if not df_c.empty:
            with st.form("manual_entry", clear_on_submit=True):
                c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
                col1, col2 = st.columns(2)
                m_compte = col1.selectbox("Compte", list(c_opts.keys()))
                m_date = col2.date_input("Date de l'opération")
                col3, col4 = st.columns(2)
                m_lib = col3.text_input("Libellé exact")
                m_montant = col4.number_input("Montant (€) - Mettre un '-' pour une dépense", step=0.01)
                if st.form_submit_button("Ajouter à la base"):
                    if m_lib:
                        date_str = m_date.strftime("%d/%m/%Y")
                        db.execute_query("INSERT INTO transactions (compte_id, date, libelle, montant) VALUES (?,?,?,?)", (c_opts[m_compte], date_str, m_lib, m_montant))
                        st.success("Transaction ajoutée.")
                        st.rerun()

    with tab_triage:
        col_header, col_ai = st.columns([3, 1])
        col_header.subheader("Transactions en attente")
        if col_ai.button("🪄 Magie Gemini"):
            with st.spinner("Analyse en cours..."):
                res = logic.suggest_categories()
                if res >= 0: st.toast(f"{res} classés !"); st.rerun()
                elif res == -3: st.error("Quota épuisé. Attends 60s.")
                elif res == -1: st.warning("Clé API manquante.")
                else: st.error("Erreur Gemini.")

        df_un = db.get_data("SELECT t.id, t.date, t.libelle, t.montant FROM transactions t WHERE t.categorie_id IS NULL ORDER BY t.date DESC")
        if df_un.empty: st.success("Tout est classé !")
        else:
            df_cats = db.get_data("SELECT c1.id, c1.nom, IFNULL(c2.nom, 'P') as parent FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id ORDER BY parent, c1.nom")
            cat_options = {f"{r['parent']} > {r['nom']}": r['id'] for _, r in df_cats.iterrows()}
            for _, row in df_un.head(10).iterrows():
                with st.expander(f"{row['date']} | {row['libelle']} | {row['montant']}€"):
                    c_sel, b_val = st.columns([3, 1])
                    choix = c_sel.selectbox("Catégorie", list(cat_options.keys()), key=f"t_{row['id']}")
                    if b_val.button("Valider", key=f"b_{row['id']}"):
                        mot_cle = logic.get_keyword(row['libelle'])
                        if mot_cle and len(mot_cle) >= 3:
                            count_sim = db.get_data("SELECT COUNT(*) FROM transactions WHERE libelle LIKE ? AND categorie_id IS NULL AND id != ?", (f"%{mot_cle}%", row['id'])).iloc[0,0]
                            if count_sim > 0: dialog_similaires(row['id'], row['libelle'], mot_cle, cat_options[choix], choix)
                            else:
                                db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_options[choix], row['id']))
                                st.rerun()
                        else:
                            db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_options[choix], row['id']))
                            st.rerun()

# --- PAGE : PARAMÈTRES ---
elif menu == "Paramètres":
    st.title("Référentiel & Configuration")
    t1, t2 = st.tabs(["Catégories", "🔑 Clé API Gemini"])
    
    with t1:
        with st.form("add_cat", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom")
            parents = db.get_data("SELECT id, nom FROM categories WHERE parent_id IS NULL")
            p_opts = {"--- PRINCIPALE ---": None}
            for _, r in parents.iterrows(): p_opts[r['nom']] = r['id']
            p_choice = c2.selectbox("Parent", list(p_opts.keys()))
            if st.form_submit_button("Ajouter"):
                if name: db.execute_query("INSERT INTO categories (nom, parent_id) VALUES (?, ?)", (name, p_opts[p_choice])); st.rerun()

        st.markdown("---")
        search_term = st.text_input("🔍 Rechercher une catégorie", "")
        df_cat = db.get_data("SELECT c1.id, c1.nom, c1.parent_id, IFNULL(c2.nom, 'PRINCIPALE') as parent_nom FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id ORDER BY parent_nom DESC, c1.nom ASC")
        if not df_cat.empty:
            if search_term: df_cat = df_cat[df_cat['nom'].str.contains(search_term, case=False, na=False) | df_cat['parent_nom'].str.contains(search_term, case=False, na=False)]
            if df_cat.empty: st.info("Aucun résultat.")
            else:
                cols = st.columns([2, 2, 1, 1])
                cols[0].write("**Nom**"); cols[1].write("**Parent**"); cols[2].write("**Éditer**"); cols[3].write("**Supprimer**")
                for _, row in df_cat.iterrows():
                    c_nom, c_par, c_edit, c_del = st.columns([2, 2, 1, 1])
                    e_key = f"edit_{row['id']}"
                    if st.session_state.get(e_key, False):
                        new_n = c_nom.text_input("Nom", value=row['nom'], key=f"n_{row['id']}", label_visibility="collapsed")
                        p_opts_edit = {"PRINCIPALE": None}
                        for _, r in parents.iterrows(): 
                            if r['id'] != row['id']: p_opts_edit[r['nom']] = r['id']
                        new_p = c_par.selectbox("Parent", list(p_opts_edit.keys()), index=list(p_opts_edit.values()).index(row['parent_id']) if row['parent_id'] in p_opts_edit.values() else 0, key=f"p_{row['id']}", label_visibility="collapsed")
                        if c_edit.button("💾", key=f"s_{row['id']}"):
                            db.execute_query("UPDATE categories SET nom = ?, parent_id = ? WHERE id = ?", (new_n, p_opts_edit[new_p], row['id']))
                            st.session_state[e_key] = False
                            st.rerun()
                    else:
                        c_nom.write(row['nom'])
                        c_par.write(f"`{row['parent_nom']}`")
                        if c_edit.button("📝", key=f"e_{row['id']}"): st.session_state[e_key] = True; st.rerun()
                        if c_del.button("🗑️", key=f"d_{row['id']}"):
                            db.execute_query("UPDATE transactions SET categorie_id = NULL WHERE categorie_id = ?", (row['id'],))
                            db.execute_query("DELETE FROM categories WHERE id = ?", (row['id'],))
                            st.rerun()

    with t2:
        current_key = db.get_config("GEMINI_API_KEY") or ""
        new_key = st.text_input("Clé API Google Gemini", value=current_key, type="password")
        if st.button("Sauvegarder"): db.set_config("GEMINI_API_KEY", new_key); st.success("Clé enregistrée.")