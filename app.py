import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

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
import json

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

# --- CONSTANTES DE RADIAÇÃO --- 
e = 0.9
sigma = 5.67e-8

# --- h_conv para placa horizontal com face quente para BAIXO ---
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

# --- ACESSO --- 
with st.sidebar.expander("Opções", expanded=False):
    senha = st.text_input("Digite a senha", type="password")

    if senha == "Priner123":
        aba = st.radio("Escolha a opção", ["Cadastrar Isolante", "Gerenciar Isolantes"])

        if aba == "Cadastrar Isolante":
            st.subheader("Cadastrar Novo Isolante")
            nome = st.text_input("Nome do Isolante")

            modelo_k = st.radio("Modelo de função k(T)", ["Constante", "Linear", "Polinomial", "Exponencial"])
            k_func = ""
            equacao_latex = ""

            if modelo_k == "Constante":
                k0 = st.number_input("k₀", value=0.035, format="%.6f")
                k_func = f"{k0}"
                equacao_latex = f"k(T) = {str(k0).replace('.', ',')}"

            elif modelo_k == "Linear":
                k0 = st.number_input("k₀", value=0.030, format="%.6f")
                k1 = st.number_input("k₁ (coef. de T)", value=0.0001, format="%.6f")
                k_func = f"{k0} + {k1} * T"
                equacao_latex = f"k(T) = {str(k0).replace('.', ',')} + {str(k1).replace('.', ',')} \\cdot T"

            elif modelo_k == "Polinomial":
                k0 = st.number_input("k₀", value=0.025, format="%.6f")
                k1 = st.number_input("k₁ (T¹)", value=0.0001, format="%.6f")
                k2 = st.number_input("k₂ (T²)", value=0.0, format="%.6f")
                k3 = st.number_input("k₃ (T³)", value=0.0, format="%.6f")
                k4 = st.number_input("k₄ (T⁴)", value=0.0, format="%.6f")
                k_func = f"{k0} + {k1}*T + {k2}*T**2 + {k3}*T**3 + {k4}*T**4"
                equacao_latex = (
                    f"k(T) = {str(k0).replace('.', ',')} + {str(k1).replace('.', ',')} \\cdot T + "
                    f"{str(k2).replace('.', ',')} \\cdot T^2 + {str(k3).replace(".", ",")} \\cdot T^3 + "
                    f"{str(k4).replace('.', ',')} \\cdot T^4"
                )

            elif modelo_k == "Exponencial":
                a = st.number_input("a (coeficiente)", value=0.0387, format="%.6f")
                b = st.number_input("b (expoente)", value=0.0019, format="%.6f")
                k_func = f"{a} * math.exp({b} * T)"
                equacao_latex = f"k(T) = {str(a).replace('.', ',')} \\cdot e^{{{str(b).replace('.', ',')} \\cdot T}}"

            if equacao_latex:
                st.markdown("**Pré-visualização da função:**")
                st.latex(equacao_latex)

            if st.button("Cadastrar"):
                if nome.strip() == "":
                    st.error("Digite um nome para o isolante.")
                else:
                    isolantes_existentes = [i["nome"] for i in carregar_isolantes()]
                    if nome in isolantes_existentes:
                        st.warning("Já existe um isolante com esse nome.")
                    else:
                        cadastrar_isolante(nome, k_func)
                        st.success(f"Isolante {nome} cadastrado com sucesso!")

        elif aba == "Gerenciar Isolantes":
            st.subheader("Isolantes Cadastrados")
            isolantes = carregar_isolantes()
            for i in isolantes:
                st.write(f"**{i['nome']}**")
                if st.button(f"Excluir {i['nome']}"):
                    excluir_isolante(i['nome'])
                    st.success(f"Isolante {i['nome']} excluído com sucesso!")

# --- INTERFACE PRINCIPAL ---
st.title("Cálculo Térmico - IsolaFácil")

# --- SELEÇÃO DO MATERIAL --- 
isolantes = carregar_isolantes()
materiais = [i['nome'] for i in isolantes]
material_selecionado = st.selectbox("Escolha o material do isolante", materiais)
isolante = next(i for i in isolantes if i['nome'] == material_selecionado)
k_func_str = isolante['k_func']

# --- ENTRADAS --- 
L_mm = st.number_input("Espessura do isolante [mm]", value=51.0)
L = L_mm / 1000
Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
To = st.number_input("Temperatura ambiente [°C]", value=30.0)

# --- BOTÃO DE CALCULAR ---
if st.button("Calcular Temperatura da Face Fria"):
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
        print(f"h_conv calculado: {h_conv:.4f} W/m²·K")
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

    # --- RESULTADOS ---
    st.subheader("Resultados")

    if convergiu:
        st.success(f"\U00002705 Temperatura da face fria: {Tf:.1f} °C".replace('.', ','))
    else:
        st.error("\U0000274C O cálculo não convergiu dentro do limite de iterações.")

    if q_transferencia is not None:
        perda_com = q_transferencia / 1000
        st.info(f"Perda total com isolante: {str(perda_com).replace('.', ',')[:6]} kW/m²")

        hr_sem = e * sigma * (Tq_K**4 - To_K**4)
        h_total_sem = calcular_h_conv(Tq, To, L) + hr_sem / (Tq - To)
        q_sem_isolante = h_total_sem * (Tq - To)

        perda_sem = q_sem_isolante / 1000
        st.warning(f"Perda total sem o uso de isolante: {str(perda_sem).replace('.', ',')[:6]} kW/m²")


# --- OBSERVAÇÃO ---
st.markdown("""
---
> **Observação:** Emissividade de **0.9** considerada no cálculo.

> **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
""")



