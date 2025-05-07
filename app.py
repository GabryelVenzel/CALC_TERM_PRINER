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

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'convergiu' not in st.session_state:
    st.session_state.convergiu = None
if 'q_transferencia' not in st.session_state:
    st.session_state.q_transferencia = None
if 'Tf' not in st.session_state:
    st.session_state.Tf = None

# --- LOGO ---
logo = Image.open("logo.png")
st.image(logo, width=300)

# --- INTERFACE PRINCIPAL ---
st.title("Calculadora IsolaFácil")

# --- INTERFACE COM TABS ---
abas = st.tabs(["Cálculo Térmico", "Cálculo Financeiro"])

with abas[0]:
    
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
    
    # --- INICIALIZAÇÃO DO SESSION STATE ---
    if 'convergiu' not in st.session_state:
        st.session_state.convergiu = None
    if 'q_transferencia' not in st.session_state:
        st.session_state.q_transferencia = None
    if 'Tf' not in st.session_state:
        st.session_state.Tf = None
    
    # --- INTERFACE LATERAL ---
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
                        f"{str(k2).replace('.', ',')} \\cdot T^2 + {str(k3).replace('.', ',')} \\cdot T^3 + "
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
    
    # --- BOTÃO DE CALCULAR ---
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
    
    if st.session_state.convergiu is not None:
        
        if st.session_state.convergiu:
            # --- RESULTADOS ---
            st.subheader("Resultados")
            
            st.success(f"\U00002705 Temperatura da face fria: {st.session_state.Tf:.1f} °C".replace('.', ','))
        else:
            st.error("\U0000274C O cálculo não convergiu dentro do limite de iterações.")
    
        # --- TEMPERATURAS INTERMEDIÁRIAS (se houver mais de 1 camada) ---
    if st.session_state.convergiu and numero_camadas > 1:
        delta_T = Tq - st.session_state.Tf
        frac_espessuras = [e / sum(espessuras) for e in espessuras]
    
        # Cálculo das temperaturas intermediárias
        temperaturas_intermed = []
        acumulado = 0
        for i in range(numero_camadas - 1):
            acumulado += frac_espessuras[i]
            Ti = Tq - (delta_T * acumulado)
            temperaturas_intermed.append(Ti)
    
        # Exibição dos resultados
        for idx, temp in enumerate(temperaturas_intermed):
            st.success(f"Temperatura entre camada {idx + 1} e {idx + 2}: {temp:.1f} °C".replace('.', ','))  
    
    # --- OBSERVAÇÃO ---
    st.markdown("""
    ---
    > **Observação:** Emissividade de **0.9** considerada no cálculo.
    
    > **Nota:** Os cálculos são realizados de acordo com a norma ASTM C680.
    """)

with abas[1]:
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
    
    combustiveis = {
        "Óleo Combustível BPF (kg)": {"valor": 3.50, "pc_kwh": 11.34, "eficiencia": 0.80},
        "Gás Natural (m³)": {"valor": 3.60, "pc_kwh": 9.65, "eficiencia": 0.75},
        "Lenha Eucalipto 30% umidade (ton)": {"valor": 200.00, "pc_kwh": 3500.00, "eficiencia": 0.70},
        "Vapor (ton)": {"valor": 100.00, "pc_kwh": 650.00, "eficiencia": 1.00},
        "Eletricidade (kWh)": {"valor": 0.75, "pc_kwh": 1.00, "eficiencia": 1.00}  # Nova opção adicionada
    }

    material_fin = st.selectbox("Escolha o material do isolante", [i['nome'] for i in carregar_isolantes()], key="mat_fin")
    isolante_fin = next(i for i in carregar_isolantes() if i['nome'] == material_fin)
    k_func_fin = isolante_fin["k_func"]
    
    combustivel_sel = st.selectbox("Tipo de combustível", list(combustiveis.keys()))
    comb = combustiveis[combustivel_sel]
    valor_padrao = comb["valor"]
    pc = comb["pc_kwh"]
    ef = comb["eficiencia"]

    col_cb1, col_cb2 = st.columns([2, 2])
    with col_cb1:
        editar_valor = st.checkbox("Editar valor do combustível")
    with col_cb2:
        if editar_valor:
            valor_comb = st.number_input(
                "Custo combustível (R$)",
                min_value=0.0,
                value=valor_padrao,
                step=0.01,
                key="valor_editado"
            )
        else:
            valor_comb = valor_padrao
            st.markdown(f"<span style='color:gray;'>Valor usado: R$ {valor_comb:.2f} (médio)</span>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        Tq_fin = st.number_input("Temperatura da face quente [°C]", value=250.0, key="Tq_fin")
    with col2:
        To_fin = st.number_input("Temperatura ambiente [°C]", value=30.0, key="To_fin")
    
    espessura_fin = st.number_input("Espessura do isolante [mm]", value=51.0, key="esp_fin") / 1000

    if st.button("Calcular Economia Financeira"):
        Tf = To_fin + 10.0
        max_iter = 1000
        step = 100.0
        min_step = 0.01
        tolerancia = 1.0
        erro_anterior = None
        convergiu = False

        for _ in range(max_iter):
            T_med = (Tq_fin + Tf) / 2
            k = calcular_k(k_func_fin, T_med)
            if k is None:
                break

            q_cond = k * (Tq_fin - Tf) / espessura_fin
            Tf_K = Tf + 273.15
            To_K = To_fin + 273.15
            h_conv = calcular_h_conv(Tf, To_fin, espessura_fin)
            q_rad = e * sigma * (Tf_K**4 - To_K**4)
            q_conv = h_conv * (Tf - To_fin)
            q_total = q_conv + q_rad
            erro = q_cond - q_total

            if abs(erro) < tolerancia:
                convergiu = True
                break

            if erro_anterior is not None and erro * erro_anterior < 0:
                step = max(min_step, step * 0.5)
            Tf += step if erro > 0 else -step
            erro_anterior = erro

        if convergiu:
            perda_com = q_total / 1000
            delta_T = Tq_fin - To_fin
            
            h_conv_sem = 1.31 * (delta_T ** (1/3))  # para placa vertical em ar
            Tfq_K = Tq_fin + 273.15
            To_K = To_fin + 273.15
            hr_sem = e * sigma * (Tfq_K**4 - To_K**4) / delta_T
            h_total_sem = h_conv_sem + hr_sem
            
            q_sem_isolante = h_total_sem * (Tq_fin - To_fin)
            perda_sem = q_sem_isolante / 1000
            economia_kw = perda_sem - perda_com
            economia_kwh = economia_kw / ef
            custo_kwh = valor_comb / pc
            economia_rs = economia_kwh * custo_kwh
            economia_pct = 100 * (1 - perda_com / perda_sem) if perda_sem != 0 else 0

            st.success(f"Temperatura da face fria: {Tf:.1f} °C")
            st.info(f"Perda com isolante: {perda_com:.3f} kW/m²")
            st.warning(f"Perda sem isolante: {perda_sem:.3f} kW/m²")
            st.success(f"💰 **Economia estimada por hora por metro quadrado:** R$ {economia_rs:.2f}")
            st.success(f"📉 **Economia percentual:** {economia_pct:.1f}%")

            st.markdown("Esta aba calcula o retorno financeiro com base em valores médios nacionais do custo dos combustíveis.")
        else:
            st.error("O cálculo não convergiu.")
