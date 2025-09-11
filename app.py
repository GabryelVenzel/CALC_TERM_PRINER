import streamlit as st
import math
import time
from PIL import Image
import pandas as pd

# --- CONFIGURAÇÕES GERAIS E ESTILO ---
st.set_page_config(page_title="Calculadora IsolaFácil", layout="wide")

st.markdown("""
<style>
    .main { background-color: #FFFFFF; }
    .block-container { padding-top: 2rem; }
    h1, h2, h3, h4 { color: #003366; }
    .stButton>button { background-color: #198754; color: white; border-radius: 8px; height: 3em; width: 100%; }
    .stMetric { border: 1px solid #E0E0E0; padding: 10px; border-radius: 8px; text-align: center; }
    input[type="radio"], input[type="checkbox"] { accent-color: #003366; }
    .stSuccess, .stInfo, .stWarning { border-radius: 8px; padding: 1rem; }
    .stSuccess { background-color: #e6f2e6; color: #1a4d2e; border: 1px solid #1a4d2e; }
    .stInfo { background-color: #e6eef2; color: #1f3c58; border: 1px solid #1f3c58; }
    .stWarning { background-color: #f2f2e6; color: #514e21; border: 1px solid #514e21; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTE GLOBAL ---
sigma = 5.67e-8

# --- BANCO DE DADOS INTERNO DE ISOLANTES ---
def carregar_isolantes_local():
    """
    Cria um DataFrame com os dados dos materiais isolantes diretamente no código.
    """
    dados_isolantes = [
        {"nome": "Manta de fibra cerâmica 96kg/m³ até 1260°C", "k_func": "0.0317 * math.exp(0.0024 * T)", "T_min": 25, "T_max": 1260},
        {"nome": "Manta de fibra cerâmica 128kg/m³ até 1260°C", "k_func": "0.0349 * math.exp(0.0021 * T)", "T_min": 25, "T_max": 1260},
        {"nome": "Manta de fibra de vidro 130kg/m³ até 800°C", "k_func": "0.0286 * math.exp(0.0029 * T)", "T_min": 25, "T_max": 800},
        {"nome": "Lã de rocha 48kg/m³ até 300°C", "k_func": "0.0333 * math.exp(0.0048 * T)", "T_min": 25, "T_max": 300},
        {"nome": "Lã de rocha 64kg/m³ até 300°C", "k_func": "0.0333 * math.exp(0.0036 * T)", "T_min": 25, "T_max": 300},
        {"nome": "Lã de Vidro 12kg/m³", "k_func": "4.2e-2", "T_min": -20, "T_max": 230},
        {"nome": "Aerogel 160kg/m³ até 650°C", "k_func": "0.0183 * math.exp(0.0022 * T)", "T_min": 25, "T_max": 650},
        {"nome": "Microporoso 220kg/m³ até 1000°C", "k_func": "0.0215 + 2e-06*T + 2e-08*T**2 + 0.0*T**3 + 0.0*T", "T_min": 25, "T_max": 1000},
        {"nome": "Espuma elastomérica 50kg/m³", "k_func": "0.034 + 8e-05*T + 1e-06*T**2 + 0.0*T**3 + 0.0*T", "T_min": -50, "T_max": 110}
    ]
    df = pd.DataFrame(dados_isolantes)
    df['T_min'] = pd.to_numeric(df['T_min'], errors='coerce').fillna(-999)
    df['T_max'] = pd.to_numeric(df['T_max'], errors='coerce').fillna(9999)
    return df

# --- FUNÇÕES DE CÁLCULO ---
def calcular_k(k_func_str, T_media):
    try:
        k_func_safe = str(k_func_str).replace(',', '.')
        return eval(k_func_safe, {"math": math, "T": T_media})
    except Exception as ex:
        st.error(f"Erro na fórmula k(T) '{k_func_str}': {ex}")
        return None

def calcular_h_conv(Tf, To, wind_speed_ms=0):
    Tf_K, To_K = Tf + 273.15, To + 273.15
    T_film_K = (Tf_K + To_K) / 2
    g, beta = 9.81, 1 / T_film_K
    nu = 1.589e-5 * (T_film_K / 293.15)**0.7
    alpha = 2.25e-5 * (T_film_K / 293.15)**0.8
    k_ar = 0.0263
    Pr = nu / alpha
    delta_T = abs(Tf - To)
    if delta_T == 0: return 0
    
    # Lógica apenas para Superfície Plana
    L_c = 1.0 
    
    if wind_speed_ms >= 1.0:
        Re = (wind_speed_ms * L_c) / nu
        if Re < 5e5:
            Nu = 0.664 * (Re**0.5) * (Pr**(1/3))
        else:
            Nu = (0.037 * (Re**0.8) - 871) * (Pr**(1/3))
    else: # Convecção Natural
        L_c = 0.1 # Characteristic length for natural convection on a flat plate
        Ra = (g * beta * delta_T * L_c**3) / (nu * alpha)
        Nu = 0.27 * Ra**(1/4)
    
    return (Nu * k_ar) / L_c

def encontrar_temperatura_face_fria(Tq, To, L_total, k_func_str, emissividade, wind_speed_ms=0):
    Tf = To + 10.0
    max_iter, step, min_step, tolerancia = 1000, 50.0, 0.001, 0.5
    erro_anterior = None
    
    for i in range(max_iter):
        T_media = (Tq + Tf) / 2
        k = calcular_k(k_func_str, T_media)
        if k is None or k <= 0: return None, None, False

        # Lógica de condução apenas para Superfície Plana
        q_conducao = k * (Tq - Tf) / L_total
        
        Tf_K, To_K = Tf + 273.15, To + 273.15
        h_conv = calcular_h_conv(Tf, To, wind_speed_ms)
        q_rad = emissividade * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf - To)
        q_transferencia = q_conv + q_rad
        
        erro = q_conducao - q_transferencia
        if abs(erro) < tolerancia: return Tf, q_transferencia, True

        if erro_anterior is not None and erro * erro_anterior < 0:
            step = max(min_step, step * 0.5)
        Tf += step if erro > 0 else -step
        erro_anterior = erro
        
    return Tf, None, False

# --- INICIALIZAÇÃO E INTERFACE PRINCIPAL ---
try:
    logo = Image.open("logo.png")
    st.image(logo, width=300)
except FileNotFoundError:
    st.warning("Arquivo 'logo.png' não encontrado.")

st.title("Análise de Isolamento Térmico")

# Inicialização do session state
if 'calculo_realizado' not in st.session_state:
    st.session_state.calculo_realizado = False
if 'calculo_frio_realizado' not in st.session_state:
    st.session_state.calculo_frio_realizado = False

df_isolantes = carregar_isolantes_local()

if df_isolantes.empty:
    st.error("Ocorreu um erro ao carregar os dados internos dos materiais isolantes.")
    st.stop()

# --- INTERFACE COM TABS ---
abas = st.tabs(["🔥 Cálculo Térmico e Financeiro", "🧊 Cálculo Térmico Frio"])
with abas[0]:
    st.subheader("Parâmetros do Isolamento Térmico")
    
    # Emissividade agora é fixa
    emissividade_fixa = 0.9
    geometry = "Superfície Plana" # Geometria fixa

    material_selecionado_nome = st.selectbox("Escolha o material do isolante", df_isolantes['nome'].tolist(), key="mat_quente")

    isolante_selecionado = df_isolantes[df_isolantes['nome'] == material_selecionado_nome].iloc[0]
    k_func_str = isolante_selecionado['k_func']
    
    col_temp1, col_temp2, col_temp3 = st.columns(3)
    Tq = col_temp1.number_input("Temperatura da face quente [°C]", value=250.0)
    To = col_temp2.number_input("Temperatura ambiente [°C]", value=30.0)
    numero_camadas = col_temp3.number_input("Número de camadas de isolante", 1, 3, 1)

    espessuras = []
    cols_esp = st.columns(numero_camadas)
    for i in range(numero_camadas):
        esp = cols_esp[i].number_input(f"Espessura camada {i+1} [mm]", value=51.0/numero_camadas, key=f"L{i+1}_quente", min_value=0.1)
        espessuras.append(esp)
    L_total = sum(espessuras)

    st.markdown("---")
    
    # O cálculo financeiro e ambiental agora é padrão e não mais opcional.
    calcular_financeiro = True 
    
    st.subheader("Parâmetros do Cálculo Financeiro e Ambiental")
    st.info("💡 Os custos e fatores de emissão são pré-configurados com valores médios de mercado.")
    
    combustiveis = {
        "Óleo BPF (kg)":                   {"v": 3.50, "pc": 11.34, "ef": 0.80, "fator_emissao": 3.15},
        "Gás Natural (m³)":                {"v": 3.60, "pc": 9.65,  "ef": 0.75, "fator_emissao": 2.0},
        "Lenha Eucalipto 30% umidade (ton)": {"v": 200.00,"pc": 3500.00,"ef": 0.70, "fator_emissao": 1260},
        "Eletricidade (kWh)":                {"v": 0.75, "pc": 1.00,  "ef": 1.00, "fator_emissao": 0.0358}
    }
    
    comb_sel_nome = st.selectbox("Tipo de combustível", list(combustiveis.keys()))
    comb_sel_obj = combustiveis[comb_sel_nome]
    
    editar_valor = st.checkbox("Editar custo do combustível/energia")
    if editar_valor:
        valor_comb = st.number_input("Custo combustível (R$)", min_value=0.10, value=comb_sel_obj['v'], step=0.01, format="%.2f")
    else:
        valor_comb = comb_sel_obj['v']
        
    col_fin1, col_fin2, col_fin3 = st.columns(3)
    m2 = col_fin1.number_input("Área do projeto (m²)", min_value=0.001, value=10.0, format="%.2f")
    h_dia = col_fin2.number_input("Horas de operação/dia", 1.0, 24.0, 8.0)
    d_sem = col_fin3.number_input("Dias de operação/semana", 1, 7, 5)

    st.markdown("---")

    if st.button("Calcular", key="btn_quente"):
        st.session_state.calculo_realizado = False
        if not (isolante_selecionado['T_min'] <= Tq <= isolante_selecionado['T_max']):
            st.error(f"Material inadequado! A temperatura de operação ({Tq}°C) está fora dos limites para '{material_selecionado_nome}' (Mín: {isolante_selecionado['T_min']}°C, Máx: {isolante_selecionado['T_max']}°C).")
        elif Tq <= To:
            st.error("Erro: A temperatura da face quente deve ser maior do que a temperatura ambiente.")
        else:
            with st.spinner("Realizando cálculos..."):
                Tf, q_com_isolante, convergiu = encontrar_temperatura_face_fria(Tq, To, L_total / 1000, k_func_str, emissividade_fixa)
                if convergiu:
                    st.session_state.calculo_realizado = True
                    perda_com_kw = q_com_isolante / 1000
                    h_sem = calcular_h_conv(Tq, To)
                    q_rad_sem = emissividade_fixa * sigma * ((Tq + 273.15)**4 - (To + 273.15)**4)
                    q_conv_sem = h_sem * (Tq - To)
                    perda_sem_kw = (q_rad_sem + q_conv_sem) / 1000
                    
                    dados_para_relatorio = {
                        "material": material_selecionado_nome, "geometria": geometry, "num_camadas": numero_camadas, 
                        "esp_total": L_total, "tq": Tq, "to": To, "emissividade": emissividade_fixa, 
                        "tf": Tf, "perda_com_kw": perda_com_kw, "perda_sem_kw": perda_sem_kw, 
                        "calculo_financeiro": calcular_financeiro
                    }

                    if calcular_financeiro:
                        economia_kw_m2 = perda_sem_kw - perda_com_kw
                        custo_kwh = valor_comb / (comb_sel_obj['pc'] * comb_sel_obj['ef'])
                        eco_mensal = economia_kw_m2 * custo_kwh * m2 * h_dia * d_sem * 4.33
                        eco_anual = eco_mensal * 12
                        reducao_pct = ((economia_kw_m2 / perda_sem_kw) * 100) if perda_sem_kw > 0 else 0
                        
                        energia_efetiva_anual_kwh = economia_kw_m2 * m2 * h_dia * d_sem * 4.33 * 12
                        energia_bruta_anual_kwh = energia_efetiva_anual_kwh / comb_sel_obj['ef']
                        quantidade_comb_poupado = energia_bruta_anual_kwh / comb_sel_obj['pc']
                        co2_evitado_anual_kg = quantidade_comb_poupado * comb_sel_obj['fator_emissao']
                        co2_evitado_anual_ton = co2_evitado_anual_kg / 1000
                        
                        dados_para_relatorio.update({
                            "eco_mensal": eco_mensal, "eco_anual": eco_anual, 
                            "reducao_pct": reducao_pct, "co2_ton_ano": co2_evitado_anual_ton
                        })

                    st.session_state.dados_ultima_simulacao = dados_para_relatorio
                else:
                    st.session_state.calculo_realizado = False
                    st.error("❌ O cálculo não convergiu. Verifique os dados de entrada.")
    
    if st.session_state.get('calculo_realizado', False):
        dados = st.session_state.dados_ultima_simulacao
        st.subheader("Resultados")
        st.success(f"🌡️ Temperatura da face fria: {dados['tf']:.1f} °C".replace('.', ','))
        
        if dados['num_camadas'] > 1:
            T_atual = dados['tq']
            k_medio = calcular_k(k_func_str, (dados['tq'] + dados['tf']) / 2)
            q_com_isolante = dados['perda_com_kw'] * 1000
            if k_medio and q_com_isolante is not None:
                for i in range(dados['num_camadas'] - 1):
                    # Lógica de interface de camadas apenas para Superfície Plana
                    resistencia_camada = (espessuras[i] / 1000) / k_medio
                    delta_T_camada = q_com_isolante * resistencia_camada
                    T_interface = T_atual - delta_T_camada
                    st.success(f"↪️ Temp. entre camada {i+1} e {i+2}: {T_interface:.1f} °C".replace('.', ','))
                    T_atual = T_interface
                    
        st.info(f"⚡ Perda de calor com isolante: {dados['perda_com_kw']:.3f} kW/m²".replace('.', ','))
        st.warning(f"⚡ Perda de calor sem isolante: {dados['perda_sem_kw']:.3f} kW/m²".replace('.', ','))
        
        if dados.get('calculo_financeiro', False):
            st.subheader("Retorno Financeiro e Ambiental")
            m1, m2, m3 = st.columns(3)
            
            eco_anual_str = f"R$ {dados['eco_anual']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            eco_mensal_str = f"R$ {dados['eco_mensal']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            m1.metric(
                label="Economia Anual",
                value=eco_anual_str,
                help=f"Economia mensal estimada: {eco_mensal_str}"
            )
            m2.metric("Carbono Evitado", f"{dados.get('co2_ton_ano', 0):.2f} tCO₂e/ano")
            m3.metric("Redução de Perda", f"{dados['reducao_pct']:.1f} %")

    st.markdown("---")
    st.markdown("""
    > **Nota:** Os cálculos são realizados de acordo com as práticas recomendadas pelas normas **ASTM C680** e **ISO 12241**, em conformidade com os procedimentos da norma brasileira **ABNT NBR 16281**.
    """)

with abas[1]:
    st.subheader("Cálculo de Espessura Mínima para Minimizar Condensação")
    
    geometry_frio = "Superfície Plana" # Geometria fixa

    material_frio_nome = st.selectbox("Escolha o material do isolante", df_isolantes['nome'].tolist(), key="mat_frio")

    isolante_frio_selecionado = df_isolantes[df_isolantes['nome'] == material_frio_nome].iloc[0]
    k_func_str_frio = isolante_frio_selecionado['k_func']

    col1, col2, col3 = st.columns(3)
    Ti_frio = col1.number_input("Temperatura interna [°C]", value=5.0, key="Ti_frio")
    Ta_frio = col2.number_input("Temperatura ambiente [°C]", value=25.0, key="Ta_frio")
    UR = col3.number_input("Umidade relativa do ar [%]", 0.0, 100.0, 70.0)

    wind_speed = st.number_input("Velocidade do vento (m/s)", min_value=0.0, value=0.0, step=0.5, format="%.1f", key="wind_speed_frio")
    if wind_speed == 0:
        st.info("💡 Com velocidade do vento igual a 0 m/s, o cálculo considera convecção natural.")

    if st.button("Calcular Espessura Mínima", key="btn_frio"):
        st.session_state.calculo_frio_realizado = False
        if not (isolante_frio_selecionado['T_min'] <= Ti_frio <= isolante_frio_selecionado['T_max']):
            st.error(f"Material inadequado! A temperatura de operação ({Ti_frio}°C) está fora dos limites para '{material_frio_nome}' (Mín: {isolante_frio_selecionado['T_min']}°C, Máx: {isolante_frio_selecionado['T_max']}°C).")
        elif Ta_frio <= Ti_frio:
            st.error("Erro: A temperatura ambiente deve ser maior que a temperatura interna para o cálculo de condensação.")
        else:
            with st.spinner("Iterando para encontrar espessura..."):
                a_mag, b_mag = 17.27, 237.7
                alfa = ((a_mag * Ta_frio) / (b_mag + Ta_frio)) + math.log(UR / 100.0)
                T_orvalho = (b_mag * alfa) / (a_mag - alfa)
                st.info(f"💧 Temperatura de orvalho calculada: {T_orvalho:.1f} °C")

                espessura_final = None
                for L_teste in [i * 0.001 for i in range(1, 501)]:
                    Tf, _, convergiu = encontrar_temperatura_face_fria(
                        Ti_frio, Ta_frio, L_teste, k_func_str_frio, 
                        0.9, wind_speed_ms=wind_speed
                    )
                    if convergiu and Tf >= T_orvalho:
                        espessura_final = L_teste
                        break

                if espessura_final:
                    st.success(f"✅ Espessura mínima para Minimizar condensação: {espessura_final * 1000:.1f} mm".replace('.',','))
                    st.session_state.calculo_frio_realizado = True
                    dados_para_relatorio_frio = {
                        "material": material_frio_nome, "geometria": geometry_frio,
                        "ti": Ti_frio, "ta": Ta_frio, "ur": UR, "vento": wind_speed,
                        "t_orvalho": T_orvalho, "espessura_final": espessura_final * 1000
                    }
                    st.session_state.dados_ultima_simulacao_frio = dados_para_relatorio_frio
                else:
                    st.session_state.calculo_frio_realizado = False
                    st.error("❌ Não foi possível encontrar uma espessura que evite condensação até 500 mm.")








