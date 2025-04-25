import streamlit as st
from gspread_utils import carregar_isolantes, cadastrar_isolante

def cadastrar_isolante_interface():
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
