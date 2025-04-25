import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
from scipy.optimize import root
import numpy as np

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
    """Função para carregar isolantes do Google Sheets"""
    dados = worksheet.get_all_records()
    return pd.DataFrame(dados).to_dict(orient="records")

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

# Título principal
st.markdown("<h1 style='text-align: center;'>Cálculo Térmico - IsolaFácil</h1>", unsafe_allow_html=True)

# Área restrita (posicionada logo após o título)
with st.expander("🔒 Área restrita: Cadastro e Gerenciamento de Isolantes", expanded=False):
    senha = st.text_input("Digite a senha para acessar:", type="password")
    if senha == "Priner123":
        st.success("Acesso concedido.")

        aba = st.radio("Selecione a operação desejada:", ["Cadastrar Isolante", "Excluir Isolante"])

        df = carregar_isolantes()

        if aba == "Cadastrar Isolante":
            nome = st.text_input("Nome do isolante")
            tipo_equacao = st.selectbox("Tipo de equação para k(T):", ["Constante", "Linear", "Polinômio de segundo grau", "Exponencial"])

            if tipo_equacao == "Linear":
                a = st.number_input("a", format="%.6f")
                b = st.number_input("b", format="%.6f")
                c = 0
                tipo = "linear"
            elif tipo_equacao == "Polinômio de segundo grau":
                a = st.number_input("a", format="%.6f")
                b = st.number_input("b", format="%.6f")
                c = st.number_input("c", format="%.6f")
                tipo = "polinomial"
            elif tipo_equacao == "Exponencial":
                a = st.number_input("a", format="%.6f")
                b = st.number_input("b", format="%.6f")
                c = 0
                tipo = "exponencial"
            else:  # Constante
                a = st.number_input("Valor da constante k(T)", format="%.6f")
                b = 0
                c = 0
                tipo = "constante"

            if st.button("Cadastrar isolante"):
                novo = pd.DataFrame([[nome, tipo, a, b, c]], columns=df.columns)
                df = pd.concat([df, novo], ignore_index=True)
                st.success("Isolante cadastrado com sucesso!")

        elif aba == "Excluir Isolante":
            isolante_selecionado = st.selectbox("Selecione o isolante a ser excluído", df["nome"].tolist())
            if st.button("Excluir isolante"):
                df = df[df["nome"] != isolante_selecionado]
                st.success("Isolante excluído com sucesso!")

# --- TABS PRINCIPAIS ---
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
        if num_camadas == 1:
            L_total = espessuras[0]
            Tf = To + 10.0
            max_iter = 1000
            step = 100.0
            min_step = 0.01
            tolerancia = 1.0
            erro_anterior = None
            convergiu = False

            for _ in range(max_iter):
                T_media = (Tq + Tf) / 2
                k_total = calcular_k(k_func_str, T_media)
                if k_total is None:
                    break

                q_cond = k_total * (Tq - Tf) / L_total
                Tf_K = Tf + 273.15
                To_K = To + 273.15
                h_conv = calcular_h_conv(Tf, To, L_total)
                q_rad = e * sigma * (Tf_K**4 - To_K**4)
                q_conv = h_conv * (Tf - To)
                q_total = q_rad + q_conv

                erro = q_cond - q_total

                if abs(erro) < tolerancia:
                    convergiu = True
                    break

                if erro_anterior and erro * erro_anterior < 0:
                    step = max(min_step, step * 0.5)

                Tf += step if erro > 0 else -step
                erro_anterior = erro
                time.sleep(0.01)

            if convergiu:
                st.success(f"Temperatura da face fria externa: {Tf:.1f} °C".replace('.', ','))
            else:
                st.error("O cálculo não convergiu.")

# --- FINAL ---
st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.
> 
> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")
