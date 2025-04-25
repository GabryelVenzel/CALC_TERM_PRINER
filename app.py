import streamlit as st
from cadastrar_isolante import cadastrar_isolante_interface
from gerenciar_isolantes import gerenciar_isolantes_interface
from gspread_utils import carregar_isolantes, cadastrar_isolante, excluir_isolante
from calculo_termo import calcular_k, calcular_h_conv

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

# --- ACESSO --- 
with st.sidebar.expander("Opções", expanded=False):
    senha = st.text_input("Digite a senha", type="password")

    if senha == "Priner123":
        aba = st.radio("Escolha a opção", ["Cadastrar Isolante", "Gerenciar Isolantes"])

        if aba == "Cadastrar Isolante":
            cadastrar_isolante_interface()
        elif aba == "Gerenciar Isolantes":
            gerenciar_isolantes_interface()

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
