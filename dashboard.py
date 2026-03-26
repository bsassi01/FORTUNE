import streamlit as st
import database as db
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import calendar

@st.dialog("🏷️ Sélection des catégories")
def dialog_filtre_categories(liste_parents):
    st.write("Coche les catégories à inclure dans l'analyse :")
    tout_cocher = st.checkbox("Tout sélectionner", value=True)
    nouvelle_selection = []
    for p in liste_parents:
        if st.checkbox(p, value=tout_cocher, key=f"filt_{p}"): nouvelle_selection.append(p)
    if st.button("Appliquer les filtres"):
        st.session_state['parents_selectionnes'] = nouvelle_selection
        st.rerun()

def render():
    st.title("Cockpit Analytique & Patrimonial")
    
    # 1. RÉCUPÉRATION DES DONNÉES BRUTES
    query_tx = """
        SELECT t.date, t.libelle, t.montant, c.nom as compte, c.type_compte,
               IFNULL(cat.nom, 'À trier') as categorie, 
               IFNULL(p_cat.nom, IFNULL(cat.nom, 'À trier')) as parent
        FROM transactions t JOIN comptes c ON t.compte_id = c.id
        LEFT JOIN categories cat ON t.categorie_id = cat.id
        LEFT JOIN categories p_cat ON cat.parent_id = p_cat.id
    """
    df_tx = db.get_data(query_tx)
    df_comptes = db.get_data("SELECT nom, type_compte, solde_initial FROM comptes")

    # Définition stricte des barrières temporelles
    today = datetime.date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_month = datetime.date(today.year, today.month, last_day)

    today_dt = pd.to_datetime(today)
    eom_dt = pd.to_datetime(end_of_month)

    # Calcul chirurgical des soldes (Aujourd'hui vs Fin de mois)
    if not df_tx.empty:
        df_tx['date'] = pd.to_datetime(df_tx['date'], format='%d/%m/%Y', errors='coerce')
        df_tx = df_tx.dropna(subset=['date'])
        
    if not df_tx.empty:
        df_tx['Mois-Année'] = df_tx['date'].dt.to_period('M').astype(str)

        df_past = df_tx[df_tx['date'] <= today_dt]
        sum_past = df_past.groupby('compte')['montant'].sum().reset_index().rename(columns={'montant': 'montant_past'})

        df_eom = df_tx[df_tx['date'] <= eom_dt]
        sum_eom = df_eom.groupby('compte')['montant'].sum().reset_index().rename(columns={'montant': 'montant_eom'})

        df_bilan = df_comptes.merge(sum_past, left_on='nom', right_on='compte', how='left').fillna(0)
        df_bilan = df_bilan.merge(sum_eom, left_on='nom', right_on='compte', how='left').fillna(0)

        df_bilan['Solde Actuel'] = df_bilan['solde_initial'] + df_bilan['montant_past']
        df_bilan['Solde Fin Mois'] = df_bilan['solde_initial'] + df_bilan['montant_eom']
    else:
        df_bilan = df_comptes.copy()
        if not df_bilan.empty:
            df_bilan['Solde Actuel'] = df_bilan['solde_initial']
            df_bilan['Solde Fin Mois'] = df_bilan['solde_initial']

    fortune_totale = df_bilan['Solde Actuel'].sum() if not df_bilan.empty else 0
    fortune_fin_mois = df_bilan['Solde Fin Mois'].sum() if not df_bilan.empty else 0

    # Calcul des provisions
    q_calc = """
        SELECT e.id,
               IFNULL((SELECT SUM(montant) FROM provisions WHERE enveloppe_id = e.id), 0) as prov,
               IFNULL((SELECT SUM(ABS(montant)) FROM transactions WHERE enveloppe_id = e.id AND montant < 0), 0) as cons
        FROM enveloppes e
    """
    df_calc = db.get_data(q_calc)
    fonds_sequestres = 0
    if not df_calc.empty:
        df_calc['dispo'] = df_calc['prov'] - df_calc['cons']
        fonds_sequestres = df_calc[df_calc['dispo'] > 0]['dispo'].sum()

    reste_a_vivre = fortune_totale - fonds_sequestres

    # 2. CENTRE DE CONTRÔLE (FILTRES AVANCÉS)
    # Valeurs de sécurité par défaut pour éviter tout crash si la base est vide
    dates_sel = ()
    comptes_exclus = []
    cats_exclues = []
    exclure_internes = True
    recherche = ""

    with st.expander("🎛️ Centre de Contrôle & Exclusions (Affiner les données)", expanded=False):
        if df_tx.empty:
            st.warning("Importez des transactions pour utiliser les filtres.")
        else:
            col_f1, col_f2, col_f3 = st.columns(3)
            
            min_date = df_tx['date'].min().date()
            max_date = df_tx['date'].max().date()
            
            dates_sel = col_f1.date_input("Période d'analyse (Graphiques)", value=(min_date, max_date), min_value=min_date, max_value=max_date)
            
            liste_comptes = df_tx['compte'].unique().tolist()
            comptes_exclus = col_f2.multiselect("❌ Comptes à exclure", liste_comptes, default=[])
            
            liste_parents = df_tx['parent'].unique().tolist()
            cats_exclues = col_f3.multiselect("❌ Catégories à exclure manuellement", liste_parents, default=[])

            c_rec1, c_rec2 = st.columns([2, 1])
            recherche = c_rec1.text_input("🔍 Isoler un libellé (mot-clé)")
            
            st.markdown("<br>", unsafe_allow_html=True)
            exclure_internes = st.checkbox("Filtrer automatiquement les mouvements internes (Recommandé)", value=True)

            # Application stricte des filtres
            if isinstance(dates_sel, tuple) and len(dates_sel) == 2:
                start_date, end_date = pd.to_datetime(dates_sel[0]), pd.to_datetime(dates_sel[1])
                df_tx = df_tx[(df_tx['date'] >= start_date) & (df_tx['date'] <= end_date)]
            
            df_tx = df_tx[~df_tx['compte'].isin(comptes_exclus)]
            df_tx = df_tx[~df_tx['parent'].isin(cats_exclues)]
            
            if exclure_internes:
                df_tx = df_tx[~df_tx['parent'].str.contains('interne', case=False, na=False)]
                df_tx = df_tx[~df_tx['categorie'].str.contains('interne', case=False, na=False)]
            
            if recherche:
                df_tx = df_tx[df_tx['libelle'].str.contains(recherche, case=False, na=False)]

    st.markdown("---")

    # 3. DIMENSIONS TEMPORELLES (ONGLETS)
    tab_present, tab_passe, tab_futur = st.tabs(["⏱️ L'Instant T (Patrimoine)", "📉 Le Rétroviseur (Historique)", "🔮 Le Radar (Prévisions)"])

    # ==========================================
    # ONGLET 1 : L'INSTANT T
    # ==========================================
    with tab_present:
        st.subheader("Photographie de la Liquidité")
        
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)
        col_k1.metric("Fortune Nette (Aujourd'hui)", f"{fortune_totale:,.2f} €".replace(',', ' '))
        col_k2.metric("Provisions Engagées", f"- {fonds_sequestres:,.2f} €".replace(',', ' '))
        col_k3.metric("Reste à Vivre (Aujourd'hui)", f"{reste_a_vivre:,.2f} €".replace(',', ' '))
        
        delta_fin_mois = fortune_fin_mois - fortune_totale
        col_k4.metric("Atterrissage Fin de Mois", f"{fortune_fin_mois:,.2f} €".replace(',', ' '), delta=f"{delta_fin_mois:+,.2f} €", delta_color="normal")

        st.markdown("<br>", unsafe_allow_html=True)
        col_p1, col_p2 = st.columns([2, 3])
        
        with col_p1:
            st.write("**Allocation par type de support (Soldes Actuels)**")
            if not df_bilan.empty and 'Solde Actuel' in df_bilan.columns:
                df_bilan_pos = df_bilan[df_bilan['Solde Actuel'] > 0]
                if not df_bilan_pos.empty:
                    fig_alloc = px.pie(df_bilan_pos, values='Solde Actuel', names='type_compte', hole=0.5, color_discrete_sequence=px.colors.sequential.Teal)
                    fig_alloc.update_traces(textposition='inside', textinfo='percent+label')
                    fig_alloc.update_layout(margin=dict(t=0, l=0, r=0, b=0), showlegend=False)
                    st.plotly_chart(fig_alloc, width='stretch')
        
        with col_p2:
            st.write("**Détail des Soldes Bancaires**")
            if not df_bilan.empty and 'Solde Actuel' in df_bilan.columns:
                df_bilan_display = df_bilan.copy().sort_values(by='Solde Actuel', ascending=False)
                df_bilan_display['Solde Actuel'] = df_bilan_display['Solde Actuel'].apply(lambda x: f"{x:,.2f} €".replace(',', ' '))
                df_bilan_display['Solde Fin Mois'] = df_bilan_display['Solde Fin Mois'].apply(lambda x: f"{x:,.2f} €".replace(',', ' '))
                st.dataframe(df_bilan_display[['nom', 'type_compte', 'Solde Actuel', 'Solde Fin Mois']].rename(columns={'nom': 'Compte', 'type_compte': 'Type'}), hide_index=True, width='stretch')

    # ==========================================
    # ONGLET 2 : LE RÉTROVISEUR (HISTORIQUE)
    # ==========================================
    with tab_passe:
        if df_tx.empty:
            st.info("Aucune donnée historique correspondant à vos filtres.")
        else:
            total_entrees = df_tx[df_tx['montant'] > 0]['montant'].sum()
            total_sorties = df_tx[df_tx['montant'] < 0]['montant'].sum()
            cash_flow = total_entrees + total_sorties

            st.subheader(f"Analyse des Flux de la période sélectionnée")
            col_h1, col_h2, col_h3 = st.columns(3)
            col_h1.metric("Total Entrées", f"+{total_entrees:,.2f} €".replace(',', ' '))
            col_h2.metric("Total Sorties", f"{total_sorties:,.2f} €".replace(',', ' '))
            col_h3.metric("Cashflow Opérationnel", f"{cash_flow:,.2f} €".replace(',', ' '), delta="Positif" if cash_flow > 0 else "Négatif", delta_color="normal" if cash_flow > 0 else "inverse")

            st.markdown("---")
            
            c_hist1, c_hist2 = st.columns([3, 2])
            
            with c_hist1:
                st.write("**Cascade de rentabilité (Mois par Mois)**")
                df_flux = df_tx.groupby('Mois-Année')['montant'].sum().reset_index().sort_values(by='Mois-Année')
                fig_waterfall = go.Figure(go.Waterfall(
                    x=df_flux['Mois-Année'],
                    y=df_flux['montant'],
                    measure=["relative"] * len(df_flux),
                    text=df_flux['montant'].apply(lambda x: f"{x:,.0f}"),
                    textposition="outside",
                    decreasing={"marker": {"color": "#e74c3c"}},
                    increasing={"marker": {"color": "#2ecc71"}}
                ))
                fig_waterfall.update_layout(margin=dict(t=20, l=10, r=10, b=10))
                st.plotly_chart(fig_waterfall, width='stretch')

            with c_hist2:
                st.write("**Cartographie des charges (Treemap interactif)**")
                df_dep = df_tx[df_tx['montant'] < 0].copy()
                if not df_dep.empty:
                    df_dep['montant_abs'] = df_dep['montant'].abs()
                    fig_tree = px.treemap(
                        df_dep, 
                        path=[px.Constant("Charges"), 'parent', 'categorie', 'libelle'], 
                        values='montant_abs', 
                        color='montant_abs', 
                        color_continuous_scale='Reds'
                    )
                    fig_tree.update_traces(
                        textinfo="label+value",
                        texttemplate="%{label}<br>%{value:.2f} €",
                        hovertemplate="<b>%{label}</b><br>Total : %{value:.2f} €<extra></extra>"
                    )
                    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0))
                    st.plotly_chart(fig_tree, width='stretch')
                else:
                    st.info("Aucune charge à afficher.")

            st.write("**Matrice de traque (Audit Catégoriel)**")
            if not df_dep.empty:
                pivot_df = pd.pivot_table(df_dep, values='montant_abs', index='parent', columns='Mois-Année', aggfunc='sum', fill_value=0)
                pivot_df['Total Période'] = pivot_df.sum(axis=1)
                pivot_df = pivot_df.sort_values(by='Total Période', ascending=False)
                st.dataframe(pivot_df.style.format("{:,.0f} €").background_gradient(cmap='Reds', axis=None, subset=pivot_df.columns[:-1]), width='stretch')

                st.markdown("### 🔬 Inspection détaillée (Scalpel)")
                cat_a_inspecter = st.selectbox("Sélectionne une catégorie principale pour examiner ses opérations exactes :", ["--- Choisir ---"] + pivot_df.index.tolist())
                
                if cat_a_inspecter != "--- Choisir ---":
                    df_detail = df_dep[df_dep['parent'] == cat_a_inspecter].sort_values(by='date', ascending=False)
                    df_detail['Date'] = df_detail['date'].dt.strftime('%d/%m/%Y')
                    df_detail['Montant'] = df_detail['montant'].apply(lambda x: f"{x:,.2f} €".replace(',', ' '))
                    st.dataframe(
                        df_detail[['Date', 'libelle', 'categorie', 'compte', 'Montant']].rename(columns={'libelle': 'Opération', 'categorie': 'Sous-Catégorie', 'compte': 'Compte débité'}), 
                        hide_index=True, 
                        width='stretch'
                    )

    # ==========================================
    # ONGLET 3 : LE RADAR (PRÉVISIONS)
    # ==========================================
    with tab_futur:
        st.subheader("Modélisation Financière (Stress Test à 12 mois)")
        
        df_abo = db.get_data("SELECT libelle, montant, frequence FROM abonnements")
        if df_abo.empty:
            st.warning("⚠️ Déclarez vos revenus et charges récurrentes dans l'onglet 'Transactions > Abonnements' pour activer le radar.")
        else:
            df_abo['montant_mensuel'] = df_abo.apply(lambda x: x['montant'] if x['frequence'] == 'MENSUEL' else x['montant'] / 12, axis=1)
            rev_fixes = df_abo[df_abo['montant_mensuel'] > 0]['montant_mensuel'].sum()
            ch_fixes = df_abo[df_abo['montant_mensuel'] < 0]['montant_mensuel'].sum()
            rav_theorique = rev_fixes + ch_fixes

            c_fut1, c_fut2 = st.columns([1, 2])
            
            with c_fut1:
                st.write("**Socle Structurel (Lissé par mois)**")
                st.metric("Revenus Assurés", f"+{rev_fixes:,.2f} €".replace(',', ' '))
                st.metric("Charges Incompressibles", f"{ch_fixes:,.2f} €".replace(',', ' '))
                st.metric("Reste à Vivre Théorique", f"{rav_theorique:,.2f} €".replace(',', ' '))
                
                st.markdown("---")
                val_defaut = int(rav_theorique * 0.7) if rav_theorique > 0 else 0
                depenses_variables = st.number_input("Estimez vos dépenses variables mensuelles (Courses, loisirs...)", value=val_defaut, step=50)

            with c_fut2:
                st.write("**Projection du Solde Global**")
                epargne_nette = rav_theorique - depenses_variables
                
                today = datetime.date.today()
                proj_data = []
                current_solde = reste_a_vivre

                for i in range(13):
                    if i == 0:
                        month_label = "Aujourd'hui (Dispo)"
                    else:
                        target_month = today.month + i
                        target_year = today.year + (target_month - 1) // 12
                        target_month = (target_month - 1) % 12 + 1
                        month_label = f"{target_year}-{str(target_month).zfill(2)}"
                        current_solde += epargne_nette

                    proj_data.append({"Mois": month_label, "Capital Projeté": current_solde})

                df_proj = pd.DataFrame(proj_data)
                
                fig_proj = px.area(df_proj, x="Mois", y="Capital Projeté", markers=True)
                fig_proj.update_traces(line_color='#3498db', fillcolor='rgba(52, 152, 219, 0.2)')
                
                if df_proj['Capital Projeté'].min() < 0:
                    fig_proj.add_hline(y=0, line_dash="dash", line_color="#e74c3c", annotation_text="Risque d'insolvabilité", annotation_position="top left")
                
                fig_proj.update_layout(margin=dict(t=10, l=10, r=10, b=10))
                st.plotly_chart(fig_proj, width='stretch')
                
                if epargne_nette > 0:
                    st.success(f"D'après cette simulation, vous capitalisez **{epargne_nette:,.2f} € / mois**.")
                else:
                    st.error(f"Déficit structurel : **{epargne_nette:,.2f} € / mois**. Vous brûlez votre capital.")