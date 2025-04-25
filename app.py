import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

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
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1W1JHXAnGJeWbGVK0AmORux5I7CYTEwoBIvBfVKO40aY")
worksheet = sheet.worksheet("Isolantes")

# --- FUNÇÕES AUXILIARES ---
def carregar_isolantes():
    df = pd.DataFrame(worksheet.get_all_records())
    return df.to_dict(orient="records")

def calcular_k(k_func_str, T_media):
    try:
        if isinstance(k_func_str, (int, float)):
            return k_func_str
        return eval(str(k_func_str), {"math": math, "T": T_media})
    except Exception as ex:
        st.error(f"Erro ao calcular k(T): {ex}")
        return None

def calcular_h_conv(Tf, To, L, isolante=False):
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
    h_conv = Nu * k_ar / L
    return h_conv

# --- CONSTANTES ---
e = 0.9
sigma = 5.67e-8

# --- SESSION STATE ---
if 'convergiu' not in st.session_state:
    st.session_state.convergiu = None
if 'q_transferencia' not in st.session_state:
    st.session_state.q_transferencia = None
if 'Tf' not in st.session_state:
    st.session_state.Tf = None
if 'temperaturas_intermediarias' not in st.session_state:
    st.session_state.temperaturas_intermediarias = []

# --- INTERFACE PRINCIPAL ---
st.title("Cálculo Térmico - IsolaFácil")

isolantes = carregar_isolantes()
materiais = [i['nome'] for i in isolantes]
material_selecionado = st.selectbox("Escolha o material do isolante", materiais)
isolante = next(i for i in isolantes if i['nome'] == material_selecionado)
k_func_str = isolante['k_func']

col1, col2 = st.columns(2)
with col1:
    Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
with col2:
    To = st.number_input("Temperatura ambiente [°C]", value=30.0)

numero_camadas = st.number_input("Número de camadas", min_value=1, max_value=3, value=1, step=1)
espessuras = []

if numero_camadas == 1:
    L1 = st.number_input("Espessura da camada 1 [mm]", value=51.0, key="L1")
    espessuras.append(L1)
elif numero_camadas == 2:
    col1, col2 = st.columns(2)
    with col1:
        L1 = st.number_input("Espessura da camada 1 [mm]", value=30.0, key="L1")
    with col2:
        L2 = st.number_input("Espessura da camada 2 [mm]", value=30.0, key="L2")
    espessuras.extend([L1, L2])
elif numero_camadas == 3:
    col1, col2, col3 = st.columns(3)
    with col1:
        L1 = st.number_input("Espessura da camada 1 [mm]", value=20.0, key="L1")
    with col2:
        L2 = st.number_input("Espessura da camada 2 [mm]", value=20.0, key="L2")
    with col3:
        L3 = st.number_input("Espessura da camada 3 [mm]", value=20.0, key="L3")
    espessuras.extend([L1, L2, L3])

L_total = sum(espessuras) / 1000

# --- BOTÃO CALCULAR ---
if st.button("Calcular Temperatura da Face Fria"):
    Tf = To + 10.0
    max_iter = 1000
    step = 100.0
    min_step = 0.01
    tolerancia = 1.0
    progress = st.progress(0)
    convergiu = False
    q_transferencia = None
    erro_anterior = None

    for i in range(max_iter):
        progress.progress(i / max_iter)
        T_media = (Tq + Tf) / 2
        k = calcular_k(k_func_str, T_media)
        if k is None:
            break

        q_conducao = k * (Tq - Tf) / L_total

        Tf_K = Tf + 273.15
        To_K = To + 273.15
        Tq_K = Tq + 273.15

        h_conv = calcular_h_conv(Tf, To, L_total)
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
        time.sleep(0.01)

    st.session_state.convergiu = convergiu
    st.session_state.q_transferencia = q_transferencia
    st.session_state.Tf = Tf

    # --- CÁLCULO DAS TEMPERATURAS INTERMEDIÁRIAS ---
    temperaturas_intermediarias = []
    temperatura_atual = Tq

    for espessura in espessuras:
        L_m = espessura / 1000  # mm para metros
        k = calcular_k(k_func_str, (temperatura_atual + Tf) / 2)
        q_conducao = k * (temperatura_atual - Tf) / L_total
        delta_T = q_conducao * L_m / k
        temperatura_atual -= delta_T
        temperaturas_intermediarias.append(temperatura_atual)

    st.session_state.temperaturas_intermediarias = temperaturas_intermediarias

# --- RESULTADOS ---
st.subheader("Resultados")

if st.session_state.convergiu is not None:
    if st.session_state.convergiu:
        st.success(f"\U00002705 Temperatura final da face fria: {st.session_state.Tf:.1f} °C".replace('.', ','))

        for idx, temp in enumerate(st.session_state.temperaturas_intermediarias, start=1):
            st.info(f"Temperatura após camada {idx}: {temp:.1f} °C".replace('.', ','))

    else:
        st.error("\U0000274C O cálculo não convergiu dentro do limite de iterações.")

    if st.session_state.q_transferencia is not None:
        perda_com = st.session_state.q_transferencia / 1000
        st.info(f"Perda total com isolante: {str(perda_com).replace('.', ',')[:6]} kW/m²")

        hr_sem = e * sigma * ((Tq + 273.15)**4 - (To + 273.15)**4)
        h_total_sem = calcular_h_conv(Tq, To, L_total) + hr_sem / (Tq - To)
        q_sem_isolante = h_total_sem * (Tq - To)

        perda_sem = q_sem_isolante / 1000
        st.warning(f"Perda total sem o uso de isolante: {str(perda_sem).replace('.', ',')[:6]} kW/m²")

# --- OBSERVAÇÃO ---
st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.

> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")


