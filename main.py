import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import numpy as np
import re
from gspread_dataframe import set_with_dataframe
import plotly.express as px
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

# --- FUNÇÕES DE CONEXÃO E DADOS ---
@st.cache_resource
def get_gsheets_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_data_from_gsheets(url):
    try:
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(url)

        def clean_value(value_str):
            if isinstance(value_str, (int, float)): return value_str
            s = str(value_str).replace('R$', '').strip()
            if ',' in s: s = s.replace('.', '').replace(',', '.')
            return pd.to_numeric(s, errors='coerce')

        ws_func = spreadsheet.worksheet("Funcionários")
        func_data = ws_func.get_all_values()
        funcionarios_df = pd.DataFrame([row[1:6] for row in func_data[3:] if len(row) > 5 and row[1]], columns=['NOME', 'FUNÇÃO', 'TIPO', 'SALARIO_BASE', 'OBRA'])
        funcionarios_df.dropna(how='all', inplace=True)
        funcionarios_df['SALARIO_BASE'] = funcionarios_df['SALARIO_BASE'].apply(clean_value)
        funcionarios_df.dropna(subset=['NOME', 'FUNÇÃO'], inplace=True)

        ws_precos = spreadsheet.worksheet("Tabela de Preços")
        precos_data = ws_precos.get_all_values()
        servicos_list = []
        last_discipline = ""
        def get_cell(r, idx):
            return r[idx].strip() if len(r) > idx else ""
        for row in precos_data[3:]:
            if not any(cell.strip() for cell in row): continue
            discipline, service, unit, value = get_cell(row, 1), get_cell(row, 2), get_cell(row, 3), get_cell(row, 4)
            if discipline: last_discipline = discipline
            if service and value: servicos_list.append([last_discipline, service, unit, value])
        precos_df = pd.DataFrame(servicos_list, columns=['DISCIPLINA', 'DESCRIÇÃO DO SERVIÇO', 'UNIDADE', 'VALOR'])
        precos_df['VALOR'] = precos_df['VALOR'].apply(clean_value)
        precos_df.dropna(subset=['DESCRIÇÃO DO SERVIÇO', 'VALOR'], inplace=True)
        
        ws_extras = spreadsheet.worksheet("Valores Extras")
        extras_data = ws_extras.get_all_values()
        if len(extras_data) > 1:
            data_rows = [row[:3] for row in extras_data[1:]]
            valores_extras_df = pd.DataFrame(data_rows, columns=['VALORES EXTRAS', 'UNIDADE', 'VALOR'])
        else:
            valores_extras_df = pd.DataFrame(columns=['VALORES EXTRAS', 'UNIDADE', 'VALOR'])
        if 'VALOR' in valores_extras_df.columns:
            valores_extras_df['VALOR'] = valores_extras_df['VALOR'].apply(clean_value)
        if 'VALORES EXTRAS' in valores_extras_df.columns and 'VALOR' in valores_extras_df.columns:
            valores_extras_df.dropna(subset=['VALORES EXTRAS', 'VALOR'], inplace=True)

        ws_obras = spreadsheet.worksheet("Obras")
        obras_data = ws_obras.get_all_values()
        obras_df = pd.DataFrame(obras_data[1:], columns=obras_data[0])
        obras_df.dropna(how='all', inplace=True)
        
        ws_lancamentos = spreadsheet.worksheet("Lançamentos")
        lancamentos_data = ws_lancamentos.get_all_values()
        colunas_lancamentos = ['Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Data do Serviço', 'Observação']
        if len(lancamentos_data) > 1:
            data_rows = [row[:len(colunas_lancamentos)] for row in lancamentos_data[1:]]
            lancamentos_df = pd.DataFrame(data_rows, columns=colunas_lancamentos)
        else:
            lancamentos_df = pd.DataFrame(columns=colunas_lancamentos)
        
        for col in ['Quantidade', 'Valor Unitário', 'Valor Parcial']:
            if col in lancamentos_df.columns:
                lancamentos_df[col] = pd.to_numeric(lancamentos_df[col], errors='coerce')
        
        lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'], errors='coerce')
        lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'], errors='coerce')
        lancamentos_df.dropna(subset=['Data'], inplace=True)
        return funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_df

    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Aba da planilha não encontrada: '{e}'. Verifique o nome.")
        st.stop()
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar os dados da planilha: {e}")
        st.stop()

# --- FUNÇÕES AUXILIARES ---
def calcular_salario_final(row):
    if str(row['TIPO']).upper() == 'PRODUCAO':
        return max(row['SALÁRIO BASE (R$)'], row['PRODUÇÃO (R$)'])
    else: 
        return row['SALÁRIO BASE (R$)'] + row['PRODUÇÃO (R$)']

def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

def safe_float(value):
    try:
        s = str(value).replace('R$', '').strip()
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def login_page(obras_df):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Lavie.png", width=300) 
    
    st.header("Login")
    
    admin_login = st.checkbox("Entrar como Administrador")

    if admin_login:
        admin_password = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar como Admin", use_container_width=True, type="primary"):
            if st.secrets.admin.password == admin_password:
                st.session_state['logged_in'] = True
                st.session_state['role'] = 'admin'
                st.session_state['obra_logada'] = 'Todas'
                st.rerun()
            else:
                st.error("Senha de administrador incorreta.")
    else:
        codigos_obras = st.secrets.get("códigos_obras", {})
        if not codigos_obras:
            st.error("Códigos de acesso não configurados nos Secrets do Streamlit.")
            return

        obra_login = st.selectbox("Selecione a Obra", options=obras_df['NOME DA OBRA'].unique(), index=None, placeholder="Escolha a obra...")
        codigo_login = st.text_input("Código de Acesso", type="password")

        if st.button("Entrar", use_container_width=True, type="primary"):
            if obra_login and codigo_login:
                if obra_login in codigos_obras and codigos_obras[obra_login] == codigo_login:
                    st.session_state['logged_in'] = True
                    st.session_state['role'] = 'user'
                    st.session_state['obra_logada'] = obra_login
                    st.rerun()
                else:
                    st.error("Obra ou código de acesso incorreto.")
            else:
                st.warning("Por favor, selecione a obra e insira o código.")

# --- LÓGICA PRINCIPAL DO APP ---
sheet_url = "https://docs.google.com/spreadsheets/d/1l5ChC0yrgiscqKBQB3rIEqA62nP97sLKZ_dAwiiVwiI/edit?usp=sharing"

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    try:
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(sheet_url)
        ws_obras = spreadsheet.worksheet("Obras")
        obras_data = ws_obras.get_all_values()
        obras_df = pd.DataFrame(obras_data[1:], columns=obras_data[0])
        obras_df.dropna(how='all', inplace=True)
        login_page(obras_df)
    except Exception as e:
        st.error(f"Não foi possível conectar à planilha para o login. Erro: {e}")
else:
    data_tuple = load_data_from_gsheets(sheet_url)
    if not all(df is not None for df in data_tuple):
        st.error("Falha ao carregar os dados completos após o login.")
        st.stop()
        
    funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_historico_df = data_tuple
    if 'lancamentos' not in st.session_state:
        st.session_state.lancamentos = lancamentos_historico_df.to_dict('records')

    # --- Sidebar ---
    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
        
        if st.button("Sair 🚪", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        st.subheader("Menu")
        
        if 'page' not in st.session_state:
            if st.session_state['role'] == 'admin':
                st.session_state.page = "Auditoria ✏️"
            else:
                st.session_state.page = "Lançamento Folha 📝"
        
        # Menu dinâmico baseado no perfil
        if st.session_state['role'] == 'user':
            if st.button("Lançamento Folha 📝", use_container_width=True):
                st.session_state.page = "Lançamento Folha 📝"
        else: # Admin
             if st.button("Auditoria ✏️", use_container_width=True):
                st.session_state.page = "Auditoria ✏️"

        if st.button("Resumo da Folha 📊", use_container_width=True):
            st.session_state.page = "Resumo da Folha 📊"
        if st.button("Editar Lançamentos ✏️", use_container_width=True):
            st.session_state.page = "Editar Lançamentos ✏️"
        if st.button("Dashboard de Análise 📈", use_container_width=True):
            st.session_state.page = "Dashboard de Análise 📈"

    # --- Renderização das Páginas ---
    if st.session_state.page == "Lançamento Folha 📝" and st.session_state['role'] == 'user':
        st.header("Adicionar Novo Lançamento de Produção")
        # (código da página de lançamento)
        pass # Placeholder for brevity

    elif st.session_state.page == "Resumo da Folha 📊":
        st.header(f"Resumo da Folha")
        # (código da página de resumo)
        pass # Placeholder for brevity

    elif st.session_state.page == "Editar Lançamentos ✏️":
        st.header(f"Gerenciar Lançamentos")
        # (código da página de edição)
        pass # Placeholder for brevity
    
    elif st.session_state.page == "Dashboard de Análise 📈":
        st.header(f"Dashboard de Análise")
        # (código da página de dashboard)
        pass # Placeholder for brevity

    elif st.session_state.page == "Auditoria ✏️" and st.session_state['role'] == 'admin':
        st.header("Auditoria de Lançamentos")
        
        lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
        
        st.info("Filtre para auditar lançamentos específicos.")
        filt_col1, filt_col2 = st.columns(2)
        
        obras_para_filtrar = sorted(lancamentos_df['Obra'].unique())
        obra_filtrada = filt_col1.multiselect("Filtrar por Obra", options=obras_para_filtrar)

        funcionarios_para_filtrar = sorted(lancamentos_df['Funcionário'].unique())
        funcionario_filtrado = filt_col2.multiselect("Filtrar por Funcionário", options=funcionarios_para_filtrar)

        df_filtrado = lancamentos_df.copy()
        if obra_filtrada:
            df_filtrado = df_filtrado[df_filtrado['Obra'].isin(obra_filtrada)]
        if funcionario_filtrado:
            df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]

        if df_filtrado.empty:
            st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
        else:
            funcionarios_na_lista = df_filtrado['Funcionário'].unique()
            for func in funcionarios_na_lista:
                lancamentos_do_func = df_filtrado[df_filtrado['Funcionário'] == func]
                total_produzido = lancamentos_do_func['Valor Parcial'].sum()
                
                with st.expander(f"Funcionário: **{func}** | Total Produzido: **{format_currency(total_produzido)}**"):
                    st.dataframe(lancamentos_do_func, use_container_width=True)



