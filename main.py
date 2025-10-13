import streamlit as st
import sys
import os
from datetime import datetime, timedelta, date
import io
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_utils
import utils
from pages import lancamento_folha, auditoria, gerenciar_funcionarios, gerenciar_obras, resumo_da_folha, remover_lancamentos, dashboard_de_analise

st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Lavie.png", width=1000)
    st.header("Login")

    obras_df_login = db_utils.get_obras()
    acessos_df_login = db_utils.get_acessos()

    if obras_df_login.empty or acessos_df_login.empty:
        st.error("Não foi possível carregar os dados das obras para o login.")
        return
        
    admin_login = st.checkbox("Entrar como Administrador")
    if admin_login:
        admin_password = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar como Admin", use_container_width=True, type="primary"):
            if 'admin' in st.secrets and st.secrets.admin.password == admin_password:
                st.session_state.logged_in = True
                st.session_state.role = 'admin'
                st.session_state.obra_logada = 'Todas'
                st.session_state.page = 'auditoria'
                st.rerun()
            else:
                st.error("Senha de administrador incorreta.")
    else:
        obras_com_acesso = pd.merge(obras_df_login, acessos_df_login, left_on='id', right_on='obra_id')
        obra_login = st.selectbox("Selecione a Obra", options=obras_com_acesso['NOME DA OBRA'].unique(), index=None, placeholder="Escolha a obra...")
        codigo_login = st.text_input("Código de Acesso", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            if obra_login and codigo_login:
                try:
                    codigo_correto = obras_com_acesso.loc[obras_com_acesso['NOME DA OBRA'] == obra_login, 'codigo_acesso'].iloc[0]
                    if codigo_correto == codigo_login:
                        st.session_state.logged_in = True
                        st.session_state.role = 'user'
                        st.session_state.obra_logada = obra_login
                        st.session_state.page = 'lancamento_folha'
                        st.rerun()
                    else:
                        st.error("Obra ou código de acesso incorreto.")
                except IndexError:
                    st.error("Obra ou código de acesso incorreto.")
            else:
                st.warning("Por favor, selecione a obra e insira o código.")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    engine = db_utils.get_db_connection()
    if engine is None:
        st.error("Falha crítica na conexão com o banco de dados. O aplicativo não pode continuar.")
        st.stop()

    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = datetime.now().strftime('%Y-%m')
    if 'page' not in st.session_state:
        st.session_state.page = 'auditoria' if st.session_state.role == 'admin' else 'lancamento_folha'

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])

        st.header("Navegação")
        if st.session_state.role == 'user':
            if st.button("📝 Lançamento Folha", use_container_width=True):
                st.session_state.page = 'lancamento_folha'
        if st.session_state.role == 'admin':
            if st.button("✏️ Auditoria", use_container_width=True):
                st.session_state.page = 'auditoria'
            if st.button("👥 Gerenciar Funcionários", use_container_width=True):
                st.session_state.page = 'gerenciar_funcionarios'
            if st.button("🏗️ Gerenciar Obras", use_container_width=True):
                st.session_state.page = 'gerenciar_obras'
        
        if st.button("📊 Resumo da Folha", use_container_width=True):
            st.session_state.page = 'resumo_da_folha'
        if st.button("🗑️ Remover Lançamentos", use_container_width=True):
            st.session_state.page = 'remover_lancamentos'
        if st.button("📈 Dashboard de Análise", use_container_width=True):
            st.session_state.page = 'dashboard_de_analise'
        
        st.markdown("---")
        st.subheader("Mês de Referência")
        current_month_str = datetime.now().strftime('%Y-%m')
        available_months = [current_month_str, (datetime.now() - timedelta(days=30)).strftime('%Y-%m')]
        available_months = sorted(list(set(available_months)), reverse=True)
        
        try:
            current_index = available_months.index(st.session_state.selected_month)
        except ValueError:
            current_index = 0 

        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=current_index,
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


    page_to_render = st.session_state.page

    if page_to_render == 'lancamento_folha':
        lancamento_folha.render_page()
    elif page_to_render == 'auditoria':
        auditoria.render_page()
    elif page_to_render == 'gerenciar_funcionarios':
        gerenciar_funcionarios.render_page()
    elif page_to_render == 'gerenciar_obras':
        gerenciar_obras.render_page()
    elif page_to_render == 'resumo_da_folha':
        resumo_da_folha.render_page()
    elif page_to_render == 'remover_lancamentos':
        remover_lancamentos.render_page()
    elif page_to_render == 'dashboard_de_analise':
        dashboard_de_analise.render_page()
        try:
            current_index = available_months.index(st.session_state.selected_month)
        except ValueError:
            current_index = 0 

        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=current_index,
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


    page_to_render = st.session_state.page
    
    page_map = {
        'lancamento_folha': lancamento_folha,
        'auditoria': auditoria,
        'gerenciar_funcionarios': gerenciar_funcionarios,
        'gerenciar_obras': gerenciar_obras,
        'resumo_da_folha': resumo_da_folha,
        'remover_lancamentos': remover_lancamentos,
        'dashboard_de_analise': dashboard_de_analise
    }
    
    if page_to_render in page_map:
        page_map[page_to_render].render_page()






