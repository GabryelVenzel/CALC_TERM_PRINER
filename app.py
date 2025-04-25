import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
from scipy.optimize import fsolve

# --- EXIBIR INTERFACE DE CADASTRO DE ISOLANTES ---
# Isso deve ser feito antes do cálculo, mantendo a aba de cadastro visível.
st.header("Cadastro de Isolantes")
nome_isolante = st.text_input("Nome do Isolante")
k_func_str = st.text_area("Equação k(T)", "Informe a equação k(T)")

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

# --- SELEÇÃO DO NÚMERO DE CAMADAS ---
num_camadas = st.selectbox("Selecione o número de camadas", [1, 2, 3])

# --- FUNÇÃO DE CÁLCULO PARA UMA CAMADA ---
def calcular_temperatura_1_camada(Tq, To, L, k_func_str):
    Tf = To + 10.0
    max_iter = 1000
    step = 100.0
    min_step = 0.01
    tolerancia = 1.0
    progress = st.progress(0)
    q_transferencia = None
    convergiu = False
    erro_anterior = None

    for i in range(max_iter):
        progress.progress(i / max_iter)
        T_media = (Tq + Tf) / 2
        k = calcular_k(k_func_str, T_media)
        if k is None:
            break

        q_conducao = k * (Tq - Tf) / L

        Tf_K = Tf + 273.15
        To_K = To + 273.15
        Tq_K = Tq + 273.15

        h_conv = calcular_h_conv(Tf, To, L)
        q_rad = e * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf - To)
        q_transferencia = q_conv + q_rad

        erro = q_conducao - q_transferencia

        if abs(erro) < tolerancia:
            convergiu = True
            break

        if erro_anterior is not None and erro * erro_anterior < 0:
            step = max(min_step, step * 0.5)

        Tf += step if erro > 0 else -step
        erro_anterior = erro

    if convergiu:
        return Tf, q_transferencia
    else:
        return None, None

# --- FUNÇÃO DE CÁLCULO PARA DUAS CAMADAS ---
def calcular_temperatura_2_camadas(Tq, To, L1, L2, k1_func_str, k2_func_str):
    Tf1 = To + 10.0
    Tf2 = To + 10.0
    max_iter = 1000
    step = 100.0
    min_step = 0.01
    tolerancia = 1.0
    progress = st.progress(0)
    q_transferencia = None
    convergiu = False
    erro_anterior = None

    for i in range(max_iter):
        progress.progress(i / max_iter)
        
        # Calcular k para ambas as camadas
        k1 = calcular_k(k1_func_str, (Tq + Tf1) / 2)
        k2 = calcular_k(k2_func_str, (Tf1 + Tf2) / 2)

        if k1 is None or k2 is None:
            break

        # Calcular o fluxo de calor de cada camada
        q_conducao_1 = k1 * (Tq - Tf1) / L1
        q_conducao_2 = k2 * (Tf1 - Tf2) / L2

        # Cálculo do fluxo de calor convectivo e radiativo
        Tf_K = Tf1 + 273.15
        To_K = To + 273.15
        Tq_K = Tq + 273.15

        h_conv = calcular_h_conv(Tf1, To, L1)
        q_rad = e * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf1 - To)

        q_transferencia = q_conv + q_rad

        erro = q_conducao_1 - q_conducao_2

        if abs(erro) < tolerancia:
            convergiu = True
            break

        if erro_anterior is not None and erro * erro_anterior < 0:
            step = max(min_step, step * 0.5)

        Tf1 += step if erro > 0 else -step
        erro_anterior = erro

    if convergiu:
        return Tf1, Tf2, q_transferencia
    else:
        return None, None, None

# --- FUNÇÃO DE CÁLCULO PARA TRÊS CAMADAS ---
def calcular_temperatura_3_camadas(Tq, To, L1, L2, L3, k1_func_str, k2_func_str, k3_func_str):
    Tf1 = To + 10.0
    Tf2 = To + 10.0
    Tf3 = To + 10.0
    max_iter = 1000
    step = 100.0
    min_step = 0.01
    tolerancia = 1.0
    progress = st.progress(0)
    q_transferencia = None
    convergiu = False
    erro_anterior = None

    for i in range(max_iter):
        progress.progress(i / max_iter)
        
        # Calcular k para todas as camadas
        k1 = calcular_k(k1_func_str, (Tq + Tf1) / 2)
        k2 = calcular_k(k2_func_str, (Tf1 + Tf2) / 2)
        k3 = calcular_k(k3_func_str, (Tf2 + Tf3) / 2)

        if k1 is None or k2 is None or k3 is None:
            break

        # Calcular os fluxos de calor para cada camada
        q_conducao_1 = k1 * (Tq - Tf1) / L1
        q_conducao_2 = k2 * (Tf1 - Tf2) / L2
        q_conducao_3 = k3 * (Tf2 - Tf3) / L3

        # Cálculo do fluxo de calor convectivo e radiativo
        Tf_K = Tf2 + 273.15
        To_K = To + 273.15
        Tq_K = Tq + 273.15

        h_conv = calcular_h_conv(Tf2, To, L2)
        q_rad = e * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf2 - To)

        q_transferencia = q_conv + q_rad

        erro = q_conducao_2 - q_transferencia

        if abs(erro) < tolerancia:
            convergiu = True
            break

        if erro_anterior is not None and erro * erro_anterior < 0:
            step = max(min_step, step * 0.5)

        Tf2 += step if erro > 0 else -step
        erro_anterior = erro

    if convergiu:
        return Tf1, Tf2, Tf3, q_transferencia
    else:
        return None, None, None, None

# --- CÁLCULO FINAL BASEADO NO NÚMERO DE CAMADAS ---
if num_camadas == 1:
    Tf, q_transferencia = calcular_temperatura_1_camada(Tq, To, L, k_func_str)
    if Tf is not None:
        st.success(f"Temperatura da face fria: {Tf:.1f} °C")
elif num_camadas == 2:
    Tf1, Tf2, q_transferencia = calcular_temperatura_2_camadas(Tq, To, L1, L2, k1_func_str, k2_func_str)
    if Tf1 is not None and Tf2 is not None:
        st.success(f"Temperaturas das faces frias: Tf1 = {Tf1:.1f} °C, Tf2 = {Tf2:.1f} °C")
elif num_camadas == 3:
    Tf1, Tf2, Tf3, q_transferencia = calcular_temperatura_3_camadas(Tq, To, L1, L2, L3, k1_func_str, k2_func_str, k3_func_str)
    if Tf1 is not None and Tf2 is not None and Tf3 is not None:
        st.success(f"Temperaturas das faces frias: Tf1 = {Tf1:.1f} °C, Tf2 = {Tf2:.1f} °C, Tf3 = {Tf3:.1f} °C")

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

