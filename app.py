import streamlit as st
import database as db
import logic
import dashboard
import pandas as pd

st.set_page_config(page_title="Fortune", page_icon="🏦", layout="wide")

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab-list"] button {
        padding: 0.8rem 2rem !important;
        border-radius: 6px 6px 0 0 !important;
        background-color: rgba(128, 128, 128, 0.05) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-bottom: none !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: rgba(255, 75, 75, 0.1) !important;
        border-bottom: 3px solid #ff4b4b !important;
    }
    .stTabs [data-baseweb="tab-list"] button p {
        font-size: 1.15rem !important; font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

db.init_db()
logic.process_automatismes()

@st.dialog("Catégorisation groupée")
def dialog_similaires(tx_id, libelle, mot_cle, cat_id, cat_nom):
    st.write(f"Autres transactions contenant **{mot_cle}** :")
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

@st.dialog("⚠️ Vérification de l'import (Doublons potentiels)", width="large")
def dialog_doublons():
    st.warning("Transactions déjà présentes décochées par défaut.")
    df_pending = pd.DataFrame(st.session_state['pending_imports'])
    edited_df = st.data_editor(df_pending[['Importer', 'date', 'libelle', 'montant', 'Doublon']], hide_index=True, disabled=['date', 'libelle', 'montant', 'Doublon'], use_container_width=True)
    if st.button("✅ Confirmer l'importation"):
        lignes_a_importer = df_pending[edited_df['Importer']]
        for _, row in lignes_a_importer.iterrows():
            db.execute_query("INSERT INTO transactions (compte_id, date, libelle, montant) VALUES (?,?,?,?)", (row['compte_id'], row['date'], row['libelle'], row['montant']))
        del st.session_state['pending_imports']
        st.rerun()
    if st.button("❌ Annuler l'import"):
        del st.session_state['pending_imports']
        st.rerun()

st.sidebar.title("Fortune")
menu = st.sidebar.radio("Modules", ["Tableau de bord", "Comptes & Enveloppes", "Transactions", "Paramètres"])

if menu == "Tableau de bord":
    dashboard.render()

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
                if st.button("🗑️ Confirmer"):
                    id_supp = c_opts[compte_supp]
                    db.execute_query("DELETE FROM transactions WHERE compte_id = ?", (id_supp,))
                    db.execute_query("DELETE FROM comptes WHERE id = ?", (id_supp,))
                    st.rerun()
        st.markdown("---")
        st.dataframe(db.get_data("SELECT nom, type_compte, solde_initial FROM comptes"), width='stretch')

    with t_env:
        c_ajout_env, c_supp_env = st.columns(2)
        with c_ajout_env:
            df_c = db.get_data("SELECT id, nom FROM comptes")
            if not df_c.empty:
                c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
                with st.form("new_env", clear_on_submit=True):
                    st.subheader("Ouvrir une enveloppe")
                    nom_env = st.text_input("Nom du projet")
                    c_parent = st.selectbox("Compte support", list(c_opts.keys()))
                    objectif = st.number_input("Objectif (€)", value=0.0)
                    if st.form_submit_button("Créer"):
                        if nom_env: db.execute_query("INSERT INTO enveloppes (nom, compte_id, objectif) VALUES (?,?,?)", (nom_env, c_opts[c_parent], objectif)); st.rerun()
        with c_supp_env:
            st.subheader("Supprimer un projet")
            df_env_list = db.get_data("SELECT id, nom FROM enveloppes")
            if not df_env_list.empty:
                e_opts = {r['nom']: r['id'] for _, r in df_env_list.iterrows()}
                env_supp = st.selectbox("Enveloppe à retirer", list(e_opts.keys()))
                if st.button("🗑️ Supprimer le projet"):
                    id_supp = e_opts[env_supp]
                    db.execute_query("UPDATE transactions SET enveloppe_id = NULL WHERE enveloppe_id = ?", (id_supp,))
                    db.execute_query("DELETE FROM provisions WHERE enveloppe_id = ?", (id_supp,))
                    db.execute_query("DELETE FROM regles_recurrentes WHERE enveloppe_id = ?", (id_supp,))
                    db.execute_query("DELETE FROM enveloppes WHERE id = ?", (id_supp,))
                    st.rerun()

        st.markdown("---")
        q_env = """
            SELECT e.nom as Projet, c.nom as Support, e.objectif as Objectif, 
                   IFNULL((SELECT SUM(montant) FROM provisions WHERE enveloppe_id = e.id), 0) as Prov_Brute,
                   IFNULL((SELECT SUM(ABS(montant)) FROM transactions WHERE enveloppe_id = e.id AND montant < 0), 0) as Consomme
            FROM enveloppes e JOIN comptes c ON e.compte_id = c.id
        """
        df_env = db.get_data(q_env)
        if not df_env.empty:
            df_env['Disponible (Net)'] = df_env['Prov_Brute'] - df_env['Consomme']
            df_env['Manquant'] = df_env['Objectif'] - df_env['Disponible (Net)']
            st.dataframe(df_env[['Projet', 'Support', 'Objectif', 'Disponible (Net)', 'Manquant']], hide_index=True, width='stretch')

    with t_auto:
        df_env_list = db.get_data("SELECT id, nom FROM enveloppes")
        if not df_env_list.empty:
            e_opts = {r['nom']: r['id'] for _, r in df_env_list.iterrows()}
            with st.form("new_rule", clear_on_submit=True):
                colA, colB, colC = st.columns(3)
                cible = colA.selectbox("Vers", list(e_opts.keys()))
                m_auto = colB.number_input("Montant (€)", step=10.0)
                d_auto = colC.date_input("Premier virement")
                if st.form_submit_button("Activer"):
                    if m_auto > 0: db.execute_query("INSERT INTO regles_recurrentes (enveloppe_id, montant, prochaine_date) VALUES (?,?,?)", (e_opts[cible], m_auto, d_auto.isoformat())); st.rerun()
            st.markdown("---")
            q_regles = "SELECT r.id, e.nom as Enveloppe, r.montant as Mensualité, r.prochaine_date as Échéance FROM regles_recurrentes r JOIN enveloppes e ON r.enveloppe_id = e.id"
            df_regles = db.get_data(q_regles)
            if not df_regles.empty:
                col_liste, col_action = st.columns([2, 1])
                with col_liste: st.table(df_regles[['Enveloppe', 'Mensualité', 'Échéance']])
                with col_action:
                    r_opts = {f"{r['Enveloppe']} ({r['Mensualité']}€)": r['id'] for _, r in df_regles.iterrows()}
                    regle_supp = st.selectbox("Sélectionner pour retirer", list(r_opts.keys()))
                    if st.button("🗑️ Supprimer"):
                        db.execute_query("DELETE FROM regles_recurrentes WHERE id = ?", (r_opts[regle_supp],)); st.rerun()

elif menu == "Transactions":
    st.title("Gestion des flux")
    tab_import, tab_manuel, tab_triage, tab_abo, tab_hist = st.tabs(["📥 Import CSV", "✍️ Saisie", "⚖️ Triage", "🔄 Abonnements", "📜 Historique & Édition"])

    df_cats = db.get_data("SELECT c1.id, c1.nom, IFNULL(c2.nom, 'P') as parent FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id ORDER BY parent, c1.nom")
    cat_opts = {f"{r['parent']} > {r['nom']}": r['id'] for _, r in df_cats.iterrows()} if not df_cats.empty else {}
    
    df_env_list = db.get_data("SELECT id, nom FROM enveloppes")
    env_opts = {}
    for _, r in df_env_list.iterrows(): env_opts[r['nom']] = r['id']

    with tab_import:
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if not df_c.empty:
            mapping_c = {r['nom']: r['id'] for _, r in df_c.iterrows()}
            c_nom = st.selectbox("Compte de destination", list(mapping_c.keys()))
            up = st.file_uploader("Fichier bancaire (CSV)", type="csv")
            
            if up:
                try:
                    df_csv = pd.read_csv(up, sep=';', encoding='utf-8')
                except:
                    up.seek(0)
                    df_csv = pd.read_csv(up, sep=',', encoding='utf-8')

                cols = df_csv.columns.tolist()
                
                st.markdown("### 🔧 Mappage intelligent des colonnes")
                
                idx_date = cols.index("dateOp") if "dateOp" in cols else 0
                idx_lib = cols.index("label") if "label" in cols else 2 if len(cols) > 2 else 0
                
                c1, c2 = st.columns(2)
                sel_date = c1.selectbox("Colonne des Dates", cols, index=idx_date)
                sel_lib = c2.selectbox("Colonne des Libellés", cols, index=idx_lib)
                
                st.markdown("<br>", unsafe_allow_html=True)
                type_montant = st.radio("Structure des montants dans le fichier :", 
                                        ["Une seule colonne (Négatif pour dépenses, Positif pour revenus) - Ex: Boursorama, N26, Revolut", 
                                         "Deux colonnes séparées (Une pour les Débits, une pour les Crédits) - Ex: Caisse d'Épargne, Crédit Agricole"])
                
                if "Une seule colonne" in type_montant:
                    idx_montant = cols.index("amount") if "amount" in cols else 0
                    sel_montant = st.selectbox("Colonne des Montants", cols, index=idx_montant)
                else:
                    c3, c4 = st.columns(2)
                    sel_deb = c3.selectbox("Colonne Débit (Dépenses)", cols, index=8 if len(cols)>8 else 0)
                    sel_cre = c4.selectbox("Colonne Crédit (Revenus)", cols, index=9 if len(cols)>9 else 0)
                
                if st.button("Lancer l'analyse du fichier"):
                    pending = []
                    for _, row in df_csv.iterrows():
                        if "Une seule colonne" in type_montant:
                            m = logic.clean_amount(row[sel_montant])
                        else:
                            m = logic.clean_amount(row[sel_cre]) + logic.clean_amount(row[sel_deb])
                        
                        raw_date = str(row[sel_date])
                        try:
                            if "-" in raw_date and len(raw_date.split("-")[0]) == 4:
                                parsed_date = pd.to_datetime(raw_date, format="%Y-%m-%d")
                            else:
                                parsed_date = pd.to_datetime(raw_date, dayfirst=True)
                            d = parsed_date.strftime("%d/%m/%Y")
                        except:
                            d = raw_date
                            
                        l = str(row[sel_lib])
                        
                        if m != 0:
                            exist = db.get_data("SELECT id FROM transactions WHERE compte_id=? AND date=? AND libelle=? AND montant=?", (mapping_c[c_nom], d, l, m))
                            pending.append({'Importer': exist.empty, 'Doublon': '⚠️ Oui' if not exist.empty else 'Non', 'date': d, 'libelle': l, 'montant': m, 'compte_id': mapping_c[c_nom]})
                    
                    if pending:
                        st.session_state['pending_imports'] = pending
                        st.rerun()
                    else:
                        st.info("Aucune transaction valide trouvée dans ce fichier.")
                        
        if 'pending_imports' in st.session_state: dialog_doublons()

    with tab_manuel:
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if not df_c.empty:
            with st.form("manual_entry", clear_on_submit=True):
                c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
                c1, c2 = st.columns(2)
                m_compte = c1.selectbox("Compte", list(c_opts.keys()))
                m_date = c2.date_input("Date")
                c3, c4 = st.columns(2)
                m_lib = c3.text_input("Libellé")
                m_montant = c4.number_input("Montant (€)", step=0.01)
                
                env_choices_manual = {"--- Aucune ---": None}
                env_choices_manual.update(env_opts)
                m_env = st.selectbox("Imputer sur une enveloppe", list(env_choices_manual.keys()))
                
                if st.form_submit_button("Ajouter"):
                    if m_lib:
                        date_str = m_date.strftime("%d/%m/%Y")
                        db.execute_query("INSERT INTO transactions (compte_id, date, libelle, montant, enveloppe_id) VALUES (?,?,?,?,?)", (c_opts[m_compte], date_str, m_lib, m_montant, env_choices_manual[m_env]))
                        st.rerun()

    with tab_triage:
        df_un = db.get_data("SELECT t.id, t.date, t.libelle, t.montant FROM transactions t WHERE t.categorie_id IS NULL ORDER BY t.date DESC")
        if df_un.empty: 
            st.success("Aucune transaction en attente.")
        else:
            col_header, col_action1, col_action2 = st.columns([2, 1, 1])
            col_header.write(f"**{len(df_un)}** opérations à classer.")
            
            if col_action1.button("🪄 IA"):
                with st.spinner("Analyse..."):
                    res = logic.suggest_categories()
                    if res >= 0: st.toast(f"{res} classés !"); st.rerun()
                    elif res == -3: st.error("Quota épuisé.")
                    elif res == -1: st.warning("Clé API manquante.")
                    else: st.error("Erreur Gemini.")

            if col_action2.button("⚡ Auto-classer (via Abonnements)"):
                df_abo = db.get_data("SELECT libelle, categorie_id, montant FROM abonnements")
                count_auto = 0
                for _, r_tx in df_un.iterrows():
                    kw_tx = logic.get_keyword(r_tx['libelle'])
                    for _, r_abo in df_abo.iterrows():
                        if logic.get_keyword(r_abo['libelle']) == kw_tx:
                            diff_pct = abs(r_tx['montant'] - r_abo['montant']) / abs(r_abo['montant']) if r_abo['montant'] != 0 else 0
                            if diff_pct <= 0.05:
                                db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (r_abo['categorie_id'], r_tx['id']))
                                count_auto += 1
                            break
                if count_auto > 0:
                    st.success(f"{count_auto} transactions reconnues et classées !")
                else:
                    st.info("Aucune correspondance exacte trouvée.")
                st.rerun()

            st.markdown("---")
            
            df_abo_dict = {}
            for _, r in db.get_data("SELECT libelle, montant FROM abonnements").iterrows():
                kw = logic.get_keyword(r['libelle'])
                if kw: df_abo_dict[kw] = r

            for _, row in df_un.head(10).iterrows():
                kw_tx = logic.get_keyword(row['libelle'])
                matched_abo = df_abo_dict.get(kw_tx)
                alert_msg = ""
                
                if matched_abo is not None:
                    diff_pct = abs(row['montant'] - matched_abo['montant']) / abs(matched_abo['montant']) if matched_abo['montant'] != 0 else 0
                    if diff_pct > 0.05:
                        alert_msg = f"⚠️ Dérive détectée (Prévu : {matched_abo['montant']}€)"

                expander_title = f"{row['date']} | {row['libelle']} | {row['montant']}€"
                if alert_msg: expander_title += f"  —  {alert_msg}"

                with st.expander(expander_title):
                    c_cat, c_env, b_val = st.columns([2, 2, 1])
                    choix_cat = c_cat.selectbox("Catégorie", list(cat_opts.keys()), key=f"t_{row['id']}")
                    
                    env_choices_triage = {"--- Ne pas lier ---": None}
                    env_choices_triage.update(env_opts)
                    choix_env = c_env.selectbox("Dénouer de l'enveloppe", list(env_choices_triage.keys()), key=f"e_{row['id']}")
                    
                    if b_val.button("Valider", key=f"b_{row['id']}"):
                        if kw_tx and len(kw_tx) >= 3:
                            count_sim = db.get_data("SELECT COUNT(*) FROM transactions WHERE libelle LIKE ? AND categorie_id IS NULL AND id != ?", (f"%{kw_tx}%", row['id'])).iloc[0,0]
                            if count_sim > 0: dialog_similaires(row['id'], row['libelle'], kw_tx, cat_opts[choix_cat], choix_cat)
                            else: db.execute_query("UPDATE transactions SET categorie_id = ?, enveloppe_id = ? WHERE id = ?", (cat_opts[choix_cat], env_choices_triage[choix_env], row['id'])); st.rerun()
                        else:
                            db.execute_query("UPDATE transactions SET categorie_id = ?, enveloppe_id = ? WHERE id = ?", (cat_opts[choix_cat], env_choices_triage[choix_env], row['id'])); st.rerun()

    with tab_abo:
        st.subheader("Saisie manuelle d'une récurrence")
        df_c = db.get_data("SELECT id, nom FROM comptes")
        if not df_c.empty:
            c_opts = {r['nom']: r['id'] for _, r in df_c.iterrows()}
            with st.form("new_abo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                a_lib = col1.text_input("Nom de l'abonnement/Revenu")
                a_mont = col2.number_input("Montant (€)", step=0.01)
                
                col3, col4, col5 = st.columns(3)
                a_freq = col3.selectbox("Fréquence", ["MENSUEL", "ANNUEL"])
                a_cat = col4.selectbox("Catégorie", list(cat_opts.keys()))
                a_compte = col5.selectbox("Compte", list(c_opts.keys()))
                
                if st.form_submit_button("Ajouter aux prévisions"):
                    if a_lib:
                        db.execute_query("INSERT INTO abonnements (libelle, montant, frequence, compte_id, categorie_id) VALUES (?,?,?,?,?)", (a_lib, a_mont, a_freq, c_opts[a_compte], cat_opts[a_cat]))
                        st.rerun()
            
            st.markdown("---")
            st.subheader("Abonnements et Revenus actifs")
            q_abo = """
                SELECT a.id, a.libelle, a.montant, a.frequence, c.nom as compte, IFNULL(cat.nom, '---') as categorie
                FROM abonnements a 
                JOIN comptes c ON a.compte_id = c.id
                LEFT JOIN categories cat ON a.categorie_id = cat.id
            """
            df_abo = db.get_data(q_abo)
            if not df_abo.empty:
                st.write("🎛️ Filtres")
                col_fa1, col_fa2 = st.columns(2)
                abo_cats = col_fa1.multiselect("Catégories", df_abo['categorie'].unique().tolist(), default=df_abo['categorie'].unique().tolist())
                abo_freqs = col_fa2.multiselect("Fréquences", df_abo['frequence'].unique().tolist(), default=df_abo['frequence'].unique().tolist())
                
                df_abo_filtered = df_abo[(df_abo['categorie'].isin(abo_cats)) & (df_abo['frequence'].isin(abo_freqs))]
                
                col_list, col_del = st.columns([2, 1])
                with col_list:
                    st.dataframe(df_abo_filtered[['libelle', 'montant', 'frequence', 'categorie', 'compte']], hide_index=True, width='stretch')
                with col_del:
                    abo_opts = {f"{r['libelle']} ({r['montant']}€)": r['id'] for _, r in df_abo_filtered.iterrows()}
                    if abo_opts:
                        abo_del = st.selectbox("Supprimer une règle", list(abo_opts.keys()))
                        if st.button("🗑️ Retirer la règle"):
                            db.execute_query("DELETE FROM abonnements WHERE id = ?", (abo_opts[abo_del],))
                            st.rerun()

    with tab_hist:
        q_hist = """
            SELECT t.id, t.date, t.libelle, t.montant, c.nom as compte, 
                   IFNULL(cat.nom, '---') as categorie, 
                   IFNULL(e.nom, '---') as enveloppe,
                   t.compte_id, t.categorie_id
            FROM transactions t 
            JOIN comptes c ON t.compte_id = c.id 
            LEFT JOIN categories cat ON t.categorie_id = cat.id 
            LEFT JOIN enveloppes e ON t.enveloppe_id = e.id 
            ORDER BY t.date DESC
        """
        df_all = db.get_data(q_hist)
        
        if not df_all.empty:
            df_all['date_dt'] = pd.to_datetime(df_all['date'], format='%d/%m/%Y', errors='coerce')
            
            st.markdown("### 🎛️ Filtres de l'historique")
            cf1, cf2, cf3, cf4 = st.columns(4)
            
            min_date, max_date = df_all['date_dt'].min(), df_all['date_dt'].max()
            if pd.notna(min_date) and pd.notna(max_date):
                min_date_d, max_date_d = min_date.date(), max_date.date()
                dates_sel = cf1.date_input("Période", [min_date_d, max_date_d], min_value=min_date_d, max_value=max_date_d)
            else:
                dates_sel = []
                
            liste_comptes = df_all['compte'].unique().tolist()
            comptes_sel = cf2.multiselect("Comptes", liste_comptes, default=liste_comptes)
                
            liste_cats = df_all['categorie'].unique().tolist()
            cats_sel = cf3.multiselect("Catégories", liste_cats, default=liste_cats)
            
            recherche = cf4.text_input("🔍 Recherche (Libellé)")
            
            df_filtered = df_all.copy()
            if len(dates_sel) == 2:
                start_date, end_date = pd.to_datetime(dates_sel[0]), pd.to_datetime(dates_sel[1])
                df_filtered = df_filtered[(df_filtered['date_dt'] >= start_date) & (df_filtered['date_dt'] <= end_date)]
                
            df_filtered = df_filtered[df_filtered['compte'].isin(comptes_sel)]
            df_filtered = df_filtered[df_filtered['categorie'].isin(cats_sel)]
            if recherche:
                df_filtered = df_filtered[df_filtered['libelle'].str.contains(recherche, case=False, na=False)]
                
            df_filtered = df_filtered.drop(columns=['date_dt'])
            
            if not df_filtered.empty:
                df_edit = df_filtered[['id', 'date', 'libelle', 'montant', 'compte', 'categorie', 'enveloppe']].copy()
                df_edit.insert(0, 'Sélection', False)
                
                st.markdown("---")
                edited_df = st.data_editor(
                    df_edit,
                    column_config={"Sélection": st.column_config.CheckboxColumn(required=True)},
                    disabled=['date', 'libelle', 'montant', 'compte', 'categorie', 'enveloppe'],
                    hide_index=True,
                    use_container_width=True
                )
                
                selected_rows = edited_df[edited_df['Sélection']]
                
                if not selected_rows.empty:
                    st.markdown("### 🛠️ Action Chirurgicale sur la sélection")
                    with st.form("bulk_edit_form"):
                        c1, c2, c3 = st.columns(3)
                        new_lib = c1.text_input("Nouveau Libellé (Vide = ignorer)")
                        new_montant_str = c2.text_input("Nouveau Montant (€) (Vide = ignorer)")
                        
                        cat_choices = {"--- Ne pas modifier ---": -1, "--- DÉCLASSER ---": None}
                        cat_choices.update(cat_opts)
                        new_cat = c3.selectbox("Nouvelle Catégorie", list(cat_choices.keys()))
                        
                        c4, c5 = st.columns(2)
                        env_choices = {"--- Ne pas modifier ---": -1, "--- DÉTACHER ---": None}
                        env_choices.update(env_opts)
                        new_env = c4.selectbox("Affectation Enveloppe", list(env_choices.keys()))
                        
                        new_freq = c5.selectbox("Périodicité (Projection future)", ["--- Ne rien faire ---", "MENSUEL", "ANNUEL"])
                        
                        if st.form_submit_button("Appliquer les modifications"):
                            parsed_montant = None
                            if new_montant_str:
                                try:
                                    parsed_montant = float(new_montant_str.replace(',', '.'))
                                except ValueError:
                                    st.error("Format de montant invalide. Utilisez des chiffres (ex: -15.50).")
                                    st.stop()

                            for _, row in selected_rows.iterrows():
                                tx_id = row['id']
                                orig_tx = df_filtered[df_filtered['id'] == tx_id].iloc[0]
                                
                                if new_lib: db.execute_query("UPDATE transactions SET libelle = ? WHERE id = ?", (new_lib, tx_id))
                                if parsed_montant is not None: db.execute_query("UPDATE transactions SET montant = ? WHERE id = ?", (parsed_montant, tx_id))
                                if cat_choices[new_cat] != -1: db.execute_query("UPDATE transactions SET categorie_id = ? WHERE id = ?", (cat_choices[new_cat], tx_id))
                                if env_choices[new_env] != -1: db.execute_query("UPDATE transactions SET enveloppe_id = ? WHERE id = ?", (env_choices[new_env], tx_id))
                                    
                                if new_freq != "--- Ne rien faire ---":
                                    lib_final = new_lib if new_lib else orig_tx['libelle']
                                    montant_final = parsed_montant if parsed_montant is not None else orig_tx['montant']
                                    cat_final = cat_choices[new_cat] if cat_choices[new_cat] != -1 else orig_tx['categorie_id']
                                    cat_final = int(cat_final) if pd.notna(cat_final) else None
                                    db.execute_query("INSERT INTO abonnements (libelle, montant, frequence, compte_id, categorie_id) VALUES (?,?,?,?,?)", 
                                                     (lib_final, montant_final, new_freq, int(orig_tx['compte_id']), cat_final))
                            st.rerun()
            else:
                st.info("Aucune transaction ne correspond à ces filtres.")
        else:
            st.info("L'historique global est vide.")

elif menu == "Paramètres":
    st.title("Référentiel & Configuration")
    t1, t2 = st.tabs(["Catégories", "🔑 Clé API"])
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
        search_term = st.text_input("🔍 Rechercher une catégorie existante", "")
        
        df_cat = db.get_data("SELECT c1.id, c1.nom, c1.parent_id, IFNULL(c2.nom, 'P') as parent_nom FROM categories c1 LEFT JOIN categories c2 ON c1.parent_id = c2.id ORDER BY parent_nom DESC, c1.nom ASC")
        
        if not df_cat.empty:
            if search_term:
                df_cat = df_cat[df_cat['nom'].str.contains(search_term, case=False, na=False) | df_cat['parent_nom'].str.contains(search_term, case=False, na=False)]
            
            if df_cat.empty:
                st.info("Aucune catégorie ne correspond à cette recherche.")
            else:
                cols = st.columns([2, 2, 1, 1])
                cols[0].write("**Nom**")
                cols[1].write("**Parent**")
                cols[2].write("**Éditer**")
                cols[3].write("**Supprimer**")
                
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
                            st.session_state[e_key] = False; st.rerun()
                    else:
                        c_nom.write(row['nom']); c_par.write(f"`{row['parent_nom']}`")
                        if c_edit.button("📝", key=f"e_{row['id']}"): st.session_state[e_key] = True; st.rerun()
                        if c_del.button("🗑️", key=f"d_{row['id']}"):
                            db.execute_query("UPDATE transactions SET categorie_id = NULL WHERE categorie_id = ?", (row['id'],))
                            db.execute_query("DELETE FROM categories WHERE id = ?", (row['id'],)); st.rerun()

    with t2:
        current_key = db.get_config("GEMINI_API_KEY") or ""
        new_key = st.text_input("Clé API Google Gemini", value=current_key, type="password")
        if st.button("Sauvegarder"): db.set_config("GEMINI_API_KEY", new_key); st.success("Clé enregistrée.")