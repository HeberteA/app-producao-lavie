import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    mes_selecionado = st.session_state.selected_month
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    
    st.header("Gerenciar Obras 🏗️")
    
    with st.form("go_add_obra_form", clear_on_submit=True):
        st.subheader("Adicionar Nova Obra")
        nome_obra = st.text_input("Nome da Nova Obra", key="go_nome_obra")
        codigo_acesso = st.text_input("Código de Acesso para a Obra", key="go_codigo_acesso")
        if st.form_submit_button("Adicionar Obra"):
            if nome_obra and codigo_acesso:
                if db_utils.adicionar_obra(nome_obra, codigo_acesso):
                    st.success(f"Obra '{nome_obra}' adicionada com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.warning("Por favor, preencha o nome e o código de acesso.")

    st.markdown("---")
    st.subheader("Remover Obra Existente")
    obra_para_remover_nome = st.selectbox(
        "Selecione a obra para remover", options=obras_df['NOME DA OBRA'].unique(), 
        index=None, placeholder="Selecione...", key="go_obra_remover"
    )
    if obra_para_remover_nome:
        st.warning(f"Atenção: A remoção de uma obra é permanente e não pode ser desfeita. Certifique-se de que não há mais funcionários ativos alocados em '{obra_para_remover_nome}'.")
        if st.button(f"Remover Obra '{obra_para_remover_nome}'", type="primary", key="go_remover_btn"):
            obra_id_para_remover = obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_remover_nome, 'id'].iloc[0]
            if db_utils.remover_obra(obra_id_para_remover):
                st.success(f"Obra '{obra_para_remover_nome}' removida com sucesso!")
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    st.subheader("Alterar Código de Acesso")
    obra_para_alterar_codigo_nome = st.selectbox(
        "1. Selecione a Obra", options=obras_df['NOME DA OBRA'].unique(),
        index=None, placeholder="Selecione...", key="go_obra_alterar"
    )
    novo_codigo = st.text_input("2. Digite o Novo Código de Acesso", type="password", key="go_novo_codigo")
    if st.button("Alterar Código", use_container_width=True, key="go_alterar_btn"):
        if obra_para_alterar_codigo_nome and novo_codigo:
            obra_id_para_alterar = obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_alterar_codigo_nome, 'id'].iloc[0]
            if db_utils.mudar_codigo_acesso_obra(obra_id_para_alterar, novo_codigo):
                st.success(f"Código de acesso da obra '{obra_para_alterar_codigo_nome}' alterado com sucesso!")
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("Por favor, selecione uma obra e digite o novo código.")

