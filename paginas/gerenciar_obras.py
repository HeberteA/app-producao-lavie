import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    mes_selecionado = st.session_state.selected_month
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    
    st.header("Gerenciar Obras 🏗️")
    
    st.subheader("Adicionar Nova Obra")
    with st.form("go_add_obra_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_obra = st.text_input("Nome da Nova Obra", key="go_nome_obra")
        with col2:
            codigo_acesso = st.text_input("Código de Acesso para a Obra", key="go_codigo_acesso")
        
        if st.form_submit_button("Adicionar Obra"):
            if nome_obra.strip() and codigo_acesso.strip():
                with st.spinner("Adicionando nova obra, aguarde..."):
                    if db_utils.adicionar_obra(nome_obra, codigo_acesso):
                        st.success(f"Obra '{nome_obra}' adicionada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
            else:
                st.warning("O nome da obra e o código de acesso não podem estar em branco.")

    st.markdown("---")
    st.subheader("Remover Obra Existente")
    if obras_df.empty:
        st.info("Nenhuma obra cadastrada.")
    else:
        status_geral_obras_df = status_df[status_df['funcionario_id'] == 0]
        
        df_para_exibir = pd.merge(
            obras_df,
            status_geral_obras_df[['obra_id', 'Status']], 
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
        
        obra_para_remover_nome = st.selectbox(
            "Selecione a obra para remover", options=obras_df['NOME DA OBRA'].unique(), 
            index=None, placeholder="Selecione na lista acima...", key="go_obra_remover"
        )
        if obra_para_remover_nome:
            st.warning(f"Atenção: A remoção da obra '{obra_para_remover_nome}' é permanente e não pode ser desfeita.")
            
            confirmacao = st.checkbox(f"Sim, confirmo a remoção da obra '{obra_para_remover_nome}'.", key="go_confirm_delete")
            
            if st.button(f"Remover Obra", type="primary", key="go_remover_btn", disabled=not confirmacao):
                with st.spinner("Removendo a obra..."):
                    obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_remover_nome, 'id']
                    if not obra_info.empty:
                        obra_id_para_remover = int(obra_info.iloc[0])
                        if db_utils.remover_obra(obra_id_para_remover):
                            st.success(f"Obra '{obra_para_remover_nome}' removida com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.error(f"Erro: Obra '{obra_para_remover_nome}' não encontrada. A página pode estar desatualizada.")

    st.markdown("---")
    st.subheader("Alterar Código de Acesso")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            obra_para_alterar_codigo_nome = st.selectbox(
                "1. Selecione a Obra", options=obras_df['NOME DA OBRA'].unique(),
                index=None, placeholder="Selecione...", key="go_obra_alterar"
            )
        with col2:
            novo_codigo = st.text_input("2. Digite o Novo Código de Acesso", type="password", key="go_novo_codigo")
        
        if st.button("Alterar Código", use_container_width=True, key="go_alterar_btn"):
            if obra_para_alterar_codigo_nome and novo_codigo.strip():
                with st.spinner("Alterando o código..."):
                    obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_alterar_codigo_nome, 'id']
                    if not obra_info.empty:
                        obra_id_para_alterar = int(obra_info.iloc[0])
                        if db_utils.mudar_codigo_acesso_obra(obra_id_para_alterar, novo_codigo):
                            st.success(f"Código de acesso da obra '{obra_para_alterar_codigo_nome}' alterado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.error(f"Erro: Obra '{obra_para_alterar_codigo_nome}' não encontrada. A página pode estar desatualizada.")
            else:
                st.warning("Por favor, selecione uma obra e digite o novo código.")
