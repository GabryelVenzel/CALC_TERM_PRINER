import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
from scipy.optimize import root

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

def calcular_k(k_func_str, T_media):
    try:
        if isinstance(k_func_str, (int, float)):
            return k_func_str
        return eval(str(k_func_str), {"math": math, "T": T_media})
    except Exception as ex:
        st.error(f"Erro ao calcular k(T): {ex}")
        return None

# --- CONSTANTES ---
e = 0.9
sigma = 5.67e-8

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

    h_conv = Nu * k_ar / L
    return h_conv

# --- INTERFACE PRINCIPAL ---
st.title("Cálculo Térmico - IsolaFácil")

tab1, tab2 = st.tabs(["Cálculo de face fria", "Cálculo Financeiro"])

with tab1:
    isolantes = carregar_isolantes()
    materiais = [i['nome'] for i in isolantes]
    material_selecionado = st.selectbox("Escolha o material do isolante", materiais)
    isolante = next(i for i in isolantes if i['nome'] == material_selecionado)
    k_func_str = isolante['k_func']

    num_camadas = st.selectbox("Quantidade de Camadas", [1, 2, 3], index=0)
    espessuras = []
    for i in range(num_camadas):
        esp = st.number_input(f"Espessura da camada {i+1} [mm]", value=25.0, key=f"L{i}")
        espessuras.append(esp / 1000)

    Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
    To = st.number_input("Temperatura ambiente [°C]", value=30.0)

    if st.button("Calcular Temperaturas de Face Fria"):
        def sistema(vars):
            Tf1, Tf2, Tf3 = vars if num_camadas == 3 else (vars + [None] * (3 - len(vars)))
            q1 = (Tq - Tf1) / espessuras[0] * calcular_k(k_func_str, (Tq + Tf1)/2)
            q2 = (Tf1 - Tf2) / espessuras[1] * calcular_k(k_func_str, (Tf1 + Tf2)/2) if num_camadas >= 2 else q1
            q3 = (Tf2 - Tf3) / espessuras[2] * calcular_k(k_func_str, (Tf2 + Tf3)/2) if num_camadas == 3 else q2
            L_ext = espessuras[-1]
            h = calcular_h_conv(Tf3 if Tf3 else Tf2 if Tf2 else Tf1, To, L_ext)
            Tf_ext = Tf3 if Tf3 else Tf2 if Tf2 else Tf1
            q_out = h * (Tf_ext - To) + e * sigma * ((Tf_ext+273.15)**4 - (To+273.15)**4)
            return [
                q1 - q2 if num_camadas >= 2 else 0,
                q2 - q3 if num_camadas == 3 else 0,
                q3 - q_out if num_camadas == 3 else q2 - q_out if num_camadas == 2 else q1 - q_out
            ][:num_camadas]

        x0 = [Tq - 20 * (i+1) for i in range(num_camadas)]
        sol = root(sistema, x0)

        if sol.success:
            for i, Tfi in enumerate(sol.x):
                st.write(f"Temperatura da face fria após camada {i+1}: {Tfi:.1f} °C".replace('.', ','))
        else:
            st.error("O cálculo não convergiu. Verifique os dados de entrada.")

with tab2:
    st.markdown("### Em breve: Cálculo com retorno financeiro")
    st.info("Esta aba será utilizada para calcular a economia financeira com o uso de isolamento térmico.")

st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.
> 
> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")

