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
    h_conv = Nu * k_ar / L
    return h_conv

# --- CONSTANTES DE RADIAÇÃO --- 
e = 0.9
sigma = 5.67e-8

# --- INTERFACE PRINCIPAL ---
st.title("Cálculo Térmico - IsolaFácil")

# --- SELEÇÃO DO MATERIAL --- 
isolantes = carregar_isolantes()
materiais = [i['nome'] for i in isolantes]

# --- ENTRADAS GERAIS ---
n_camadas = st.selectbox("Número de camadas de isolante", [1, 2, 3])

materiais_selecionados = []
espessuras = []
for i in range(n_camadas):
    materiais_selecionados.append(st.selectbox(f"Material da camada {i+1}", materiais, key=f"mat_{i}"))
    espessuras.append(st.number_input(f"Espessura da camada {i+1} [mm]", value=25.0, key=f"L_{i}"))

Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
To = st.number_input("Temperatura ambiente [°C]", value=30.0)

# --- BOTÃO DE CALCULAR ---
if st.button("Calcular Temperatura da(s) Face(s) Fria(s)"):
    isolante_info = [next(i for i in isolantes if i['nome'] == nome) for nome in materiais_selecionados]
    k_funcs = [i['k_func'] for i in isolante_info]
    L_list = [L_mm / 1000 for L_mm in espessuras]

    Tf_values = [To + 10.0 for _ in range(n_camadas)]
    max_iter = 1000
    step = 100.0
    min_step = 0.01
    tolerancia = 1.0
    progress = st.progress(0)

    convergiu = False
    erro_anterior = None

    for iteracao in range(max_iter):
        progress.progress(iteracao / max_iter)

        # Inicializar temperaturas das interfaces
        T = [Tq] + Tf_values
        k_medias = [calcular_k(k_funcs[i], (T[i] + T[i+1])/2) for i in range(n_camadas)]
        if any(k is None for k in k_medias):
            break

        q_conducao = k_medias[0] * (T[0] - T[1]) / L_list[0]
        valido = True
        for i in range(1, n_camadas):
            q_i = k_medias[i] * (T[i] - T[i+1]) / L_list[i]
            if abs(q_i - q_conducao) > tolerancia:
                valido = False
                erro = q_i - q_conducao
                if erro_anterior is not None and erro * erro_anterior < 0:
                    step = max(min_step, step * 0.5)
                Tf_values[i] += step if erro > 0 else -step
                erro_anterior = erro
                break

        if valido:
            Tf_K = Tf_values[-1] + 273.15
            To_K = To + 273.15
            Tq_K = Tq + 273.15
            h_conv = calcular_h_conv(Tf_values[-1], To, sum(L_list))
            q_rad = e * sigma * (Tf_K**4 - To_K**4)
            q_conv = h_conv * (Tf_values[-1] - To)
            q_transferencia = q_conv + q_rad
            erro = q_conducao - q_transferencia
            if abs(erro) < tolerancia:
                convergiu = True
                break
            if erro_anterior is not None and erro * erro_anterior < 0:
                step = max(min_step, step * 0.5)
            Tf_values[-1] += step if erro > 0 else -step
            erro_anterior = erro

        time.sleep(0.01)

    # --- RESULTADOS ---
    st.subheader("Resultados")
    if convergiu:
        for i, Tf in enumerate(Tf_values):
            st.success(f"\U00002705 Temperatura da face fria da camada {i+1}: {Tf:.1f} °C".replace('.', ','))
    else:
        st.error("\U0000274C O cálculo não convergiu dentro do limite de iterações.")

    if convergiu:
        perda_com = q_transferencia / 1000
        st.info(f"Perda total com isolante: {str(perda_com).replace('.', ',')[:6]} kW/m²")

        hr_sem = e * sigma * (Tq_K**4 - To_K**4)
        h_total_sem = calcular_h_conv(Tq, To, sum(L_list)) + hr_sem / (Tq - To)
        q_sem_isolante = h_total_sem * (Tq - To)

        perda_sem = q_sem_isolante / 1000
        st.warning(f"Perda total sem o uso de isolante: {str(perda_sem).replace('.', ',')[:6]} kW/m²")

# --- OBSERVAÇÃO ---
st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.

> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")


