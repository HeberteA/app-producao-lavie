import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    if st.session_state['role'] != 'admin':
        st.stop()
    
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(st.session_state.selected_month)
    
    st.header("Gerenciar Obras 🏗️")
    
    tab_adicionar, tab_remover, tab_codigo = st.tabs(["➕ Adicionar Obra", "🗑️ Remover Obra", "🔑 Alterar Código de Acesso"])

    with tab_adicionar:
        st.subheader("Adicionar Nova Obra")
        with st.form("add_obra", clear_on_submit=True):
            col1, col2 = st.columns(2)
    
            with col1:
                nome_obra = st.text_input("Nome da Nova Obra")
    
            with col2:
                codigo_acesso = st.text_input("Código de Acesso para a Obra")
            submitted = st.form_submit_button("Adicionar Obra")
            if submitted:
                if nome_obra and codigo_acesso: 
                    if db_utils.adicionar_obra(nome_obra, codigo_acesso):
                        st.success(f"Obra '{nome_obra}' adicionada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.warning("Por favor, insira o nome e o código de acesso da obra.")

    with tab_remover:
        st.subheader("Remover Obra Existente")
        if obras_df.empty:
            st.info("Nenhuma obra cadastrada.")
        else:
            status_do_mes_df = status_df[
                (status_df['funcionario_id'] == 0)
            ]
            df_para_exibir = pd.merge(
                obras_df,
                status_do_mes_df[['obra_id', 'Status']], 
                left_on='id',
                right_on='obra_id',
                how='left'
            )
            df_para_exibir['Status'] = df_para_exibir['Status'].fillna('A Revisar')
            st.dataframe(
                df_para_exibir[['NOME DA OBRA', 'Status']].style.applymap(
                    utils.style_status,
                    subset=['Status']
                ),
                use_container_width=True
            )  
            obra_para_remover = st.selectbox(
                "Selecione a obra para remover", 
                options=obras_df['NOME DA OBRA'].unique(), 
                index=None, 
                placeholder="Selecione..."
            )
            if obra_para_remover:
                st.warning(f"Atenção: Remover uma obra não remove ou realoca os funcionários associados a ela. Certifique-se de que nenhum funcionário esteja alocado em '{obra_para_remover}' antes de continuar.")
                if st.button(f"Remover Obra '{obra_para_remover}'", type="primary"):
                    obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_remover, 'id'].iloc[0])

                    if db_utils.remover_obra(obra_id, obra_para_remover):
                        st.success(f"Obra '{obra_para_remover}' removida com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
    
    with tab_codigo:
        st.subheader("Alterar Código de Acesso")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                obra_para_alterar_codigo = st.selectbox(
                    "1. Selecione a Obra",
                    options=obras_df['NOME DA OBRA'].unique(),
                    index=None,
                    placeholder="Selecione..."
                )
            with col2:
                novo_codigo = st.text_input("2. Digite o Novo Código de Acesso", type="password")

            if st.button("Alterar Código", use_container_width=True):
                if obra_para_alterar_codigo and novo_codigo:
                    obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_alterar_codigo, 'id'].iloc[0])
                    if db_utils.mudar_codigo_acesso_obra(obra_id, novo_codigo, obra_para_alterar_codigo):
                        st.toast(f"Código de acesso da obra '{obra_para_alterar_codigo}' alterado com sucesso!", icon="🔑")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.warning("Por favor, selecione uma obra e digite o novo código.")




