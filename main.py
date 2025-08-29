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

st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1l5ChC0yrgiscqKBQB3rIEqA62nP97sLKZ_dAwiiVwiI/edit?usp=sharing"
COLUNAS_LANCAMENTOS = ['Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Data do Serviço', 'Observação']

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

# Função para carregar os status de auditoria
def load_status_data(spreadsheet):
    try:
        ws_status = spreadsheet.worksheet("StatusAuditoria")
        status_data = ws_status.get_all_records()
        if not status_data:
            return pd.DataFrame(columns=['Obra', 'Funcionario', 'Status'])
        
        df = pd.DataFrame(status_data)
        for col in ['Obra', 'Funcionario', 'Status']:
            if col not in df.columns:
                df[col] = np.nan
        return df

    except gspread.exceptions.WorksheetNotFound:
        st.warning("Aba 'StatusAuditoria' não encontrada. Para salvar o status das auditorias, crie uma aba com esse nome e as colunas: Obra, Funcionario, Status.")
        return pd.DataFrame(columns=['Obra', 'Funcionario', 'Status'])

# Função para salvar os status de auditoria
def save_status_data(status_df, obra, funcionario, status):
    try:
        condition = (status_df['Obra'] == obra) & (status_df['Funcionario'] == funcionario)
        
        if condition.any():
            status_df.loc[condition, 'Status'] = status
        else:
            new_row = pd.DataFrame([{'Obra': obra, 'Funcionario': funcionario, 'Status': status}])
            status_df = pd.concat([status_df, new_row], ignore_index=True)
        
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(SHEET_URL)
        ws_status = spreadsheet.worksheet("StatusAuditoria")
        set_with_dataframe(ws_status, status_df, include_index=False, resize=True)
        st.toast(f"Status de '{funcionario}' atualizado para '{status}'", icon="💾")
        st.cache_data.clear()
        return status_df

    except gspread.exceptions.WorksheetNotFound:
        pass 
    except Exception as e:
        st.error(f"Erro ao salvar o status: {e}")
    return status_df


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
        if len(lancamentos_data) > 1:
            data_rows = [row[:len(COLUNAS_LANCAMENTOS)] for row in lancamentos_data[1:]]
            lancamentos_df = pd.DataFrame(data_rows, columns=COLUNAS_LANCAMENTOS)
        else:
            lancamentos_df = pd.DataFrame(columns=COLUNAS_LANCAMENTOS)
        
        for col in ['Quantidade', 'Valor Unitário', 'Valor Parcial']:
            if col in lancamentos_df.columns:
                lancamentos_df[col] = pd.to_numeric(lancamentos_df[col], errors='coerce')
        
        lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'], errors='coerce')
        lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'], errors='coerce')
        lancamentos_df.dropna(subset=['Data'], inplace=True)
        lancamentos_df.reset_index(inplace=True)
        lancamentos_df.rename(columns={'index': 'id_lancamento'}, inplace=True)
        
        status_df = load_status_data(spreadsheet)
        
        # Carrega a nova tabela de Funções
        try:
            ws_funcoes = spreadsheet.worksheet("Funções")
            funcoes_data = ws_funcoes.get_all_records()
            funcoes_df = pd.DataFrame(funcoes_data)
            funcoes_df['SALARIO_BASE'] = funcoes_df['SALARIO_BASE'].apply(clean_value)
        except gspread.exceptions.WorksheetNotFound:
            st.error("Aba 'Funções' não encontrada! Crie esta aba na planilha para poder adicionar funcionários.")
            funcoes_df = pd.DataFrame(columns=['FUNÇÃO', 'TIPO', 'SALARIO_BASE'])

        return funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_df, status_df, funcoes_df

    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Aba da planilha não encontrada: '{e}'. Verifique o nome.")
        st.stop()
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar os dados da planilha: {e}")
        st.stop()

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

def get_status_color_html(status, font_size='1.1em'):
    color = 'gray'
    if status == 'Aprovado':
        color = 'green'
    elif status == 'Analisar':
        color = 'red'
    
    return f'<span style="color:{color}; font-weight:bold; font-size:{font_size};">● {status}</span>'

def login_page(obras_df):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Lavie.png", width=1000) 
    
    st.header("Login")
    
    admin_login = st.checkbox("Entrar como Administrador")

    if admin_login:
        admin_password = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar como Admin", use_container_width=True, type="primary"):
            if 'admin' in st.secrets and st.secrets.admin.password == admin_password:
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

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    try:
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(SHEET_URL)
        ws_obras = spreadsheet.worksheet("Obras")
        obras_data = ws_obras.get_all_values()
        obras_df = pd.DataFrame(obras_data[1:], columns=obras_data[0])
        obras_df.dropna(how='all', inplace=True)
        login_page(obras_df)
    except Exception as e:
        st.error(f"Não foi possível conectar à planilha para o login. Erro: {e}")
else:
    data_tuple = load_data_from_gsheets(SHEET_URL)
    if not all(df is not None for df in data_tuple):
        st.error("Falha ao carregar os dados completos após o login.")
        st.stop()
        
    funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_historico_df, status_df, funcoes_df = data_tuple
    if 'lancamentos' not in st.session_state:
        st.session_state.lancamentos = lancamentos_historico_df.to_dict('records')

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obra_logada = st.session_state['obra_logada']
            
            status_geral_obra_row = status_df[(status_df['Obra'] == obra_logada) & (status_df['Funcionario'] == 'GERAL')]
            status_atual = 'A Revisar'
            if not status_geral_obra_row.empty:
                status_atual = status_geral_obra_row['Status'].iloc[0]
            st.markdown(f"Status da Obra: {get_status_color_html(status_atual, font_size='1em')}", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Menu")
        
        if 'page' not in st.session_state:
            if st.session_state['role'] == 'admin':
                st.session_state.page = "Auditoria ✏️"
            else:
                st.session_state.page = "Lançamento Folha 📝"
        
        if st.session_state['role'] == 'user':
            if st.button("Lançamento Folha 📝", use_container_width=True):
                st.session_state.page = "Lançamento Folha 📝"
        else: # Menu do Administrador
            if st.button("Auditoria ✏️", use_container_width=True):
                st.session_state.page = "Auditoria ✏️"
            if st.button("Gerenciar Funcionários 👥", use_container_width=True):
                st.session_state.page = "Gerenciar Funcionários"
            if st.button("Gerenciar Obras 🏗️", use_container_width=True):
                st.session_state.page = "Gerenciar Obras"

        if st.button("Resumo da Folha 📊", use_container_width=True):
            st.session_state.page = "Resumo da Folha 📊"
        if st.button("Editar Lançamentos ✏️", use_container_width=True):
            st.session_state.page = "Editar Lançamentos ✏️"
        if st.button("Dashboard de Análise 📈", use_container_width=True):
            st.session_state.page = "Dashboard de Análise 📈"
        
        st.markdown("---")
        st.header("Ferramentas")
        st.subheader("Backup dos Dados")
        if st.button("📥 Baixar Backup em Excel", use_container_width=True):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(st.session_state.lancamentos).to_excel(writer, sheet_name='Lançamentos', index=False)
                funcionarios_df.to_excel(writer, sheet_name='Funcionários', index=False)
                precos_df.to_excel(writer, sheet_name='Tabela de Preços', index=False)
                valores_extras_df.to_excel(writer, sheet_name='Valores Extras', index=False)
                obras_df.to_excel(writer, sheet_name='Obras', index=False)
            
            st.download_button(
                label="Clique para baixar o backup",
                data=output.getvalue(),
                file_name=f"backup_producao_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
    if st.session_state.page == "Lançamento Folha 📝" and st.session_state['role'] == 'user':
        # ... (código da página de Lançamento Folha permanece o mesmo)
        pass

    elif st.session_state.page == "Gerenciar Funcionários" and st.session_state['role'] == 'admin':
        st.header("Gerenciar Funcionários 👥")

        st.subheader("Adicionar Novo Funcionário")
        with st.form("add_funcionario", clear_on_submit=True):
            nome = st.text_input("Nome do Funcionário")
            
            # Seleção de Função que preenche o resto
            lista_funcoes = [""] + funcoes_df['FUNÇÃO'].dropna().unique().tolist()
            funcao = st.selectbox("Função", options=lista_funcoes, index=0)
            
            tipo = ""
            salario = 0.0
            
            if funcao:
                info_funcao = funcoes_df[funcoes_df['FUNÇÃO'] == funcao].iloc[0]
                tipo = info_funcao['TIPO']
                salario = info_funcao['SALARIO_BASE']
                
                col_tipo, col_salario = st.columns(2)
                col_tipo.text_input("Tipo de Contrato", value=tipo, disabled=True)
                col_salario.text_input("Salário Base", value=format_currency(salario), disabled=True)
            
            obra = st.selectbox("Alocar na Obra", options=obras_df['NOME DA OBRA'].unique())
            
            submitted = st.form_submit_button("Adicionar Funcionário")
            if submitted:
                if nome and funcao and obra:
                    try:
                        gc = get_gsheets_connection()
                        ws_func = gc.open_by_url(SHEET_URL).worksheet("Funcionários")
                        nova_linha = ['', nome, funcao, tipo, salario, obra]
                        ws_func.append_row(nova_linha)
                        st.success(f"Funcionário '{nome}' adicionado com sucesso!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao adicionar o funcionário: {e}")
                else:
                    st.warning("Por favor, preencha nome, função e obra.")

        st.markdown("---")

        st.subheader("Remover Funcionário Existente")
        if funcionarios_df.empty:
            st.info("Nenhum funcionário cadastrado.")
        else:
            st.dataframe(funcionarios_df[['NOME', 'FUNÇÃO', 'OBRA']], use_container_width=True)
            func_para_remover = st.selectbox("Selecione o funcionário para remover", options=funcionarios_df['NOME'].unique(), index=None, placeholder="Selecione...")
            
            if func_para_remover:
                if st.button(f"Remover {func_para_remover}", type="primary"):
                    try:
                        gc = get_gsheets_connection()
                        ws_func = gc.open_by_url(SHEET_URL).worksheet("Funcionários")
                        cell = ws_func.find(func_para_remover, in_column=2) 
                        if cell:
                            ws_func.delete_rows(cell.row)
                            st.success(f"Funcionário '{func_para_remover}' removido com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Funcionário não encontrado na planilha.")
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao remover o funcionário: {e}")

    elif st.session_state.page == "Gerenciar Obras" and st.session_state['role'] == 'admin':
        st.header("Gerenciar Obras 🏗️")

        st.subheader("Adicionar Nova Obra")
        with st.form("add_obra", clear_on_submit=True):
            nome_obra = st.text_input("Nome da Nova Obra")
            submitted = st.form_submit_button("Adicionar Obra")
            if submitted:
                if nome_obra:
                    try:
                        gc = get_gsheets_connection()
                        ws_obras = gc.open_by_url(SHEET_URL).worksheet("Obras")
                        ws_obras.append_row([nome_obra])
                        st.success(f"Obra '{nome_obra}' adicionada com sucesso!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao adicionar a obra: {e}")
                else:
                    st.warning("Por favor, insira o nome da obra.")

        st.markdown("---")
        st.subheader("Remover Obra Existente")
        if obras_df.empty:
            st.info("Nenhuma obra cadastrada.")
        else:
            st.dataframe(obras_df, use_container_width=True)
            obra_para_remover = st.selectbox("Selecione a obra para remover", options=obras_df['NOME DA OBRA'].unique(), index=None, placeholder="Selecione...")
            
            if obra_para_remover:
                st.warning(f"Atenção: Remover uma obra não remove ou realoca os funcionários associados a ela. Certifique-se de que nenhum funcionário esteja alocado em '{obra_para_remover}' antes de continuar.")
                if st.button(f"Remover Obra '{obra_para_remover}'", type="primary"):
                    try:
                        gc = get_gsheets_connection()
                        ws_obras = gc.open_by_url(SHEET_URL).worksheet("Obras")
                        cell = ws_obras.find(obra_para_remover)
                        if cell:
                            ws_obras.delete_rows(cell.row)
                            st.success(f"Obra '{obra_para_remover}' removida com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Obra não encontrada na planilha.")
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao remover a obra: {e}")
    
    # O restante das páginas permanece igual
    elif st.session_state.page == "Resumo da Folha 📊":
        # ... (código existente)
        pass

    elif st.session_state.page == "Editar Lançamentos ✏️":
        # ... (código existente)
        pass

    elif st.session_state.page == "Dashboard de Análise 📈":
        # ... (código existente)
        pass

    elif st.session_state.page == "Auditoria ✏️" and st.session_state['role'] == 'admin':
        # ... (código existente)
        pass
