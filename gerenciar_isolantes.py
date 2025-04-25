import streamlit as st
from gspread_utils import carregar_isolantes, excluir_isolante

def gerenciar_isolantes_interface():
    st.subheader("Isolantes Cadastrados")
    isolantes = carregar_isolantes()
    for i in isolantes:
        st.write(f"**{i['nome']}**")
        if st.button(f"Excluir {i['nome']}"):
            excluir_isolante(i['nome'])
            st.success(f"Isolante {i['nome']} excluído com sucesso!")
