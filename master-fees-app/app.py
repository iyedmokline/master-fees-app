import pandas as pd
import streamlit as st
import re
from datetime import datetime

# === Taux de conversion ===
usd_to_eur = 0.86
gbp_to_eur = 1.15
chf_to_eur = 1.07
eur_to_tnd = 3.5

# === Charger le fichier CSV ===
df = pd.read_csv("Corrected_Masters_Quant_Table__B_Tier_for_19-20__C_Tier_from_21_.csv")

# === Conversion des frais en euros ===
def convert_to_eur(fee):
    if pd.isna(fee):
        return 0
    fee_str = str(fee).upper().strip().replace(" ", "").replace(" ", "")
    if "GBP" in fee_str or "£" in fee_str:
        currency = "GBP"
    elif "$" in fee_str:
        currency = "USD"
    elif "CHF" in fee_str:
        currency = "CHF"
    else:
        currency = "EUR"
    match = re.search(r"(\d+)", fee_str)
    if not match:
        return 0
    amount = float(match.group(1))
    if currency == "GBP":
        return amount * gbp_to_eur
    elif currency == "USD":
        return amount * usd_to_eur
    elif currency == "CHF":
        return amount * chf_to_eur
    return amount

df["Frais en EUR"] = df["Frais de candidature"].apply(convert_to_eur)

# Ajouter la colonne de sélection
df["Sélectionner"] = False

# Réindexer à partir de 1
df.index = range(1, len(df) + 1)
df.index.name = "Classement ChatGPT"

# === Fonctions de tri ===
def sort_dataframe(df, colonne):
    if colonne == "Classement ChatGPT":
        return df
    elif colonne == "Catégorie visant les carrières quant":
        ordre = {"A+ Tier": 1, "A Tier": 2, "B Tier": 3, "C Tier": 4}
        return df.sort_values(by=colonne, key=lambda x: x.map(ordre))
    elif colonne == "Date limite de candidature":
        # Nettoyer les dates (enlever "(estimée)")
        cleaned_dates = (
            df[colonne]
            .astype(str)
            .str.replace(r"\(.*\)", "", regex=True)  # Retirer "(estimée)"
            .str.strip()
            .str.upper()
        )

        # Ajouter zéro devant les jours à un chiffre
        cleaned_dates = cleaned_dates.str.replace(r"^(\d) ", r"0\1 ", regex=True)

        # Conversion en datetime
        df["Date triée"] = pd.to_datetime(cleaned_dates, format="%d %b %Y", errors="coerce")

        # Supprimer les lignes sans date (mettre en bas)
        df["Date triée"] = df["Date triée"].fillna(pd.Timestamp.max)

        # Trier uniquement sur la date normalisée
        df = df.sort_values(by="Date triée", ascending=True).drop(columns=["Date triée"])
        return df
    elif colonne == "Frais de candidature":
        return df.sort_values(by="Frais en EUR", ascending=False)
    elif colonne == "Taux d'acceptance":
        return df.sort_values(by=colonne, key=lambda x: x.str.replace("%", "").astype(float), ascending=False)
    elif colonne == "Taux d'emploi à 3 mois":
        return df.sort_values(by=colonne, key=lambda x: x.str.replace("%", "").astype(float), ascending=False)
    elif colonne == "Salaire de base estimé":
        return df.sort_values(by=colonne, key=lambda x: x.astype(str).str.replace("[^0-9]", "", regex=True).astype(float), ascending=False)
    elif colonne == "Classement QuantNet.com":
        return df.sort_values(by=colonne, key=lambda x: x.astype(str).str.extract(r"(\d+)").astype(float).fillna(9999))
    elif colonne == "Classement Risk.net":
        return df.sort_values(by=colonne, key=lambda x: x.astype(str).str.extract(r"(\d+)").astype(float).fillna(9999))
    return df

# === Interface Streamlit ===
st.title("Calculateur de frais de candidature des masters")

# Choix de colonne pour trier
colonne_tri = st.selectbox(
    "Trier le tableau par :",
    ["Classement ChatGPT", "Catégorie visant les carrières quant", "Date limite de candidature",
     "Frais de candidature", "Taux d'acceptance", "Taux d'emploi à 3 mois",
     "Salaire de base estimé", "Classement QuantNet.com", "Classement Risk.net"]
)

# Trier le DataFrame
df = sort_dataframe(df, colonne_tri)

# Colonnes affichées
colonnes_affichage = [c for c in df.columns if c not in ["Frais en EUR"]]

# Tableau éditable
edited_df = st.data_editor(
    df[colonnes_affichage],
    column_config={"Sélectionner": st.column_config.CheckboxColumn("Sélectionner")},
    disabled=[c for c in colonnes_affichage if c != "Sélectionner"],
    use_container_width=True
)

# Mettre à jour sélection
df["Sélectionner"] = edited_df["Sélectionner"]
selected_df = df[df["Sélectionner"]]

# Calcul des frais
if not selected_df.empty:
    frais_base = selected_df["Frais en EUR"].sum()

    frais_supp = 0
    if len(selected_df) > 4:
        frais_supp = (len(selected_df) - 4) * 60 * usd_to_eur

    total = frais_base + frais_supp
    total_tnd = total * eur_to_tnd

    st.write(f"### Programmes sélectionnés : {len(selected_df)}")
    st.write(f"Frais de base : {frais_base:,.2f} €")
    st.write(f"Frais supplémentaires (GRE/TOEFL) : {frais_supp:,.2f} €")
    st.write(f"### Total : {total:,.2f} € ({total_tnd:,.2f} TND)")
else:
    st.write("Aucun programme sélectionné.")
