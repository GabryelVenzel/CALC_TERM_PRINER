import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st

# Conexão com o Google Sheets
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    gcp_json = json.loads(st.secrets["GCP_JSON"])
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_json, scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1W1JHXAnGJeWbGVK0AmORux5I7CYTEwoBIvBfVKO40aY/edit#gid=0")
    worksheet = sheet.worksheet("Isolantes")
    return worksheet

def carregar_isolantes():
    worksheet = conectar_google_sheets()
    df = pd.DataFrame(worksheet.get_all_records())
    return df.to_dict(orient="records")

def cadastrar_isolante(nome, k_func):
    worksheet = conectar_google_sheets()
    worksheet.append_row([nome, k_func])

def excluir_isolante(nome):
    worksheet = conectar_google_sheets()
    cell = worksheet.find(nome)
    if cell:
        worksheet.delete_rows(cell.row)
