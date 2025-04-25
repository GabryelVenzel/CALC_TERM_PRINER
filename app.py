import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
from scipy.optimize import fsolve

# --- CONFIGURAÇÕES GERAIS ---
st.set_page_config(page_title="Calculadora IsolaFácil", layout="wide")

# --- ESTILO VISUAL ---
st.markdown("""
<style>
    .main {
        background-color: #FFFFFF;
    }
    .block-container {
        padding-top: 2rem;
    }
    h1, h2, h3, h4 {
        color: #003366;
    }
    .stButton>button {
        background-color: #198754;
        color: white;
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    input[type="radio"], input[type="checkbox"] {
        accent-color: #003366;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGO ---
logo = Image.open("logo.png")
st.image(logo, width=300)

# --- CONECTAR COM GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gcp_json = json.loads(st.secrets["GCP_JSON"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_json, scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1W1JHXAnGJeWbGVK0AmORux5I7CYTEwoBIvBfVKO40aY/edit#gid=0")
worksheet = sheet.worksheet("Isolantes")

# --- FUNÇÕES AUXILIARES ---
def carregar_isolantes():
    df = pd.DataFrame(worksheet.get_all_records())
    return df.to_dict(orient="records")

def cadastrar_isolante(nome, k_func):
    worksheet.append_row([nome, k_func])

def excluir_isolante(nome):
    cell = worksheet.find(nome)
    if cell:
        worksheet.delete_rows(cell.row)

def calcular_k(k_func_str, T_media):
    try:
        if isinstance(k_func_str, (int, float)):
            return k_func_str
        return eval(str(k_func_str), {"math": math, "T": T_media})
    except Exception as ex:
        st.error(f"Erro ao calcular k(T): {ex}")
        return None

def calcular_h_conv(Tf, To, L):
    g = 9.81
    Tf_K = Tf + 273.15
    To_K = To + 273.15
    T_film = (Tf_K + To_K) / 2
    beta = 1 / T_film
    nu = 1.5e-5
    alpha = 2.2e-5
    k_ar = 0.026
    delta_T = Tf - To
    Ra = (g * beta * abs(delta_T) * L**3) / (nu * alpha)
    if Ra < 1e7:
        Nu = 0.27 * Ra**0.25
    else:
        Nu = 0.15 * Ra**(1/3)
    return Nu * k_ar / L

# --- NOVO CÁLCULO COM RESOLUÇÃO DIRETA ---
def calcular_temperaturas_direto(num_camadas, espessuras, Tq, To, k_func_str):
    def sistema(vars):
        if num_camadas == 1:
            Tf = vars[0]
            Tm = (Tq + Tf) / 2
            k = calcular_k(k_func_str, Tm)
            q = k * (Tq - Tf) / espessuras[0]
        elif num_camadas == 2:
            T1, Tf = vars
            k1 = calcular_k(k_func_str, (Tq + T1) / 2)
            k2 = calcular_k(k_func_str, (T1 + Tf) / 2)
            q1 = k1 * (Tq - T1) / espessuras[0]
            q2 = k2 * (T1 - Tf) / espessuras[1]
            q = (q1 + q2) / 2
        else:  # 3 camadas
            T1, T2, Tf = vars
            k1 = calcular_k(k_func_str, (Tq + T1) / 2)
            k2 = calcular_k(k_func_str, (T1 + T2) / 2)
            k3 = calcular_k(k_func_str, (T2 + Tf) / 2)
            q1 = k1 * (Tq - T1) / espessuras[0]
            q2 = k2 * (T1 - T2) / espessuras[1]
            q3 = k3 * (T2 - Tf) / espessuras[2]
            q = (q1 + q2 + q3) / 3

        Tf_K = Tf + 273.15
        To_K = To + 273.15
        h_conv = calcular_h_conv(Tf, To, sum(espessuras))
        q_rad = e * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf - To)
        q_perda = q_conv + q_rad

        if num_camadas == 1:
            return [q - q_perda]
        elif num_camadas == 2:
            return [q1 - q2, q - q_perda]
        else:
            return [q1 - q2, q2 - q3, q - q_perda]

    if num_camadas == 1:
        sol = fsolve(sistema, [To])
        return [Tq, sol[0]]
    elif num_camadas == 2:
        sol = fsolve(sistema, [To + 10, To])
        return [Tq, sol[0], sol[1]]
    else:
        sol = fsolve(sistema, [Tq - 10, To + 10, To])
        return [Tq, sol[0], sol[1], sol[2]]

# --- CONSTANTES ---
e = 0.9
sigma = 5.67e-8

# --- INTERFACE PRINCIPAL ---
st.title("Cálculo Térmico - IsolaFácil")

isolantes = carregar_isolantes()
materiais = [i['nome'] for i in isolantes]
material_selecionado = st.selectbox("Escolha o material do isolante", materiais)
isolante = next(i for i in isolantes if i['nome'] == material_selecionado)
k_func_str = isolante['k_func']

num_camadas = st.selectbox("Número de camadas de isolante", [1, 2, 3], index=0)
espessuras_mm = [st.number_input(f"Espessura da camada {i+1} [mm]", value=51.0) for i in range(num_camadas)]
espessuras = [esp / 1000 for esp in espessuras_mm]
Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
To = st.number_input("Temperatura ambiente [°C]", value=30.0)

if st.button("Calcular Temperatura da Face Fria"):
    temperaturas = calcular_temperaturas_direto(num_camadas, espessuras, Tq, To, k_func_str)
    Tf = temperaturas[-1]
    st.subheader("Resultados")
    st.success(f"\U00002705 Temperatura da face fria: {Tf:.1f} °C".replace('.', ','))

    Tf_K = Tf + 273.15
    To_K = To + 273.15
    Tq_K = Tq + 273.15
    h_conv = calcular_h_conv(Tf, To, sum(espessuras))
    q_rad = e * sigma * (Tf_K**4 - To_K**4)
    q_conv = h_conv * (Tf - To)
    q_transferencia = q_conv + q_rad
    perda_com = q_transferencia / 1000
    st.info(f"Perda total com isolante: {str(perda_com).replace('.', ',')[:6]} kW/m²")

    hr_sem = e * sigma * (Tq_K**4 - To_K**4)
    h_total_sem = calcular_h_conv(Tq, To, sum(espessuras)) + hr_sem / (Tq - To)
    q_sem_isolante = h_total_sem * (Tq - To)
    perda_sem = q_sem_isolante / 1000
    st.warning(f"Perda total sem o uso de isolante: {str(perda_sem).replace('.', ',')[:6]} kW/m²")

# --- OBSERVAÇÃO ---
st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.

> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")

