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

# --- CONSTANTES ---
e = 0.9
sigma = 5.67e-8

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

# --- SESSION STATE ---
if 'convergiu' not in st.session_state:
    st.session_state.convergiu = None
if 'q_transferencia' not in st.session_state:
    st.session_state.q_transferencia = None
if 'Tf' not in st.session_state:
    st.session_state.Tf = None

# --- ABA PRINCIPAL ---
aba = st.sidebar.radio("Escolha a aba:", ["Cálculo Térmico", "Cálculo Financeiro"])

# --- ABA CÁLCULO TÉRMICO ---
if aba == "Cálculo Térmico":
    st.title("Cálculo Térmico com Isolante")
    
    Ti = st.number_input("Temperatura interna (°C)", value=100.0)
    To = st.number_input("Temperatura externa (°C)", value=25.0)
    L = st.number_input("Espessura da camada (m)", value=0.05, step=0.01)
    A = st.number_input("Área (m²)", value=1.0)
    
    lista_isolantes = carregar_isolantes()
    nomes_isolantes = [iso["Nome"] for iso in lista_isolantes]
    escolha_isolante = st.selectbox("Selecione o isolante", nomes_isolantes)
    
    k_func_str = next((iso["k(T)"] for iso in lista_isolantes if iso["Nome"] == escolha_isolante), None)
    
    if st.button("Calcular"):
        with st.spinner("Calculando..."):
            Tf = (Ti + To) / 2
            k = calcular_k(k_func_str, Tf)
            if k:
                h_conv_i = calcular_h_conv(Ti, Tf, L, isolante=True)
                h_conv_o = calcular_h_conv(Tf, To, L, isolante=False)
                h_rad = e * sigma * ((Tf+273.15)**2 + (To+273.15)**2) * ((Tf+273.15) + (To+273.15))
                
                R_total = 1/h_conv_i + L/k + 1/(h_conv_o + h_rad)
                q = (Ti - To) / R_total
                st.session_state.q_transferencia = q
                st.session_state.Tf = Tf
                st.success(f"Transferência de calor: {q:.2f} W/m²")
            else:
                st.error("Não foi possível calcular a condutividade térmica.")
                
# --- ABA CÁLCULO FINANCEIRO ---
elif aba == "Cálculo Financeiro":
    st.title("Cálculo Financeiro da Economia com Isolante")
    
    Ti = st.number_input("Temperatura interna (°C)", value=100.0, key="fin_Ti")
    To = st.number_input("Temperatura externa (°C)", value=25.0, key="fin_To")
    L_mm = st.number_input("Espessura do isolante (mm)", value=51.0, step=1.0)
    L = L_mm / 1000  # converter para metros
    
    combustiveis = {
        "Gás Natural": {"preco_R$/kWh": 0.25, "eficiencia": 0.9},
        "GLP": {"preco_R$/kWh": 0.30, "eficiencia": 0.85},
        "Óleo Diesel": {"preco_R$/kWh": 0.28, "eficiencia": 0.88},
        "Eletricidade": {"preco_R$/kWh": 0.50, "eficiencia": 1.0},
    }
    
    combustivel = st.selectbox("Selecione o combustível", list(combustiveis.keys()))
    preco_kWh = combustiveis[combustivel]["preco_R$/kWh"]
    eficiencia = combustiveis[combustivel]["eficiencia"]
    
    lista_isolantes = carregar_isolantes()
    nomes_isolantes = [iso["Nome"] for iso in lista_isolantes]
    escolha_isolante = st.selectbox("Isolante utilizado", nomes_isolantes, key="fin_isolante")
    k_func_str = next((iso["k(T)"] for iso in lista_isolantes if iso["Nome"] == escolha_isolante), None)
    
    if st.button("Calcular economia"):
        with st.spinner("Calculando..."):
            Tf = (Ti + To) / 2
            k = calcular_k(k_func_str, Tf)
            if k:
                h_conv_i = calcular_h_conv(Ti, Tf, L, isolante=True)
                h_conv_o = calcular_h_conv(Tf, To, L, isolante=False)
                h_rad = e * sigma * ((Tf+273.15)**2 + (To+273.15)**2) * ((Tf+273.15) + (To+273.15))
                R_total = 1/h_conv_i + L/k + 1/(h_conv_o + h_rad)
                q_com = (Ti - To) / R_total
                
                # sem isolante
                h_conv_i_sem = calcular_h_conv(Ti, To, 0.01, isolante=False)
                h_conv_o_sem = calcular_h_conv(To, To, 0.01, isolante=False)
                h_rad_sem = e * sigma * ((To+273.15)**2 + (To+273.15)**2) * ((To+273.15) + (To+273.15))
                R_sem = 1/h_conv_i_sem + 1/(h_conv_o_sem + h_rad_sem)
                q_sem = (Ti - To) / R_sem
                
                economia_W_m2 = q_sem - q_com
                economia_kWh = economia_W_m2 / 1000
                economia_reais_h = economia_kWh / eficiencia * preco_kWh
                economia_percentual = economia_W_m2 / q_sem * 100

                st.markdown(f"### Resultados")
                st.markdown(f"**Temperatura da face fria estimada:** {Tf:.1f} °C")
                st.markdown(f"**Perda de calor sem isolante:** {q_sem:.2f} W/m²")
                st.markdown(f"**Perda de calor com isolante:** {q_com:.2f} W/m²")
                st.markdown(f"**Economia de combustível:** R$ {economia_reais_h:.4f} por hora/m²")
                st.markdown(f"**Economia percentual:** {economia_percentual:.1f}%")
            else:
                st.error("Erro ao calcular a condutividade térmica.")
