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

def load_status_data(spreadsheet):
    try:
        ws_status = spreadsheet.worksheet("StatusAuditoria")
        status_data = ws_status.get_all_records()
        if not status_data:
            # Garante que todas as colunas existam mesmo se a planilha estiver vazia
            return pd.DataFrame(columns=['Obra', 'Funcionario', 'Status', 'Comentario'])
        df = pd.DataFrame(status_data)
        # Verifica se as colunas essenciais existem, se não, as cria em branco
        for col in ['Obra', 'Funcionario', 'Status', 'Comentario']:
            if col not in df.columns:
                df[col] = ''
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.warning("Aba 'StatusAuditoria' não encontrada. Crie uma aba com esse nome e as colunas: Obra, Funcionario, Status, Comentario.")
        return pd.DataFrame(columns=['Obra', 'Funcionario', 'Status', 'Comentario'])

def save_comment_data(status_df, obra, funcionario, comment, append=False):
    try:
        condition = (status_df['Obra'] == obra) & (status_df['Funcionario'] == funcionario)
        
        # Busca o comentário atual, se existir
        current_comment = ""
        if condition.any() and 'Comentario' in status_df.columns:
            # Garante que não estamos lendo um valor 'nan'
            comment_val = status_df.loc[condition, 'Comentario'].iloc[0]
            if pd.notna(comment_val):
                current_comment = str(comment_val)

        # Anexa o novo comentário ao antigo, se a flag 'append' for verdadeira
        final_comment = comment
        if append and current_comment.strip():
            timestamp = datetime.now().strftime("%d/%m/%Y")
            final_comment = f"{current_comment}\n---\n[REMOÇÃO - {timestamp}]: {comment}"
        elif append: # Caso de anexo, mas não há comentário anterior
            timestamp = datetime.now().strftime("%d/%m/%Y")
            final_comment = f"[REMOÇÃO - {timestamp}]: {comment}"

        if condition.any():
            status_df.loc[condition, 'Comentario'] = final_comment
        else:
            new_row = pd.DataFrame([{'Obra': obra, 'Funcionario': funcionario, 'Status': 'A Revisar', 'Comentario': final_comment}])
            status_df = pd.concat([status_df, new_row], ignore_index=True)
        
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(SHEET_URL)
        ws_status = spreadsheet.worksheet("StatusAuditoria")
        set_with_dataframe(ws_status, status_df, include_index=False, resize=True)
        st.toast(f"Comentário para '{funcionario}' salvo com sucesso!", icon="💬")
        st.cache_data.clear()
        return status_df
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar o comentário: {e}")
    return status_df

def save_aviso_data(obras_df, obra, aviso):
    try:
        obras_df.loc[obras_df['NOME DA OBRA'] == obra, 'Aviso'] = aviso
        
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(SHEET_URL)
        ws_obras = spreadsheet.worksheet("Obras")
        set_with_dataframe(ws_obras, obras_df, include_index=False, resize=True)
        st.toast(f"Aviso para a obra '{obra}' salvo com sucesso!", icon="📢")
        st.cache_data.clear()
        return obras_df
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar o aviso: {e}")
    return obras_df
    
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
def launch_monthly_sheet(obra, mes):
    try:
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(SHEET_URL)
        
        # 1. Ler todos os lançamentos ativos
        ws_lancamentos = spreadsheet.worksheet("Lançamentos")
        lancamentos_ativos = ws_lancamentos.get_all_records()
        df_lancamentos = pd.DataFrame(lancamentos_ativos)
        
        # Converte a coluna 'Data' para datetime para poder filtrar
        df_lancamentos['Data'] = pd.to_datetime(df_lancamentos['Data'])
        
        # 2. Identificar os lançamentos do mês e obra a serem arquivados
        mes_dt = pd.to_datetime(mes)
        filtro = (df_lancamentos['Obra'] == obra) & (df_lancamentos['Data'].dt.month == mes_dt.month) & (df_lancamentos['Data'].dt.year == mes_dt.year)
        
        df_para_arquivar = df_lancamentos[filtro]
        df_para_manter = df_lancamentos[~filtro]

        if not df_para_arquivar.empty:
            # 3. Adicionar os lançamentos ao histórico
            ws_historico = spreadsheet.worksheet("Histórico_Lançamentos")
            # Garante que as colunas estão na ordem correta antes de adicionar
            df_para_arquivar_ordenado = df_para_arquivar.reindex(columns=COLUNAS_LANCAMENTOS, fill_value='')
            ws_historico.append_rows(df_para_arquivar_ordenado.values.tolist(), value_input_option='USER_ENTERED')
            
            # 4. Reescrever a aba de Lançamentos apenas com os que devem ser mantidos
            df_para_manter_ordenado = df_para_manter.reindex(columns=COLUNAS_LANCAMENTOS, fill_value='')
            set_with_dataframe(ws_lancamentos, df_para_manter_ordenado, include_index=False, resize=True)

        # 5. Marcar a folha como "Lançada"
        ws_folhas = spreadsheet.worksheet("Folhas_Mensais")
        ws_folhas.append_row([obra, mes, "Lançada"], value_input_option='USER_ENTERED')
        
        st.toast(f"Folha de {mes} para a obra '{obra}' lançada e arquivada!", icon="🚀")
        st.cache_data.clear()
        st.rerun()
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao lançar a folha: {e}")
        return False
        
@st.cache_data(ttl=30)
def load_data_from_gsheets(url):
    try:
        gc = get_gsheets_connection()
        spreadsheet = gc.open_by_url(url)

        def clean_value(value_str):
            if isinstance(value_str, (int, float)): return value_str
            s = str(value_str).replace('R$', '').strip()
            if ',' in s: s = s.replace('.', '').replace(',', '.')
            return pd.to_numeric(s, errors='coerce')

        # Carrega Funcionários
        ws_func = spreadsheet.worksheet("Funcionários")
        func_data = ws_func.get_all_values()
        funcionarios_df = pd.DataFrame([row[1:6] for row in func_data[3:] if len(row) > 5 and row[1]], columns=['NOME', 'FUNÇÃO', 'TIPO', 'SALARIO_BASE', 'OBRA'])
        funcionarios_df.dropna(how='all', inplace=True)
        funcionarios_df['SALARIO_BASE'] = funcionarios_df['SALARIO_BASE'].apply(clean_value)
        funcionarios_df.dropna(subset=['NOME', 'FUNÇÃO'], inplace=True)

        # Carrega Preços
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
        
        # Carrega Extras
        ws_extras = spreadsheet.worksheet("Valores Extras")
        extras_data = ws_extras.get_all_records()
        valores_extras_df = pd.DataFrame(extras_data)
        if 'VALOR' in valores_extras_df.columns:
            valores_extras_df['VALOR'] = valores_extras_df['VALOR'].apply(clean_value)
        if 'VALORES EXTRAS' in valores_extras_df.columns and 'VALOR' in valores_extras_df.columns:
            valores_extras_df.dropna(subset=['VALORES EXTRAS', 'VALOR'], inplace=True)

        # Carrega Obras
        ws_obras = spreadsheet.worksheet("Obras")
        obras_data = ws_obras.get_all_values()
        obras_df = pd.DataFrame(obras_data[1:], columns=obras_data[0]) if len(obras_data) > 1 else pd.DataFrame(columns=['NOME DA OBRA', 'Status', 'Aviso'])
        obras_df.dropna(how='all', inplace=True)
        if 'Aviso' not in obras_df.columns:
            obras_df['Aviso'] = ''
        
        # Carrega Lançamentos
        ws_lancamentos = spreadsheet.worksheet("Lançamentos")
        lancamentos_data = ws_lancamentos.get_all_records()
        lancamentos_df = pd.DataFrame(lancamentos_data) if lancamentos_data else pd.DataFrame(columns=COLUNAS_LANCAMENTOS)
        for col in ['Quantidade', 'Valor Unitário', 'Valor Parcial']:
            if col in lancamentos_df.columns:
                lancamentos_df[col] = lancamentos_df[col].apply(clean_value).fillna(0)
        lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'], errors='coerce')
        lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'], errors='coerce')
        lancamentos_df.dropna(subset=['Data'], inplace=True)
        lancamentos_df.reset_index(inplace=True)
        lancamentos_df.rename(columns={'index': 'id_lancamento'}, inplace=True)
        
        # Carrega Status
        status_df = load_status_data(spreadsheet)
        
        # Carrega Funções
        try:
            ws_funcoes = spreadsheet.worksheet("Funções")
            funcoes_data = ws_funcoes.get_all_records()
            funcoes_df = pd.DataFrame(funcoes_data)
            funcoes_df['SALARIO_BASE'] = funcoes_df['SALARIO_BASE'].apply(clean_value)
        except gspread.exceptions.WorksheetNotFound:
            st.error("Aba 'Funções' não encontrada!")
            funcoes_df = pd.DataFrame()

        # --- INÍCIO DA CORREÇÃO ---
        # Carrega Folhas Mensais de forma mais segura
        try:
            ws_folhas = spreadsheet.worksheet("Folhas_Mensais")
            folhas_data = ws_folhas.get_all_records()
            folhas_df = pd.DataFrame(folhas_data)
            # Garante que as colunas essenciais existam, mesmo se a aba estiver vazia
            for col in ['Obra', 'Mes', 'Status']:
                if col not in folhas_df.columns:
                    folhas_df[col] = pd.NA
        except gspread.exceptions.WorksheetNotFound:
            st.error("Aba 'Folhas_Mensais' não encontrada! Crie-a com as colunas: Obra, Mes, Status.")
            folhas_df = pd.DataFrame(columns=['Obra', 'Mes', 'Status'])
        # --- FIM DA CORREÇÃO ---

        return funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_df, status_df, funcoes_df, folhas_df
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

def display_status_box(label, status):
    if status == 'Aprovado':
        st.success(f"{label}: {status}")
    elif status == 'Analisar':
        st.error(f"{label}: {status}")
    else:
        st.info(f"{label}: {status}")
        
def style_status(status):
    color = 'gray'
    if status == 'Aprovado':
        color = 'green'
    elif status == 'Analisar':
        color = 'red'
    return f'color: {color}; font-weight: bold;'

# FUNÇÃO DE LOGIN RESTAURADA
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
        
    funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_historico_df, status_df, funcoes_df, folhas_df = data_tuple
    
    if 'lancamentos' not in st.session_state or not st.session_state.lancamentos:
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
            display_status_box("Status da Obra", status_atual)

            aviso_obra = ""
            if 'Aviso' in obras_df.columns and not obras_df[obras_df['NOME DA OBRA'] == obra_logada].empty:
                aviso_obra = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'Aviso'].iloc[0]
            
            if aviso_obra and str(aviso_obra).strip():
                st.error(f"📢 Aviso: {aviso_obra}")
        
        st.markdown("---")
        
        st.subheader("Mês de Referência")
        lancamentos_df_sidebar = pd.DataFrame(st.session_state.lancamentos)
        
        available_months = []
        if not lancamentos_df_sidebar.empty and 'Data' in lancamentos_df_sidebar.columns:
            lancamentos_df_sidebar['Mes'] = pd.to_datetime(lancamentos_df_sidebar['Data']).dt.to_period('M')
            available_months = sorted(lancamentos_df_sidebar['Mes'].unique().astype(str))

        current_month_str = datetime.now().strftime('%Y-%m')
        if current_month_str not in available_months:
            available_months.append(current_month_str)

        if 'selected_month' not in st.session_state:
            st.session_state.selected_month = current_month_str

        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=available_months.index(st.session_state.selected_month if st.session_state.selected_month in available_months else current_month_str),
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
        
        st.markdown("---")
        st.subheader("Menu")
        if 'page' not in st.session_state:
            st.session_state.page = "Auditoria ✏️" if st.session_state['role'] == 'admin' else "Lançamento Folha 📝"
        
        if st.session_state['role'] == 'user':
            if st.button("Lançamento Folha 📝", use_container_width=True):
                st.session_state.page = "Lançamento Folha 📝"
        else:
            if st.button("Auditoria ✏️", use_container_width=True):
                st.session_state.page = "Auditoria ✏️"
            if st.button("Gerenciar Funcionários 👥", use_container_width=True):
                st.session_state.page = "Gerenciar Funcionários"
            if st.button("Gerenciar Obras 🏗️", use_container_width=True):
                st.session_state.page = "Gerenciar Obras"

        if st.button("Resumo da Folha 📊", use_container_width=True):
            st.session_state.page = "Resumo da Folha 📊"
        if st.button("Remover Lançamentos 🗑️", use_container_width=True):
            st.session_state.page = "Remover Lançamentos 🗑️"
        if st.button("Dashboard de Análise 📈", use_container_width=True):
            st.session_state.page = "Dashboard de Análise 📈"
        
        st.markdown("---")
        st.header("Ferramentas")
        st.subheader("Backup dos Dados")
        if st.button("📥 Baixar Backup em Excel", use_container_width=True):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(st.session_state.lancamentos).drop(columns=['id_lancamento'], errors='ignore').to_excel(writer, sheet_name='Lançamentos', index=False)
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

    # --- FILTRAGEM DE DADOS PELO MÊS SELECIONADO ---
    lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
    if not lancamentos_df.empty:
        mes_selecionado_dt = pd.to_datetime(st.session_state.selected_month)
        lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'])
        lancamentos_df = lancamentos_df[
            (lancamentos_df['Data'].dt.month == mes_selecionado_dt.month) &
            (lancamentos_df['Data'].dt.year == mes_selecionado_dt.year)
        ]

    # --- ESTRUTURA DE NAVEGAÇÃO (FORA DA SIDEBAR) ---
    if st.session_state.page == "Lançamento Folha 📝" and st.session_state['role'] == 'user':
        st.header("Adicionar Novo Lançamento de Produção")
        
        obra_logada = st.session_state['obra_logada']
        mes_selecionado = st.session_state.selected_month

        folha_lancada_row = folhas_df[(folhas_df['Obra'] == obra_logada) & (folhas_df['Mes'] == mes_selecionado)]
        is_launched = not folha_lancada_row.empty

        if is_launched:
            st.error(f" Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi lançada. Não é possível adicionar ou alterar lançamentos.")
        else:
            col_form, col_view = st.columns(2)
            with col_form:
                quantidades_extras = {}
                observacoes_extras = {}
                datas_servico_extras = {}
                
                st.markdown(f"##### 📍 Lançamento para a Obra: **{st.session_state['obra_logada']}**")
                with st.container(border=True):
                    obra_selecionada = st.session_state['obra_logada']
                    opcoes_funcionario = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique()
                    funcionario_selecionado = st.selectbox("Selecione o Funcionário", options=opcoes_funcionario, index=None, placeholder="Selecione um funcionário...")
                    if funcionario_selecionado:
                        funcao_selecionada = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'FUNÇÃO'].iloc[0]
                        st.metric(label="Função do Colaborador", value=funcao_selecionada)

                st.markdown("##### 🛠️ Selecione o Serviço Principal")
                with st.container(border=True):
                    disciplinas = precos_df['DISCIPLINA'].unique()
                    disciplina_selecionada = st.selectbox("Disciplina", options=disciplinas, index=None, placeholder="Selecione...")
                    opcoes_servico = []
                    if disciplina_selecionada:
                        opcoes_servico = precos_df[precos_df['DISCIPLINA'] == disciplina_selecionada]['DESCRIÇÃO DO SERVIÇO'].unique()
                    servico_selecionado = st.selectbox("Descrição do Serviço", options=opcoes_servico, index=None, placeholder="Selecione uma disciplina...", disabled=(not disciplina_selecionada))
                    
                    quantidade_principal = 0 
                    if servico_selecionado:
                        servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                        kpi1, kpi2 = st.columns(2)
                        kpi1.metric(label="Unidade", value=servico_info['UNIDADE'])
                        kpi2.metric(label="Valor Unitário", value=format_currency(servico_info['VALOR']))
                        
                        col_qtd, col_parcial = st.columns(2)
                        with col_qtd:
                            quantidade_principal = st.number_input("Quantidade", min_value=0, step=1, key="qty_principal")
                        with col_parcial:
                            valor_unitario = safe_float(servico_info.get('VALOR'))
                            valor_parcial_servico = quantidade_principal * valor_unitario
                            st.metric(label="Subtotal do Serviço", value=format_currency(valor_parcial_servico))
                        
                        col_data_princ, col_obs_princ = st.columns(2)
                        with col_data_princ:
                            data_servico_principal = st.date_input("Data do Serviço", value=None, key="data_principal", format="DD/MM/YYYY")
                        with col_obs_princ:
                            obs_principal = st.text_area("Observação (Obrigatório)", key="obs_principal")
                
                st.markdown("##### Adicione Itens Extras")
                with st.expander("📝 Lançar Item Diverso"):
                    descricao_diverso = st.text_input("Descrição do Item Diverso")
                    valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="valor_diverso")
                    quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="qty_diverso")
                    
                    col_data_div, col_obs_div = st.columns(2)
                    with col_data_div:
                        data_servico_diverso = st.date_input("Data do Serviço", value=None, key="data_diverso", format="DD/MM/YYYY")
                    with col_obs_div:
                        obs_diverso = st.text_area("Observação (Obrigatório)", key="obs_diverso")

                with st.expander("➕ Lançar Valores Extras"):
                    if valores_extras_df.empty:
                        st.info("Nenhum item na tabela de 'Valores Extras' da planilha.")
                    else:
                        extras_options = valores_extras_df['VALORES EXTRAS'].unique()
                        extras_selecionados = st.multiselect("Selecione", options=extras_options, key="valores_extras_multiselect", label_visibility="collapsed")
                        if extras_selecionados:
                            for extra in extras_selecionados:
                                extra_info = valores_extras_df[valores_extras_df['VALORES EXTRAS'] == extra].iloc[0]
                                st.markdown(f"--- \n **{extra}**")
                                kpi1, kpi2 = st.columns(2)
                                kpi1.metric(label="Unidade", value=extra_info['UNIDADE'])
                                kpi2.metric(label="Valor Unitário", value=format_currency(extra_info['VALOR']))
                                key_slug = re.sub(r'[^a-zA-Z0-9]', '', extra)
                                
                                col_qtd_extra, col_parcial_extra = st.columns(2)
                                with col_qtd_extra:
                                    quantidades_extras[extra] = st.number_input("Quantidade", min_value=0, step=1, key=f"qty_{key_slug}")
                                with col_parcial_extra:
                                    valor_unitario_extra = safe_float(extra_info.get('VALOR'))
                                    valor_parcial_extra_calc = quantidades_extras.get(extra, 0) * valor_unitario_extra
                                    st.metric(label="Subtotal do Extra", value=format_currency(valor_parcial_extra_calc))

                                col_data_extra, col_obs_extra = st.columns(2)
                                with col_data_extra:
                                    datas_servico_extras[extra] = st.date_input("Data do Serviço (Obrigatório)", value=None, key=f"data_{key_slug}", format="DD/MM/YYYY")
                                with col_obs_extra:
                                    observacoes_extras[extra] = st.text_area("Observação (Obrigatório)", key=f"obs_{key_slug}")

                if st.button("✅ Adicionar Lançamento", use_container_width=True, type="primary"):
                    if not funcionario_selecionado:
                        st.warning("Por favor, selecione um funcionário.")
                    else:
                        erros = []
                        if 'servico_selecionado' in locals() and servico_selecionado and quantidade_principal > 0:
                            if not obs_principal.strip():
                                erros.append(f"Para o Serviço Principal '{servico_selecionado}', o campo 'Observação' é obrigatório.")
                        if 'descricao_diverso' in locals() and descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                            if not obs_diverso.strip():
                                erros.append(f"Para o Item Diverso '{descricao_diverso}', o campo 'Observação' é obrigatório.")
                        if 'extras_selecionados' in locals() and extras_selecionados:
                            for extra in extras_selecionados:
                                if quantidades_extras.get(extra, 0) > 0:
                                    if not datas_servico_extras.get(extra):
                                        erros.append(f"Para o Item Extra '{extra}', a 'Data do Serviço' é obrigatória.")
                                    if not observacoes_extras.get(extra, "").strip():
                                        erros.append(f"Para o Item Extra '{extra}', a 'Observação' é obrigatória.")
                        
                        if erros:
                            for erro in erros:
                                st.warning(erro)
                        else:
                            novos_lancamentos_dicts = []
                            agora = datetime.now()
                            
                            if 'servico_selecionado' in locals() and servico_selecionado and quantidade_principal > 0:
                                valor_unitario = safe_float(servico_info.get('VALOR', 0))
                                novos_lancamentos_dicts.append({
                                    'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                                    'Disciplina': servico_info['DISCIPLINA'], 'Serviço': servico_selecionado,
                                    'Quantidade': quantidade_principal, 'Unidade': servico_info['UNIDADE'],
                                    'Valor Unitário': valor_unitario, 'Valor Parcial': quantidade_principal * valor_unitario,
                                    'Data do Serviço': data_servico_principal, 'Observação': obs_principal
                                })
                            if 'descricao_diverso' in locals() and descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                                novos_lancamentos_dicts.append({
                                    'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                                    'Disciplina': "Diverso", 'Serviço': descricao_diverso,
                                    'Quantidade': quantidade_diverso, 'Unidade': 'UN',
                                    'Valor Unitário': valor_diverso, 'Valor Parcial': quantidade_diverso * valor_diverso,
                                    'Data do Serviço': data_servico_diverso, 'Observação': obs_diverso
                                })
                            if 'extras_selecionados' in locals() and extras_selecionados:
                                for extra in extras_selecionados:
                                    qty = quantidades_extras.get(extra, 0)
                                    if qty > 0:
                                        extra_info = valores_extras_df[valores_extras_df['VALORES EXTRAS'] == extra].iloc[0]
                                        valor_unitario = safe_float(extra_info.get('VALOR', 0))
                                        novos_lancamentos_dicts.append({
                                            'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                                            'Disciplina': "Extras", 'Serviço': extra,
                                            'Quantidade': qty, 'Unidade': extra_info['UNIDADE'],
                                            'Valor Unitário': valor_unitario, 'Valor Parcial': qty * valor_unitario,
                                            'Data do Serviço': datas_servico_extras[extra], 'Observação': observacoes_extras[extra]
                                        })
                            
                            if not novos_lancamentos_dicts:
                                st.warning("Nenhum serviço ou item com quantidade maior que zero foi adicionado.")
                            else:
                                try:
                                    gc = get_gsheets_connection()
                                    ws_lancamentos = gc.open_by_url(SHEET_URL).worksheet("Lançamentos")
                                    
                                    df_novos = pd.DataFrame(novos_lancamentos_dicts)
                                    df_novos_ordenado = df_novos[COLUNAS_LANCAMENTOS].copy()

                                    df_novos_ordenado['Data'] = pd.to_datetime(df_novos_ordenado['Data']).dt.strftime('%Y-%m-%d %H:%m:%S')
                                    datas_formatadas = pd.to_datetime(df_novos_ordenado['Data do Serviço'], errors='coerce').dt.strftime('%Y-%m-%d')
                                    df_novos_ordenado['Data do Serviço'] = datas_formatadas.fillna('')
                                    
                                    for col in ['Valor Unitário', 'Valor Parcial', 'Quantidade']:
                                        if col in df_novos_ordenado.columns:
                                            df_novos_ordenado[col] = pd.to_numeric(df_novos_ordenado[col], errors='coerce').fillna(0)
                                            if col in ['Valor Unitário', 'Valor Parcial']:
                                                df_novos_ordenado[col] = df_novos_ordenado[col].apply(lambda x: f'{x:.2f}'.replace('.', ','))
                                            else:
                                                df_novos_ordenado[col] = df_novos_ordenado[col].astype(str)
                                    
                                    ws_lancamentos.append_rows(df_novos_ordenado.values.tolist(), value_input_option='USER_ENTERED')
                                    
                                    st.success("Lançamento(s) adicionado(s) com sucesso!")
                                    
                                    df_atual_historico = pd.DataFrame(st.session_state.lancamentos)
                                    df_atualizado = pd.concat([df_atual_historico, df_novos], ignore_index=True)
                                    st.session_state.lancamentos = df_atualizado.to_dict('records')
                                    
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Ocorreu um erro ao salvar na planilha: {e}")

            with col_view:
                if 'funcionario_selecionado' in locals() and funcionario_selecionado:
                    st.subheader("Status")
                    status_da_obra = status_df[status_df['Obra'] == obra_logada]
                    func_status_row = status_da_obra[status_da_obra['Funcionario'] == funcionario_selecionado]
                    
                    status_atual = 'A Revisar'
                    if not func_status_row.empty and 'Status' in func_status_row.columns:
                        status_atual = func_status_row['Status'].iloc[0]
                    display_status_box(f"Status de {funcionario_selecionado}", status_atual)
                    
                    comment = ""
                    st.markdown("---")
                    st.subheader("Comentário")
                    if not func_status_row.empty and 'Comentario' in func_status_row.columns:
                        comment = func_status_row['Comentario'].iloc[0]
                    if comment and str(comment).strip():
                        st.warning(f"Comentário: {comment}")
                    
                    st.markdown("---")

                st.subheader("Histórico Recente na Obra")
                lancamentos_recentes_df = pd.DataFrame(st.session_state.lancamentos)
                if not lancamentos_recentes_df.empty:
                    lancamentos_da_obra = lancamentos_recentes_df[lancamentos_recentes_df['Obra'] == st.session_state['obra_logada']]
                    colunas_display = ['Data', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Data do Serviço', 'Observação']
                    colunas_existentes = [col for col in colunas_display if col in lancamentos_da_obra.columns]
                    if 'Data' in lancamentos_da_obra.columns:
                        lancamentos_da_obra['Data'] = pd.to_datetime(lancamentos_da_obra['Data'])
                        st.dataframe(lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[colunas_existentes].style.format({'Valor Unitário': 'R$ {:,.2f}', 'Valor Parcial': 'R$ {:,.2f}'}), use_container_width=True)
                else:
                    st.info("Nenhum lançamento adicionado ainda.")
    

   
    elif st.session_state.page == "Gerenciar Funcionários" and st.session_state['role'] == 'admin':
        st.header("Gerenciar Funcionários 👥")
        st.subheader("Adicionar Novo Funcionário")
        with st.container(border=True):
            lista_funcoes = [""] + funcoes_df['FUNÇÃO'].dropna().unique().tolist()
            funcao_selecionada = st.selectbox(
                "1. Selecione a Função",
                options=lista_funcoes,
                index=0,
                help="A escolha da função preencherá o tipo e o salário automaticamente."
            )
            tipo = ""
            salario = 0.0
            if funcao_selecionada:
                info_funcao = funcoes_df[funcoes_df['FUNÇÃO'] == funcao_selecionada].iloc[0]
                tipo = info_funcao['TIPO']
                salario = info_funcao['SALARIO_BASE']
                col_tipo, col_salario = st.columns(2)
                col_tipo.text_input("Tipo de Contrato", value=tipo, disabled=True)
                col_salario.text_input("Salário Base", value=format_currency(salario), disabled=True)
            with st.form("add_funcionario_form", clear_on_submit=True):
                nome = st.text_input("2. Nome do Funcionário")
                obra = st.selectbox("3. Alocar na Obra", options=obras_df['NOME DA OBRA'].unique())
                submitted = st.form_submit_button("Adicionar Funcionário")
                if submitted:
                    if nome and funcao_selecionada and obra:
                        try:
                            gc = get_gsheets_connection()
                            ws_func = gc.open_by_url(SHEET_URL).worksheet("Funcionários")
                            nova_linha = ['', nome, funcao_selecionada, tipo, salario, obra]
                            ws_func.append_row(nova_linha)
                            st.success(f"Funcionário '{nome}' adicionado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
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
                        st.rerun()
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
    
    elif st.session_state.page == "Resumo da Folha 📊":
        st.header("Resumo da Folha")
        base_para_resumo = funcionarios_df.copy()
        if st.session_state['role'] == 'user':
            base_para_resumo = base_para_resumo[base_para_resumo['OBRA'] == st.session_state['obra_logada']]
            funcionarios_disponiveis = base_para_resumo['NOME'].unique()
            funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s) específico(s):", options=funcionarios_disponiveis, key="resumo_func_user")
            if funcionarios_filtrados:
                base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
        else: # Visão do Administrador
            filtro_col1, filtro_col2 = st.columns(2)
            with filtro_col1:
                obras_disponiveis = obras_df['NOME DA OBRA'].unique()
                obras_filtradas = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis, key="resumo_obras_admin")
                if obras_filtradas:
                    base_para_resumo = base_para_resumo[base_para_resumo['OBRA'].isin(obras_filtradas)]
            
            with filtro_col2:
                funcionarios_disponiveis = base_para_resumo['NOME'].unique()
                funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s):", options=funcionarios_disponiveis, key="resumo_func_admin")
                if funcionarios_filtrados:
                    base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
                    
       
        if base_para_resumo.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            # O 'lancamentos_df' JÁ VEM FILTRADO PELO MÊS SELECIONADO
            if not lancamentos_df.empty:
                producao_por_funcionario = lancamentos_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
                producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
                resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            else:
                resumo_df = base_para_resumo.copy()
                resumo_df['PRODUÇÃO (R$)'] = 0
        
            
        if 'Funcionário' in resumo_df.columns:
            resumo_df = resumo_df.drop(columns=['Funcionário'])
        
        resumo_com_status_df = pd.merge(
            resumo_df, 
            status_df, 
            left_on=['NOME', 'OBRA'], 
            right_on=['Funcionario', 'Obra'], 
            how='left'
        ).drop(columns=['Funcionario', 'Obra'])
        
        resumo_com_status_df['Status'] = resumo_com_status_df['Status'].fillna('A Revisar')

        resumo_com_status_df['PRODUÇÃO (R$)'] = resumo_com_status_df['PRODUÇÃO (R$)'].fillna(0)
        resumo_final_df = resumo_com_status_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
        resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(calcular_salario_final, axis=1)
        
        # --- INÍCIO DA CORREÇÃO ---
        # Reordena as colunas, colocando 'Status' no final
        colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)', 'Status']
        # --- FIM DA CORREÇÃO ---
        
        colunas_existentes = [col for col in colunas_finais if col in resumo_final_df.columns]
        resumo_final_df = resumo_final_df[colunas_existentes].reset_index(drop=True)
        
        st.dataframe(
            resumo_final_df.style.format({
                'SALÁRIO BASE (R$)': 'R$ {:,.2f}',
                'PRODUÇÃO (R$)': 'R$ {:,.2f}',
                'SALÁRIO A RECEBER (R$)': 'R$ {:,.2f}'
            }).applymap(style_status, subset=['Status']), # Aplica a função de cor na coluna 'Status'
            use_container_width=True
        )

    elif st.session_state.page == "Remover Lançamentos 🗑️":
        st.header("Gerenciar Lançamentos")
        
        df_para_editar = pd.DataFrame(st.session_state.lancamentos).copy()
        if st.session_state['role'] == 'user':
            if not df_para_editar.empty:
                df_para_editar = df_para_editar[df_para_editar['Obra'] == st.session_state['obra_logada']]
            
            funcionarios_para_filtrar = sorted(df_para_editar['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_user")
            if funcionario_filtrado:
                df_para_editar = df_para_editar[df_para_editar['Funcionário'].isin(funcionario_filtrado)]

        else: # Visão do Administrador
            filtro_col1, filtro_col2 = st.columns(2)
            with filtro_col1:
                obras_disponiveis = sorted(df_para_editar['Obra'].unique())
                obras_filtradas = st.multiselect("Filtrar por Obra(s):", options=obras_disponiveis, key="editar_obras_admin")
                if obras_filtradas:
                    df_para_editar = df_para_editar[df_para_editar['Obra'].isin(obras_filtradas)]
            
            with filtro_col2:
                funcionarios_para_filtrar = sorted(df_para_editar['Funcionário'].unique())
                funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_admin")
                if funcionario_filtrado:
                    df_para_editar = df_para_editar[df_para_editar['Funcionário'].isin(funcionario_filtrado)]
        
        df_filtrado = df_para_editar.copy()

        if df_para_editar.empty:
            st.info("Nenhum lançamento para editar.")
        else:
            funcionarios_para_filtrar = sorted(df_para_editar['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar)
            
            df_filtrado = df_para_editar.copy()
            if funcionario_filtrado:
                df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]

            if df_filtrado.empty:
                st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
            else:
                df_filtrado['Remover'] = False
                
                # --- INÍCIO DA CORREÇÃO 2: ADICIONAR COLUNA DISCIPLINA ---
                colunas_visiveis = [
                    'Remover', 'Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 
                    'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação', 
                    'Data do Serviço', 'id_lancamento'
                ]
                colunas_existentes = [col for col in colunas_visiveis if col in df_filtrado.columns]
                
                st.write("Marque as caixas dos lançamentos que deseja apagar e clique no botão de remoção.")
                
                df_modificado = st.data_editor(
                    df_filtrado[colunas_existentes],
                    hide_index=True,
                    column_config={
                        "Remover": st.column_config.CheckboxColumn(required=True),
                        "id_lancamento": None,
                        "Disciplina": st.column_config.TextColumn("Disciplina"),
                        "Valor Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Valor Parcial": st.column_config.NumberColumn(format="R$ %.2f")
                    },
                    disabled=df_filtrado.columns.drop(['Remover', 'id_lancamento'], errors='ignore')
                )
                
                linhas_para_remover = df_modificado[df_modificado['Remover']]
                
                if not linhas_para_remover.empty:
                    st.warning("Atenção! Você selecionou os seguintes lançamentos para remoção permanente:")
                    st.dataframe(linhas_para_remover.drop(columns=['Remover', 'id_lancamento'], errors='ignore'))
                    
                    razao_remocao = ""
                    # O campo de justificativa só aparece para o administrador
                    if st.session_state['role'] == 'admin':
                        razao_remocao = st.text_area("Justificativa para a remoção (obrigatório):", key="razao_remocao_admin")

                    confirmacao_remocao = st.checkbox("Sim, confirmo que desejo remover os itens selecionados.")
                    
                    # Condição para desabilitar o botão de remoção
                    is_disabled = not confirmacao_remocao
                    if st.session_state['role'] == 'admin':
                        is_disabled = not confirmacao_remocao or not razao_remocao.strip()

                    if st.button("Remover Itens Selecionados", disabled=is_disabled, type="primary"):
                        # Salva a justificativa como um comentário para cada funcionário afetado
                        if st.session_state['role'] == 'admin' and razao_remocao:
                            funcionarios_afetados = { (row['Obra'], row['Funcionário']) for _, row in linhas_para_remover.iterrows() }
                            
                            for obra, funcionario in funcionarios_afetados:
                                status_df = save_comment_data(status_df, obra, funcionario, razao_remocao, append=True)

                        # Lógica de remoção continua normalmente
                        ids_para_remover_local = linhas_para_remover['id_lancamento'].tolist()
                        df_original = pd.DataFrame(st.session_state.lancamentos)
                        df_atualizado = df_original[~df_original['id_lancamento'].isin(ids_para_remover_local)]
                        
                        try:
                            gc = get_gsheets_connection()
                            ws_lancamentos = gc.open_by_url(SHEET_URL).worksheet("Lançamentos")
                            set_with_dataframe(ws_lancamentos, df_atualizado.drop(columns=['id_lancamento'], errors='ignore'), include_index=False, resize=True)
                            st.session_state.lancamentos = df_atualizado.to_dict('records')
                            st.toast("Lançamentos removidos com sucesso!", icon="🗑️")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ocorreu um erro ao atualizar a planilha: {e}")
                            
    elif st.session_state.page == "Dashboard de Análise 📈":
        st.header("Dashboard de Análise")
        lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
        base_para_dash = lancamentos_df.copy()

        if st.session_state['role'] == 'user':
            st.header(f"Obra: {st.session_state['obra_logada']}")
            if not base_para_dash.empty:
                base_para_dash = base_para_dash[base_para_dash['Obra'] == st.session_state['obra_logada']]

        if base_para_dash.empty:
            st.info("Ainda não há lançamentos para analisar.")
        else:
            st.markdown("#### Filtros do Dashboard")
            col1, col2 = st.columns(2)
            data_inicio = col1.date_input("Data de Início", value=(datetime.now() - timedelta(days=30)).date())
            data_fim = col2.date_input("Data de Fim", value=datetime.now().date())
            
            data_inicio_ts = pd.to_datetime((datetime.now() - timedelta(days=30)).date())
            data_fim_ts = pd.to_datetime(datetime.now().date()) + timedelta(days=1)
            
            df_filtrado_dash = base_para_dash.copy()

            if st.session_state['role'] == 'admin':
                filtro_col1, filtro_col2 = st.columns(2)
                with filtro_col1:
                    data_inicio = st.date_input("Data de Início", value=(datetime.now() - timedelta(days=30)).date(), key="dash_data_inicio_admin")
                    data_inicio_ts = pd.to_datetime(data_inicio)
                with filtro_col2:
                    data_fim = st.date_input("Data de Fim", value=datetime.now().date(), key="dash_data_fim_admin")
                    data_fim_ts = pd.to_datetime(data_fim) + timedelta(days=1)

                df_filtrado_dash = base_para_dash[(base_para_dash['Data'] >= data_inicio_ts) & (base_para_dash['Data'] < data_fim_ts)]

                filtro_col3, filtro_col4 = st.columns(2)
                with filtro_col3:
                    obras_disponiveis = sorted(df_filtrado_dash['Obra'].unique())
                    obras_filtradas_dash = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis)
                    if obras_filtradas_dash:
                        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Obra'].isin(obras_filtradas_dash)]
                with filtro_col4:
                    funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
                    funcionarios_filtrados_dash = st.multiselect("Filtrar por Funcionário(s)", options=funcionarios_disponiveis)
                    if funcionarios_filtrados_dash:
                        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]
            
            else: # Visão do usuário normal
                col1, col2 = st.columns(2)
                data_inicio = col1.date_input("Data de Início", value=(datetime.now() - timedelta(days=30)).date())
                data_fim = col2.date_input("Data de Fim", value=datetime.now().date())
                data_inicio_ts = pd.to_datetime(data_inicio)
                data_fim_ts = pd.to_datetime(data_fim) + timedelta(days=1)
                df_filtrado_dash = base_para_dash[(base_para_dash['Data'] >= data_inicio_ts) & (base_para_dash['Data'] < data_fim_ts)]

                funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
                funcionarios_filtrados_dash = st.multiselect("Filtrar por Funcionário(s)", options=funcionarios_disponiveis)
                if funcionarios_filtrados_dash:
                    df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]
            
            if df_filtrado_dash.empty:
                st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
            else:
                st.markdown("---")
                
                # --- INÍCIO DA CORREÇÃO 1: VOLTA PARA O st.metric E AJUSTA TEXTO LONGO ---
                total_produzido = df_filtrado_dash['Valor Parcial'].sum()
                top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
                top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()

                # Encurta os nomes longos para exibição nos cards
                top_funcionario_display = (top_funcionario[:22] + '...') if len(top_funcionario) > 22 else top_funcionario
                top_servico_display = (top_servico[:22] + '...') if len(top_servico) > 22 else top_servico

                if st.session_state['role'] == 'admin':
                    kpi_cols = st.columns(4)
                    kpi_cols[0].metric("Produção Total", format_currency(total_produzido))
                    
                    top_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().idxmax()
                    kpi_cols[1].metric("Obra Destaque", top_obra)
                    
                    kpi_cols[2].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
                    kpi_cols[3].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)
                else: # Visão do usuário normal
                    kpi_cols = st.columns(3)
                    kpi_cols[0].metric("Produção Total", format_currency(total_produzido))
                    kpi_cols[1].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
                    kpi_cols[2].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)
                # --- FIM DA CORREÇÃO 1 ---

                st.markdown("---")

                # --- INÍCIO DA CORREÇÃO 2: PADRONIZAÇÃO DAS CORES DOS GRÁFICOS ---
                cor_padrao = '#E37026'

                if st.session_state['role'] == 'admin':
                    st.subheader("Produção por Obra")
                    prod_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                    fig_bar_obra = px.bar(prod_obra, x='Obra', y='Valor Parcial', text_auto=True, title="Produção Total por Obra")
                    fig_bar_obra.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                    st.plotly_chart(fig_bar_obra, use_container_width=True)
                
                st.subheader("Produção por Funcionário")
                prod_func = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                fig_bar_func = px.bar(prod_func, x='Funcionário', y='Valor Parcial', text_auto=True, title="Produção Total por Funcionário")
                fig_bar_func.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                st.plotly_chart(fig_bar_func, use_container_width=True)
                
                
                st.markdown("---")
                st.subheader("Produção ao Longo do Tempo")
                col_diag, col_mes = st.columns(2)
                with col_diag:
                    prod_dia = df_filtrado_dash.set_index('Data').resample('D')['Valor Parcial'].sum().reset_index()
                    fig_line = px.line(prod_dia, x='Data', y='Valor Parcial', markers=True, title="Evolução Diária da Produção")
                    fig_line.update_traces(line_color=cor_padrao, marker=dict(color=cor_padrao))
                    st.plotly_chart(fig_line, use_container_width=True)
                with col_mes:
                    prod_mes = df_filtrado_dash.set_index('Data').resample('ME')['Valor Parcial'].sum().reset_index()
                    prod_mes['Mês'] = prod_mes['Data'].dt.strftime('%Y-%m')
                    fig_bar_mes = px.bar(prod_mes, x='Mês', y='Valor Parcial', text_auto=True, title="Produção Total Mensal")
                    fig_bar_mes.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                    st.plotly_chart(fig_bar_mes, use_container_width=True)
            
                if st.session_state['role'] == 'admin':
                    st.markdown("---")
                    st.subheader("Análise de Serviços")
                    col_freq, col_custo = st.columns(2)

                    with col_freq:
                        serv_freq = df_filtrado_dash['Serviço'].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
                        serv_freq.columns = ['Serviço', 'Contagem']
                        fig_freq = px.bar(serv_freq, y='Serviço', x='Contagem', orientation='h', title="Top 10 Serviços Mais Realizados (Frequência)")
                        fig_freq.update_traces(marker_color=cor_padrao, texttemplate='%{x}', textposition='outside')
                        st.plotly_chart(fig_freq, use_container_width=True)

                    with col_custo:
                        serv_custo = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                        fig_custo = px.bar(serv_custo, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços de Maior Custo Total", text_auto=True)
                        fig_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                        st.plotly_chart(fig_custo, use_container_width=True)
                        
                    st.markdown("---")
                    st.subheader("Análise de Disciplinas")
                    col_disc_freq, col_disc_custo = st.columns(2)
                    with col_disc_freq:
                        disc_freq = df_filtrado_dash['Disciplina'].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
                        disc_freq.columns = ['Disciplina', 'Contagem']
                        fig_disc_freq = px.bar(disc_freq, y='Disciplina', x='Contagem', orientation='h', title="Top 10 Disciplinas Mais Realizadas")
                        fig_disc_freq.update_traces(marker_color=cor_padrao, texttemplate='%{x}', textposition='outside')
                        st.plotly_chart(fig_disc_freq, use_container_width=True)
                    with col_disc_custo:
                        disc_custo = df_filtrado_dash.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                        fig_disc_custo = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas de Maior Custo")
                        fig_disc_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                        st.plotly_chart(fig_disc_custo, use_container_width=True)

                
    elif st.session_state.page == "Auditoria ✏️" and st.session_state['role'] == 'admin':
        st.header(f"Auditoria de Lançamentos - {st.session_state.selected_month}")
        col_filtro1, col_filtro2 = st.columns(2)
        obras_disponiveis = sorted(lancamentos_df['Obra'].unique())
        obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra para auditar", options=obras_disponiveis, index=None, placeholder="Selecione uma obra...")
        
        funcionarios_filtrados = []
        if obra_selecionada:
            funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
            funcionarios_filtrados = col_filtro2.multiselect("2. Filtre por Funcionário (Opcional)", options=funcionarios_da_obra)
        
        if obra_selecionada:
            mes_selecionado = st.session_state.selected_month

            lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
            funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]

            status_geral_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == 'GERAL') & (status_df['Mes'] == mes_selecionado)]
            status_atual_obra = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"
            
            folha_lancada_row = folhas_df[(folhas_df['Obra'] == obra_selecionada) & (folhas_df['Mes'] == mes_selecionado)]
            is_launched = not folha_lancada_row.empty

            is_locked = (status_atual_obra == "Aprovado") or is_launched
            if is_launched:
                st.success(f"✅ A folha para {obra_selecionada} em {mes_selecionado} já foi lançada e arquivada. Nenhuma edição é permitida.")
            elif is_locked:
                st.warning(f"🔒 A obra {obra_selecionada} está com status 'Aprovado' para o mês {mes_selecionado}. As edições estão bloqueadas.")

            st.markdown("---")
            col_status_geral, col_aviso_geral = st.columns(2)

            with col_status_geral:
                st.markdown("##### Status e Finalização do Mês")
                display_status_box("Status Geral", status_atual_obra)
                
                with st.popover("Alterar Status", disabled=is_locked):
                    todos_aprovados = True
                    nomes_funcionarios_obra = funcionarios_obra_df['NOME'].unique()
                    if len(nomes_funcionarios_obra) > 0:
                        status_funcionarios_obra = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Mes'] == mes_selecionado)]
                        for nome in nomes_funcionarios_obra:
                            status_func_row = status_funcionarios_obra[status_funcionarios_obra['Funcionario'] == nome]
                            status_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else 'A Revisar'
                            if status_func != 'Aprovado':
                                todos_aprovados = False
                                break
                    status_options = ['A Revisar', 'Analisar']
                    if todos_aprovados:
                        status_options.append('Aprovado')
                    else:
                        st.info("Para aprovar a obra, todos os funcionários devem ter o status 'Aprovado'.")
                    idx = status_options.index(status_atual_obra) if status_atual_obra in status_options else 0
                    selected_status_obra = st.radio("Defina um novo status", options=status_options, index=idx, horizontal=True, key=f"radio_status_obra_{obra_selecionada}")
                    if st.button("Salvar Status da Obra", key=f"btn_obra_{obra_selecionada}"):
                        if selected_status_obra != status_atual_obra:
                            # Adicionar o parâmetro 'mes' ao salvar o status
                            status_df = save_status_data(status_df, obra_selecionada, 'GERAL', selected_status_obra, mes=mes_selecionado)
                            st.rerun()
                
                if st.button("🚀 Lançar Folha Mensal", disabled=(status_atual_obra != "Aprovado" or is_launched), help="Arquiva os lançamentos deste mês e os remove da lista de ativos. Esta ação não pode ser desfeita."):
                    launch_monthly_sheet(obra_selecionada, mes_selecionado)

            with col_aviso_geral:
                st.markdown("#####📢 Aviso Geral da Obra")
                aviso_atual = ""
                if 'Aviso' in obras_df.columns and not obras_df[obras_df['NOME DA OBRA'] == obra_selecionada].empty:
                    aviso_atual = obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'Aviso'].iloc[0]
                
                novo_aviso = st.text_area(
                    "Aviso para a Obra:", value=aviso_atual, key=f"aviso_{obra_selecionada}", label_visibility="collapsed"
                )
                if st.button("Salvar Aviso", key=f"btn_aviso_{obra_selecionada}", disabled=is_locked):
                    obras_df = save_aviso_data(obras_df, obra_selecionada, novo_aviso)
                    st.rerun()

            producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
            producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
            resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            if 'Funcionário' in resumo_df.columns:
                resumo_df = resumo_df.drop(columns=['Funcionário'])
            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            resumo_df = resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
            resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(calcular_salario_final, axis=1)

            st.markdown("---")
            st.subheader("Análise por Funcionário")
            
            if funcionarios_filtrados:
                resumo_df = resumo_df[resumo_df['Funcionário'].isin(funcionarios_filtrados)]

            if resumo_df.empty:
                st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
            else:
                for index, row in resumo_df.iterrows():
                    funcionario = row['Funcionário']
                    header_cols = st.columns([3, 2, 2, 2, 2])
                    header_cols[0].markdown(f"**Funcionário:** {row['Funcionário']} ({row['FUNÇÃO']})")
                    header_cols[1].metric("Salário Base", format_currency(row['SALÁRIO BASE (R$)']))
                    header_cols[2].metric("Produção", format_currency(row['PRODUÇÃO (R$)']))
                    header_cols[3].metric("Salário a Receber", format_currency(row['SALÁRIO A RECEBER (R$)']))

                    status_func_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario) & (status_df['Mes'] == mes_selecionado)]
                    status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    
                    with header_cols[4]:
                        display_status_box("Status", status_atual_func)

                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações", expanded=False):
                        col_status, col_comment = st.columns(2)
                        with col_status:
                            st.markdown("##### Status do Funcionário")
                            status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                            idx_func = status_options_func.index(status_atual_func)
                            selected_status_func = st.radio(
                                "Definir Status:", options=status_options_func, index=idx_func, horizontal=True, 
                                key=f"status_{obra_selecionada}_{funcionario}",
                                disabled=is_locked
                            )
                            if st.button("Salvar Status do Funcionário", key=f"btn_func_{obra_selecionada}_{funcionario}", disabled=is_locked):
                                if selected_status_func != status_atual_func:
                                    status_df = save_status_data(status_df, obra_selecionada, funcionario, selected_status_func, mes=mes_selecionado)
                                    st.rerun()
                        with col_comment:
                            st.markdown("##### Comentário de Auditoria")
                            comment_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario) & (status_df['Mes'] == mes_selecionado)]
                            current_comment = ""
                            if not comment_row.empty and 'Comentario' in comment_row.columns:
                                current_comment = str(comment_row['Comentario'].iloc[0])
                            new_comment = st.text_area(
                                "Adicionar/Editar Comentário:", value=current_comment, key=f"comment_{obra_selecionada}_{funcionario}",
                                help="Este comentário será visível na tela de lançamento.", label_visibility="collapsed",
                                disabled=is_locked
                            )
                            if st.button("Salvar Comentário", key=f"btn_comment_{obra_selecionada}_{funcionario}", disabled=is_locked):
                                status_df = save_comment_data(status_df, obra_selecionada, funcionario, new_comment, mes=mes_selecionado)
                                st.rerun()
                        st.markdown("---")
                        st.markdown("##### Lançamentos e Observações")
                        lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario].copy()
                        if lancamentos_do_funcionario.empty:
                            st.info("Nenhum lançamento de produção para este funcionário.")
                        else:
                            colunas_visiveis = [
                                'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 
                                'Valor Unitário', 'Valor Parcial', 'Observação', 'id_lancamento'
                            ]
                            colunas_config = {
                                "id_lancamento": None, "Data": st.column_config.DatetimeColumn("Data Lançamento", format="DD/MM/YYYY HH:mm"),
                                "Data do Serviço": st.column_config.DateColumn("Data Serviço", format="DD/MM/YYYY"),
                                "Disciplina": st.column_config.TextColumn("Disciplina"), "Serviço": st.column_config.TextColumn("Serviço", width="large"),
                                "Valor Unitário": st.column_config.NumberColumn("V. Unit.", format="R$ %.2f"),
                                "Valor Parcial": st.column_config.NumberColumn("V. Parcial", format="R$ %.2f"),
                                "Observação": st.column_config.TextColumn("Observação (Editável)", width="medium")
                            }
                            colunas_desabilitadas = ['Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial']
                            
                            edited_df = st.data_editor(
                                lancamentos_do_funcionario[colunas_visiveis], key=f"editor_{obra_selecionada}_{funcionario}",
                                hide_index=True, column_config=colunas_config,
                                disabled=colunas_desabilitadas if is_locked else ['Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial']
                            )
                            if not edited_df.equals(lancamentos_do_funcionario[colunas_visiveis]):
                                if st.button("Salvar Alterações nas Observações", key=f"save_obs_{obra_selecionada}_{funcionario}", type="primary", disabled=is_locked):
                                    try:
                                        lancamentos_df_global = pd.DataFrame(st.session_state.lancamentos)
                                        lancamentos_df_global.set_index('id_lancamento', inplace=True)
                                        edited_df.set_index('id_lancamento', inplace=True)
                                        lancamentos_df_global.update(edited_df[['Observação']])
                                        lancamentos_df_global.reset_index(inplace=True)
                                        gc = get_gsheets_connection()
                                        spreadsheet = gc.open_by_url(SHEET_URL)
                                        ws_lancamentos = spreadsheet.worksheet("Lançamentos")
                                        df_to_save = lancamentos_df_global.drop(columns=['id_lancamento'])
                                        set_with_dataframe(ws_lancamentos, df_to_save, include_index=False, resize=True)
                                        st.session_state.lancamentos = lancamentos_df_global.to_dict('records')
                                        st.toast("Observações salvas com sucesso!", icon="✅")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Ocorreu um erro ao salvar as observações: {e}")

































































