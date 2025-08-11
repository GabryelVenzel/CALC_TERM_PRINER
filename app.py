### **Código Refatorado da Aplicação IsolaFácil**

```python
import streamlit as st
import math
import time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# --- CONFIGURAÇÕES GERAIS E ESTILO (Definido uma única vez) ---
st.set_page_config(page_title="Calculadora IsolaFácil", layout="wide")

# Estilo visual aplicado globalmente
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
    .stMetric {
        border: 1px solid #E0E0E0;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
    input[type="radio"], input[type="checkbox"] {
        accent-color: #003366;
    }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES GLOBAIS ---
e = 0.9  # Emissividade
sigma = 5.67e-8  # Constante de Stefan-Boltzmann

# --- CONEXÃO COM GOOGLE SHEETS E CACHING ---
# REFACTOR: Funções de conexão e carregamento de dados com cache para performance.

@st.cache_resource(ttl=600)  # Cache do recurso de conexão por 10 min
def autorizar_cliente_gspread():
    """Autoriza o cliente gspread e o retorna."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    gcp_json = json.loads(st.secrets["GCP_JSON"])
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_json, scope)
    client = gspread.authorize(credentials)
    return client

@st.cache_data(ttl=600) # Cache dos dados por 10 min
def carregar_isolantes():
    """Carrega os dados dos isolantes da planilha para um DataFrame."""
    try:
        client = autorizar_cliente_gspread()
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1W1JHXAnGJeWbGVK0AmORux5I7CYTEwoBIvBfVKO40aY")
        worksheet = sheet.worksheet("Isolantes")
        df = pd.DataFrame(worksheet.get_all_records())
        # Garante que colunas de coeficientes existam e preenche NaNs com 0
        coef_cols = ['k0', 'k1', 'k2', 'k3', 'k4', 'a', 'b']
        for col in coef_cols:
            if col not in df.columns:
                df[col] = 0
        df[coef_cols] = df[coef_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
        return df
    except Exception as ex:
        st.error(f"Erro ao conectar com o Google Sheets: {ex}")
        return pd.DataFrame()

def get_worksheet():
    """Retorna o objeto worksheet para operações de escrita."""
    client = autorizar_cliente_gspread()
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1W1JHXAnGJeWbGVK0AmORux5I7CYTEwoBIvBfVKO40aY")
    return sheet.worksheet("Isolantes")

# --- FUNÇÕES DE CÁLCULO E LÓGICA (Refatoradas) ---

def calcular_k(isolante_selecionado, T_media):
    """
    Calcula a condutividade térmica k(T) de forma segura, sem usar eval().
    'isolante_selecionado' é uma linha (Series) do DataFrame.
    """
    modelo = isolante_selecionado.get('modelo_k', 'Constante')
    try:
        if modelo == "Constante":
            return isolante_selecionado['k0']
        elif modelo == "Linear":
            return isolante_selecionado['k0'] + isolante_selecionado['k1'] * T_media
        elif modelo == "Polinomial":
            return (isolante_selecionado['k0'] +
                    isolante_selecionado['k1'] * T_media +
                    isolante_selecionado['k2'] * T_media**2 +
                    isolante_selecionado['k3'] * T_media**3 +
                    isolante_selecionado['k4'] * T_media**4)
        elif modelo == "Exponencial":
            return isolante_selecionado['a'] * math.exp(isolante_selecionado['b'] * T_media)
        else:
            st.error(f"Modelo de k(T) '{modelo}' desconhecido.")
            return None
    except Exception as ex:
        st.error(f"Erro ao calcular k(T): {ex}")
        return None

def calcular_h_conv(Tf, To, L_caracteristico):
    """
    Calcula o coeficiente de transferência de calor por convecção natural.
    Premissa: Placa Plana Vertical. L_caracteristico é a altura da placa (aqui, espessura total).
    """
    # Propriedades do ar no filme de temperatura
    Tf_K = Tf + 273.15
    To_K = To + 273.15
    T_film_K = (Tf_K + To_K) / 2
    
    # Propriedades do ar a T_film_K (aproximações comuns para cálculos de isolamento)
    g = 9.81
    beta = 1 / T_film_K
    nu = 1.589e-5 * (T_film_K / 293.15)**0.7 # Visc. cinemática com correção de temp.
    alpha = 2.25e-5 * (T_film_K / 293.15)**0.8 # Difus. térmica com correção de temp.
    k_ar = 0.0263

    delta_T = abs(Tf - To)
    if delta_T == 0: return 0 # Evita divisão por zero

    Ra = (g * beta * delta_T * L_caracteristico**3) / (nu * alpha)

    # Correlação de Nusselt para placa vertical
    Nu = (0.825 + (0.387 * Ra**(1/6)) / (1 + (0.492 / (nu/alpha))**(9/16))**(8/27))**2
    
    h_conv = Nu * k_ar / L_caracteristico
    return h_conv

def encontrar_temperatura_face_fria(Tq, To, L_total, isolante_selecionado):
    """
    Função centralizada para calcular iterativamente a temperatura da face fria (Tf).
    Retorna (Tf, q_total_transferido, convergiu).
    """
    Tf = To + 10.0  # Chute inicial
    max_iter = 1000
    step = 50.0
    min_step = 0.001
    tolerancia = 0.5
    erro_anterior = None

    for i in range(max_iter):
        T_media = (Tq + Tf) / 2
        k = calcular_k(isolante_selecionado, T_media)
        if k is None or k == 0:
            st.error("Condutividade térmica (k) inválida. Verifique o material.")
            return None, None, False

        q_conducao = k * (Tq - Tf) / L_total

        Tf_K = Tf + 273.15
        To_K = To + 273.15
        
        h_conv = calcular_h_conv(Tf, To, L_total)
        q_rad = e * sigma * (Tf_K**4 - To_K**4)
        q_conv = h_conv * (Tf - To)
        q_transferencia_total = q_conv + q_rad

        erro = q_conducao - q_transferencia_total

        if abs(erro) < tolerancia:
            return Tf, q_transferencia_total, True

        if erro_anterior is not None and erro * erro_anterior < 0:
            step = max(min_step, step * 0.5)

        Tf += step if erro > 0 else -step
        erro_anterior = erro

    return Tf, None, False

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'convergiu' not in st.session_state:
    st.session_state.convergiu = None
if 'q_transferencia' not in st.session_state:
    st.session_state.q_transferencia = None
if 'Tf' not in st.session_state:
    st.session_state.Tf = None

# --- INTERFACE PRINCIPAL ---
logo = Image.open("logo.png")
st.image(logo, width=300)
st.title("Calculadora IsolaFácil")

# Carregar dados dos isolantes uma vez
df_isolantes = carregar_isolantes()
if df_isolantes.empty:
    st.stop()

# --- INTERFACE LATERAL (ADMIN) ---
with st.sidebar.expander("Opções de Administrador", expanded=False):
    senha = st.text_input("Digite a senha", type="password", key="senha_admin")

    if senha == "Priner123":
        aba_admin = st.radio("Escolha a opção", ["Cadastrar Isolante", "Gerenciar Isolantes"])

        if aba_admin == "Cadastrar Isolante":
            st.subheader("Cadastrar Novo Isolante")
            nome = st.text_input("Nome do Isolante", key="novo_nome")

            modelo_k = st.radio("Modelo de função k(T)", ["Constante", "Linear", "Polinomial", "Exponencial"], key="novo_modelo")
            
            # REFACTOR: Coleta coeficientes em vez de strings para `eval()`
            params = {'nome': nome, 'modelo_k': modelo_k, 'k0': 0, 'k1': 0, 'k2': 0, 'k3': 0, 'k4': 0, 'a': 0, 'b': 0}

            if modelo_k == "Constante":
                params['k0'] = st.number_input("k₀", value=0.035, format="%.6f", key="p_k0c")
            elif modelo_k == "Linear":
                params['k0'] = st.number_input("k₀", value=0.030, format="%.6f", key="p_k0l")
                params['k1'] = st.number_input("k₁ (coef. de T)", value=0.0001, format="%.6f", key="p_k1l")
            elif modelo_k == "Polinomial":
                # ... (entradas para k0, k1, k2, k3, k4)
                 params['k0'] = st.number_input("k₀", value=0.025, format="%.6f")
                 params['k1'] = st.number_input("k₁ (T¹)", value=0.0001, format="%.6f")
                 params['k2'] = st.number_input("k₂ (T²)", value=0.0, format="%.6f")
                 params['k3'] = st.number_input("k₃ (T³)", value=0.0, format="%.6f")
                 params['k4'] = st.number_input("k₄ (T⁴)", value=0.0, format="%.6f")
            elif modelo_k == "Exponencial":
                params['a'] = st.number_input("a (coeficiente)", value=0.0387, format="%.6f", key="p_a")
                params['b'] = st.number_input("b (expoente)", value=0.0019, format="%.6f", key="p_b")

            if st.button("Cadastrar"):
                if not nome.strip():
                    st.error("Digite um nome para o isolante.")
                elif nome in df_isolantes['nome'].tolist():
                    st.warning("Já existe um isolante com esse nome.")
                else:
                    try:
                        worksheet = get_worksheet()
                        # A ordem deve corresponder exatamente às colunas da planilha
                        new_row = [params[col] for col in ['nome', 'modelo_k', 'k0', 'k1', 'k2', 'k3', 'k4', 'a', 'b']]
                        worksheet.append_row(new_row)
                        st.success(f"Isolante {nome} cadastrado com sucesso!")
                        st.cache_data.clear() # Limpa o cache para recarregar a lista
                    except Exception as e:
                        st.error(f"Falha ao cadastrar: {e}")

        elif aba_admin == "Gerenciar Isolantes":
            st.subheader("Isolantes Cadastrados")
            for index, isolante in df_isolantes.iterrows():
                st.write(f"**{isolante['nome']}**")
                if st.button(f"Excluir {isolante['nome']}", key=f"del_{isolante['nome']}"):
                    try:
                        worksheet = get_worksheet()
                        cell = worksheet.find(isolante['nome'])
                        if cell:
                            worksheet.delete_rows(cell.row)
                            st.success(f"Isolante {isolante['nome']} excluído com sucesso!")
                            st.cache_data.clear()
                            time.sleep(1) # Aguarda para dar tempo de atualizar
                            st.rerun()
                    except Exception as e:
                        st.error(f"Falha ao excluir: {e}")

# --- INTERFACE COM TABS ---
abas = st.tabs(["🔥 Cálculo Térmico Quente", "🧊 Cálculo Térmico Frio", "💰 Cálculo Financeiro"])

# ==============================================================================
# ABA 1: CÁLCULO TÉRMICO QUENTE
# ==============================================================================
with abas[0]:
    materiais = df_isolantes['nome'].tolist()
    material_selecionado_nome = st.selectbox("Escolha o material do isolante", materiais, key="mat_quente")
    isolante_selecionado = df_isolantes[df_isolantes['nome'] == material_selecionado_nome].iloc[0]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        Tq = st.number_input("Temperatura da face quente [°C]", value=250.0)
    with col2:
        To = st.number_input("Temperatura ambiente [°C]", value=30.0)
    with col3:
        numero_camadas = st.number_input("Número de camadas", min_value=1, max_value=3, value=1, step=1)
        
    espessuras = []
    cols = st.columns(numero_camadas)
    for i in range(numero_camadas):
        with cols[i]:
            esp = st.number_input(f"Espessura camada {i+1} [mm]", value=51.0 / numero_camadas, key=f"L{i+1}_quente")
            espessuras.append(esp)

    L_total = sum(espessuras) / 1000

    if st.button("Calcular Face Fria"):
        with st.spinner("Calculando... Por favor, aguarde."):
            Tf, q_transferencia, convergiu = encontrar_temperatura_face_fria(Tq, To, L_total, isolante_selecionado)
            st.session_state.Tf = Tf
            st.session_state.q_transferencia = q_transferencia
            st.session_state.convergiu = convergiu
    
    if st.session_state.convergiu is not None:
        if st.session_state.convergiu:
            st.subheader("Resultados")
            st.success(f"\U00002705 Temperatura da face fria: {st.session_state.Tf:.1f} °C".replace('.', ','))

            if numero_camadas > 1:
                st.subheader("Temperaturas Intermediárias")
                # REFACTOR: Cálculo de temp. intermediária baseado em resistência térmica
                T_atual = Tq
                q_total = st.session_state.q_transferencia
                k_medio = calcular_k(isolante_selecionado, (Tq + st.session_state.Tf) / 2)

                for i in range(numero_camadas - 1):
                    resistencia_camada = (espessuras[i] / 1000) / k_medio
                    delta_T_camada = q_total * resistencia_camada
                    T_interface = T_atual - delta_T_camada
                    st.info(f"Temperatura entre camada {i+1} e {i+2}: {T_interface:.1f} °C".replace('.', ','))
                    T_atual = T_interface
        else:
            st.error("\U0000274C O cálculo não convergiu. Tente ajustar os parâmetros de entrada.")

    st.markdown("--- \n > **Observações:** Emissividade de 0.9 considerada. O cálculo de convecção assume uma superfície plana vertical.")

# ==============================================================================
# ABA 2: CÁLCULO TÉRMICO FRIO
# ==============================================================================
with abas[1]:
    material_frio_nome = st.selectbox("Escolha o material do isolante", df_isolantes['nome'].tolist(), key="mat_frio")
    isolante_frio = df_isolantes[df_isolantes['nome'] == material_frio_nome].iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        Ti_frio = st.number_input("Temperatura interna [°C]", value=5.0, key="Ti_frio")
    with col2:
        Ta_frio = st.number_input("Temperatura ambiente [°C]", value=25.0, key="Ta_frio")
    with col3:
        UR = st.number_input("Umidade relativa do ar [%]", min_value=0.0, max_value=100.0, value=70.0, step=1.0)

    if st.button("Calcular Espessura Mínima (Anti-Condensação)"):
        with st.spinner("Iterando para encontrar espessura mínima..."):
            # 1. Calcular temperatura de orvalho (Magnus)
            a_mag, b_mag = 17.27, 237.7
            alfa = ((a_mag * Ta_frio) / (b_mag + Ta_frio)) + math.log(UR / 100.0)
            T_orvalho = (b_mag * alfa) / (a_mag - alfa)
            st.info(f"💧 Temperatura de orvalho calculada: {T_orvalho:.1f} °C")

            # 2. Iterar para encontrar L mínimo
            L_min = 0.001  # espessura mínima (1mm)
            L_max = 0.5    # limite de cálculo (500mm)
            passo_L = 0.001 # incremento de 1mm
            
            espessura_final = None
            for L_teste in [i * passo_L for i in range(1, int(L_max/passo_L) + 1)]:
                # Para cada espessura, calcula o Tf resultante
                Tf, _, convergiu = encontrar_temperatura_face_fria(Ti_frio, Ta_frio, L_teste, isolante_frio)
                
                if convergiu and Tf >= T_orvalho:
                    espessura_final = L_teste
                    break
            
            if espessura_final:
                st.success(f"✅ Espessura mínima para evitar condensação: {espessura_final * 1000:.1f} mm".replace('.', ','))
            else:
                st.error("❌ Não foi possível encontrar uma espessura que evite condensação até 500 mm.")


# ==============================================================================
# ABA 3: CÁLCULO FINANCEIRO
# ==============================================================================
with abas[2]:
    combustiveis = {
        "Óleo Combustível BPF (kg)": {"valor": 3.50, "pc_kwh": 11.34, "eficiencia": 0.80},
        "Gás Natural (m³)": {"valor": 3.60, "pc_kwh": 9.65, "eficiencia": 0.75},
        "Lenha Eucalipto 30% umidade (ton)": {"valor": 200.00, "pc_kwh": 3500.00, "eficiencia": 0.70},
        "Vapor (ton)": {"valor": 100.00, "pc_kwh": 650.00, "eficiencia": 1.00},
        "Eletricidade (kWh)": {"valor": 0.75, "pc_kwh": 1.00, "eficiencia": 1.00}
    }

    material_fin_nome = st.selectbox("Escolha o material do isolante", df_isolantes['nome'].tolist(), key="mat_fin")
    isolante_fin = df_isolantes[df_isolantes['nome'] == material_fin_nome].iloc[0]
    
    combustivel_sel = st.selectbox("Tipo de combustível", list(combustiveis.keys()))
    comb = combustiveis[combustivel_sel]
    
    valor_padrao = comb["valor"]
    pc = comb["pc_kwh"]
    ef = comb["eficiencia"]

    editar_valor = st.checkbox("Editar custo do combustível/energia")
    if editar_valor:
        valor_comb = st.number_input("Custo (R$)", min_value=0.0, value=valor_padrao, step=0.01, key="valor_editado")
    else:
        valor_comb = valor_padrao

    col1, col2, col3 = st.columns(3)
    with col1:
        Tq_fin = st.number_input("Temperatura da operação [°C]", value=250.0, key="Tq_fin")
    with col2:
        To_fin = st.number_input("Temperatura ambiente [°C]", value=30.0, key="To_fin")
    with col3:
        espessura_fin = st.number_input("Espessura do isolante [mm]", value=51.0, key="esp_fin") / 1000

    st.subheader("Parâmetros para Cálculo de Retorno")
    col1, col2, col3 = st.columns(3)
    with col1:
        metragem_quadrada = st.number_input("Área do projeto (m²)", min_value=1.0, value=10.0, step=1.0)
    with col2:
        horas_por_dia = st.number_input("Horas de operação/dia", min_value=1.0, max_value=24.0, value=8.0)
    with col3:
        dias_por_semana = st.number_input("Dias de operação/semana", min_value=1, max_value=7, value=5)

    if st.button("Calcular Economia Financeira"):
        with st.spinner("Calculando economia..."):
            Tf, q_com_isolante, convergiu = encontrar_temperatura_face_fria(Tq_fin, To_fin, espessura_fin, isolante_fin)

            if convergiu:
                perda_com_kw = q_com_isolante / 1000

                # Cálculo da perda sem isolante
                h_conv_sem = calcular_h_conv(Tq_fin, To_fin, 1.0) # L característico de 1m para uma parede grande
                Tq_K = Tq_fin + 273.15
                To_K = To_fin + 273.15
                q_rad_sem = e * sigma * (Tq_K**4 - To_K**4)
                q_conv_sem = h_conv_sem * (Tq_fin - To_fin)
                q_sem_isolante = q_conv_sem + q_rad_sem
                perda_sem_kw = q_sem_isolante / 1000
                
                economia_kw_m2 = perda_sem_kw - perda_com_kw
                
                # Custo por kWh gerado
                custo_kwh_util = valor_comb / (pc * ef)

                economia_rs_hora_m2 = economia_kw_m2 * custo_kwh_util
                economia_mensal_total = economia_rs_hora_m2 * metragem_quadrada * horas_por_dia * dias_por_semana * 4.33 # Média de semanas/mês
                
                st.subheader("Resultados Financeiros")

                # UX: Usando st.metric para destacar resultados
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    label="Economia Mensal Estimada",
                    value=f"R$ {economia_mensal_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                )
                m2.metric(
                    label="Redução de Perda Térmica",
                    value=f"{ (economia_kw_m2 / perda_sem_kw * 100):.1f} %",
                )
                m3.metric(
                    label="Temperatura da Superfície",
                    value=f"{Tf:.1f} °C",
                    delta=f"{(Tf - Tq_fin):.1f} °C vs. sem isolante",
                    delta_color="inverse"
                )

                # UX: Gráfico de barras para comparação visual
                st.subheader("Comparativo de Perda Térmica (por m²)")
                df_perdas = pd.DataFrame({
                    "Situação": ["Sem Isolante", "Com Isolante"],
                    "Perda Térmica (kW/m²)": [perda_sem_kw, perda_com_kw]
                }).set_index("Situação")
                st.bar_chart(df_perdas)

            else:
                st.error("O cálculo da temperatura não convergiu. Verifique os dados de entrada.")

```
        else:
            st.error("O cálculo não convergiu.")


