import pandas as pd
import streamlit as st
import numpy as np
import re
import io
import altair as alt
from datetime import datetime

# ============================
#  CONSTANTES DE CONVERSION
# ============================
usd_to_eur = 0.86      # Taux de conversion USD → EUR
gbp_to_eur = 1.15      # Taux de conversion GBP → EUR
chf_to_eur = 1.07      # Taux de conversion CHF → EUR
eur_to_tnd = 3.5       # Taux de conversion EUR → TND

# ============================
#  CHARGEMENT DES DONNÉES
# ============================
# Lecture du fichier CSV contenant la liste des masters
df = pd.read_csv("master-fees-app/masters.csv")

# ============================
#  FONCTION : Conversion des frais
# ============================
def convert_to_eur(fee):
    """
    Convertit les frais d'inscription (quelle que soit la devise)
    en euros.

    Paramètres:
        fee (str | float): Frais d'inscription (ex: '90$', '80 GBP')

    Retour:
        float: Montant converti en EUR
    """
    if pd.isna(fee):
        return 0

    # Nettoyage de la valeur (suppression des espaces, caractères spéciaux)
    fee_str = str(fee).upper().strip().replace(" ", "").replace(" ", "")

    # Détection de la devise
    if "GBP" in fee_str or "£" in fee_str:
        currency = "GBP"
    elif "$" in fee_str:
        currency = "USD"
    elif "CHF" in fee_str:
        currency = "CHF"
    else:
        currency = "EUR"

    # Extraction du montant numérique
    match = re.search(r"(\d+)", fee_str)
    if not match:
        return 0
    amount = float(match.group(1))

    # Conversion selon la devise détectée
    if currency == "GBP":
        return amount * gbp_to_eur
    elif currency == "USD":
        return amount * usd_to_eur
    elif currency == "CHF":
        return amount * chf_to_eur
    return amount

# Ajout de la colonne "Frais en EUR" au DataFrame
df["Frais en EUR"] = df["Frais de candidature"].apply(convert_to_eur)
df["Sélectionner"] = False  # Colonne de sélection
df.index = range(1, len(df) + 1)
df.index.name = "Rang HF"

# ============================
#  FONCTION : Tri du DataFrame
# ============================
def sort_dataframe(df, colonne):
    """
    Trie le DataFrame selon la colonne sélectionnée.

    Paramètres:
        df (pd.DataFrame): Le tableau des masters
        colonne (str): La colonne de tri

    Retour:
        pd.DataFrame: Tableau trié
    """
    if colonne == "Rang HF":
        return df

    elif colonne == "Date limite de candidature":
        # Nettoyage des dates
        cleaned_dates = (
            df[colonne]
            .astype(str)
            .str.replace(r"\(.*\)", "", regex=True)  # Supprimer "(estimée)"
            .str.strip()
            .str.upper()
        )
        cleaned_dates = cleaned_dates.str.replace(r"^(\d) ", r"0\1 ", regex=True)

        # Conversion en datetime
        df["Date triée"] = pd.to_datetime(cleaned_dates, format="%d %b %Y", errors="coerce")

        # Score de tri personnalisé
        def compute_sort_score(date):
            if pd.isna(date):
                return float("inf")
            month_score = date.month * 100
            year_score = 10000 if date.year == 2025 else 20000 if date.year == 2026 else date.year * 10000
            return year_score + month_score + date.day

        df["Sort_Score"] = df["Date triée"].apply(compute_sort_score)
        df = df.sort_values(by="Sort_Score", ascending=True)
        df = df.drop(columns=["Date triée", "Sort_Score"])
        return df

    elif colonne == "Frais de candidature":
        return df.sort_values(by="Frais en EUR", ascending=False)

    elif colonne in ["Taux d'acceptance", "Taux d'emploi à 3 mois"]:
        # Nettoyage des pourcentages
        def nettoyer_taux(series):
            return (
                series.astype(str)
                .str.replace(r"[^\d\.]", "", regex=True)
                .replace("", "0")
                .astype(float)
            )
        return df.sort_values(by=colonne, key=nettoyer_taux, ascending=False)

    elif colonne == "Classement Risk.net":
        return df.sort_values(
            by=colonne,
            key=lambda x: pd.to_numeric(
                x.astype(str).str.extract(r"(\d+)")[0],
                errors="coerce"
            ).fillna(9999)
        )

# ============================
#  INTERFACE STREAMLIT
# ============================
st.title("Calculateur de frais de candidature des masters")

# Sélecteur de colonne de tri
colonne_tri = st.selectbox(
    "Trier le tableau par :",
    [
        "Rang HF",
        "Date limite de candidature",
        "Frais de candidature",
        "Taux d'acceptance",
        "Taux d'emploi à 3 mois",
        "Classement Risk.net"
    ]
)

# Tri du DataFrame
df = sort_dataframe(df, colonne_tri)

# Détection dynamique des colonnes de noms et d'universités
colonne_nom = next((c for c in df.columns if "programme" in c.lower() or "master" in c.lower() or "name" in c.lower()), None)
colonne_universite = next((c for c in df.columns if "université" in c.lower() or "university" in c.lower()), None)

# Mode compact
affichage_compact = st.toggle("Mode compact")
if affichage_compact:
    colonnes_affichage = ["Sélectionner"]
    if colonne_universite:
        colonnes_affichage.append(colonne_universite)
    colonnes_affichage.append("Frais de candidature")
else:
    colonnes_affichage = [c for c in df.columns if c not in ["Frais en EUR"]]

# Éditeur interactif
edited_df = st.data_editor(
    df[colonnes_affichage],
    column_config={"Sélectionner": st.column_config.CheckboxColumn("Sélectionner")},
    disabled=[c for c in colonnes_affichage if c != "Sélectionner"],
    use_container_width=True
)

df["Sélectionner"] = edited_df["Sélectionner"]
selected_df = df[df["Sélectionner"]]

# ============================
#  CALCUL DES FRAIS TOTAUX
# ============================
if not selected_df.empty:
    frais_base = selected_df["Frais en EUR"].sum()

    # Frais supplémentaires GRE/TOEFL si > 4 masters
    frais_supp = (len(selected_df) - 4) * 60 * usd_to_eur if len(selected_df) > 4 else 0
    total = frais_base + frais_supp
    total_tnd = total * eur_to_tnd

    st.write(f"### Programmes sélectionnés : {len(selected_df)}")
    st.write(f"Frais de base : {frais_base:,.2f} €")

    if len(selected_df) > 4:
        st.write(f"Frais supplémentaires (GRE/TOEFL) : {frais_supp:,.2f} €")
        st.caption("💡 Les frais supplémentaires s'appliquent si vous postulez à plus de 4 masters. Chaque master supplémentaire nécessite 60 $ pour envoyer vos scores GRE/TOEFL via ETS.")
    else:
        st.write(f"Frais supplémentaires (GRE/TOEFL) : {frais_supp:,.2f} €")
        st.caption("Aucun frais supplémentaire : l'envoi des scores GRE/TOEFL pour 4 masters est inclus.")

    st.write(f"### Total : {total:,.2f} € ({total_tnd:,.2f} TND)")
    st.caption(f"💱 Taux de change appliqué : 1 EUR = {eur_to_tnd} TND")

    # Export Excel
    buffer = io.BytesIO()
    selected_df.to_excel(buffer, index=False)
    st.download_button(
        label="📥 Télécharger la sélection en Excel",
        data=buffer,
        file_name="masters_selectionnes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Visualisation graphique
    if not selected_df.empty:
        colonne_y = colonne_nom if not affichage_compact else (colonne_universite or colonne_nom)
        if colonne_y:
            chart = alt.Chart(selected_df).mark_bar().encode(
                x=alt.X("Frais en EUR", title="Frais (€)"),
                y=alt.Y(f"{colonne_y}:N", title="Programme/Université", sort='-x'),
                color="Frais en EUR"
            ).properties(title="Frais par programme sélectionné")
            st.altair_chart(chart, use_container_width=True)

else:
    st.write("Aucun programme sélectionné.")
