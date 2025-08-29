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
        
    # --- ESTRUTURA DE NAVEGAÇÃO CORRIGIDA ---
    if st.session_state.page == "Lançamento Folha 📝" and st.session_state['role'] == 'user':
        st.header("Adicionar Novo Lançamento de Produção")
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
                        data_servico_principal = st.date_input("Data do Serviço", value=datetime.now().date(), key="data_principal")
                    with col_obs_princ:
                        obs_principal = st.text_area("Observação", key="obs_principal")
            
            st.markdown("##### Adicione Itens Extras")
            with st.expander("📝 Lançar Item Diverso"):
                descricao_diverso = st.text_input("Descrição do Item Diverso")
                valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="valor_diverso")
                quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="qty_diverso")
                
                col_data_div, col_obs_div = st.columns(2)
                with col_data_div:
                    data_servico_diverso = st.date_input("Data do Serviço", value=datetime.now().date(), key="data_diverso")
                with col_obs_div:
                    obs_diverso = st.text_area("Observação", key="obs_diverso")

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
                                datas_servico_extras[extra] = st.date_input("Data do Serviço", value=datetime.now().date(), key=f"data_{key_slug}", help="Este campo é obrigatório")
                            with col_obs_extra:
                                observacoes_extras[extra] = st.text_area("Observação", key=f"obs_{key_slug}", placeholder="Obrigatório se houver quantidade")

            if st.button("✅ Adicionar Lançamento", use_container_width=True, type="primary"):
                if not funcionario_selecionado:
                    st.warning("Por favor, selecione um funcionário.")
                else:
                    lancamentos_para_salvar = []
                    agora = datetime.now()
                    
                    if 'servico_selecionado' in locals() and servico_selecionado and quantidade_principal > 0:
                        valor_unitario = safe_float(servico_info.get('VALOR', 0))
                        lancamentos_para_salvar.append({
                            'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                            'Disciplina': servico_info['DISCIPLINA'], 'Serviço': servico_selecionado,
                            'Quantidade': quantidade_principal, 'Unidade': servico_info['UNIDADE'],
                            'Valor Unitário': valor_unitario, 'Valor Parcial': quantidade_principal * valor_unitario,
                            'Data do Serviço': pd.to_datetime(data_servico_principal), 'Observação': obs_principal
                        })

                    if 'descricao_diverso' in locals() and descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                        lancamentos_para_salvar.append({
                            'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                            'Disciplina': "Diverso", 'Serviço': descricao_diverso,
                            'Quantidade': quantidade_diverso, 'Unidade': 'UN',
                            'Valor Unitário': valor_diverso, 'Valor Parcial': quantidade_diverso * valor_diverso,
                            'Data do Serviço': pd.to_datetime(data_servico_diverso), 'Observação': obs_diverso
                        })

                    if 'extras_selecionados' in locals() and extras_selecionados:
                        for extra, qty in quantidades_extras.items():
                            if qty > 0:
                                extra_info = valores_extras_df[valores_extras_df['VALORES EXTRAS'] == extra].iloc[0]
                                valor_unitario = safe_float(extra_info.get('VALOR', 0))
                                lancamentos_para_salvar.append({
                                    'Data': agora, 'Obra': obra_selecionada, 'Funcionário': funcionario_selecionado,
                                    'Disciplina': "Extras", 'Serviço': extra,
                                    'Quantidade': qty, 'Unidade': extra_info['UNIDADE'],
                                    'Valor Unitário': valor_unitario, 'Valor Parcial': qty * valor_unitario,
                                    'Data do Serviço': pd.to_datetime(datas_servico_extras[extra]), 'Observação': observacoes_extras[extra]
                                })
                    
                    if not lancamentos_para_salvar:
                        st.warning("Nenhum serviço ou item com quantidade maior que zero foi adicionado.")
                    else:
                        try:
                            gc = get_gsheets_connection()
                            ws_lancamentos = gc.open_by_url(SHEET_URL).worksheet("Lançamentos")
                            
                            linhas_formatadas = []
                            for item in lancamentos_para_salvar:
                                linha = [
                                    item['Data'].strftime('%Y-%m-%d %H:%M:%S'),
                                    item['Obra'],
                                    item['Funcionário'],
                                    item['Disciplina'],
                                    item['Serviço'],
                                    item['Quantidade'],
                                    item['Unidade'],
                                    item['Valor Unitário'],
                                    item['Valor Parcial'],
                                    item['Data do Serviço'].strftime('%Y-%m-%d'),
                                    item['Observação']
                                ]
                                linhas_formatadas.append(linha)
                            
                            ws_lancamentos.append_rows(linhas_formatadas, value_input_option='USER_ENTERED')
                            
                            st.success("Lançamento(s) adicionado(s) com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ocorreu um erro ao salvar na planilha: {e}")
        
        with col_view:
            if 'funcionario_selecionado' in locals() and funcionario_selecionado:
                st.subheader("Status da Auditoria")
                obra_logada = st.session_state['obra_logada']
                status_da_obra = status_df[status_df['Obra'] == obra_logada]
                func_status_row = status_da_obra[status_da_obra['Funcionario'] == funcionario_selecionado]
                status = func_status_row['Status'].iloc[0] if not func_status_row.empty else 'A Revisar'
                st.markdown(f"**{funcionario_selecionado}:** {get_status_color_html(status)}", unsafe_allow_html=True)
                st.markdown("---")

            st.subheader("Histórico Recente na Obra")
            lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
            if not lancamentos_df.empty:
                lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
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
            st.header(f"Obra: {st.session_state['obra_logada']}")
            base_para_resumo = base_para_resumo[base_para_resumo['OBRA'] == st.session_state['obra_logada']]
        else: 
            obras_disponiveis = obras_df['NOME DA OBRA'].unique()
            obras_filtradas = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis)
            if obras_filtradas:
                base_para_resumo = base_para_resumo[base_para_resumo['OBRA'].isin(obras_filtradas)]
        funcionarios_disponiveis = base_para_resumo['NOME'].unique()
        funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s) específico(s):", options=funcionarios_disponiveis)
        if funcionarios_filtrados:
            base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
        if base_para_resumo.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
            producao_por_funcionario = lancamentos_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
            producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
            resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            if 'Funcionário' in resumo_df.columns:
                resumo_df = resumo_df.drop(columns=['Funcionário'])
            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            resumo_final_df = resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
            resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(calcular_salario_final, axis=1)
            colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)']
            resumo_final_df = resumo_final_df[colunas_finais].reset_index(drop=True)
            st.dataframe(resumo_final_df.style.format(formatter={'SALÁRIO BASE (R$)': '{:,.2f}', 'PRODUÇÃO (R$)': '{:,.2f}', 'SALÁRIO A RECEBER (R$)': '{:,.2f}'}), use_container_width=True)

    elif st.session_state.page == "Editar Lançamentos ✏️":
        st.header("Gerenciar Lançamentos")
        lancamentos_df = pd.DataFrame(st.session_state.lancamentos).copy()
        if st.session_state['role'] == 'user':
            lancamentos_df = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
        if lancamentos_df.empty:
            st.info("Nenhum lançamento para editar.")
        else:
            funcionarios_para_filtrar = sorted(lancamentos_df['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar)
            df_filtrado = lancamentos_df.copy()
            if funcionario_filtrado:
                df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
            if df_filtrado.empty:
                st.warning("Nenhum lançamento encontrado.")
            else:
                df_filtrado['Remover'] = False
                colunas_visiveis = ['Remover', 'Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação', 'Data do Serviço', 'id_lancamento']
                colunas_existentes = [col for col in colunas_visiveis if col in df_filtrado.columns]
                st.write("Marque as caixas dos lançamentos que deseja apagar e clique no botão de remoção.")
                df_modificado = st.data_editor(
                    df_filtrado[colunas_existentes],
                    hide_index=True,
                    column_config={"Remover": st.column_config.CheckboxColumn(required=True), "id_lancamento": None},
                    disabled=df_filtrado.columns.drop(['Remover', 'id_lancamento'])
                )
                linhas_para_remover = df_modificado[df_modificado['Remover']]
                if not linhas_para_remover.empty:
                    st.warning("Atenção! Você selecionou os seguintes lançamentos para remoção permanente:")
                    st.dataframe(linhas_para_remover.drop(columns=['Remover', 'id_lancamento']))
                    confirmacao_remocao = st.checkbox("Sim, confirmo que desejo remover os itens selecionados.")
                    if st.button("Remover Itens Selecionados", disabled=(not confirmacao_remocao), type="primary"):
                        ids_para_remover_local = linhas_para_remover['id_lancamento'].tolist()
                        df_original = pd.DataFrame(st.session_state.lancamentos)
                        df_atualizado = df_original[~df_original['id_lancamento'].isin(ids_para_remover_local)]
                        try:
                            gc = get_gsheets_connection()
                            ws_lancamentos = gc.open_by_url(SHEET_URL).worksheet("Lançamentos")
                            set_with_dataframe(ws_lancamentos, df_atualizado.drop(columns=['id_lancamento']), include_index=False, resize=True)
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
            base_para_dash = base_para_dash[base_para_dash['Obra'] == st.session_state['obra_logada']]
        if base_para_dash.empty:
            st.info("Ainda não há lançamentos para analisar.")
        else:
            st.markdown("#### Filtros do Dashboard")
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
                kpi1, kpi2, kpi3 = st.columns(3)
                total_produzido = df_filtrado_dash['Valor Parcial'].sum()
                kpi1.metric("Produção Total", format_currency(total_produzido))
                top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
                kpi2.metric("Funcionário Destaque", top_funcionario)
                top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()
                kpi3.metric("Serviço de Maior Custo", top_servico)
                st.markdown("---")
                st.subheader("Produção por Funcionário")
                prod_func = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                fig_bar_func = px.bar(prod_func, x='Funcionário', y='Valor Parcial', text_auto=True, title="Produção Total por Funcionário")
                fig_bar_func.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color='#E37026')
                st.plotly_chart(fig_bar_func, use_container_width=True)
                col_diag, col_mes = st.columns(2)
                with col_diag:
                    st.subheader("Produção Diária")
                    prod_dia = df_filtrado_dash.set_index('Data').resample('D')['Valor Parcial'].sum().reset_index()
                    fig_line = px.line(prod_dia, x='Data', y='Valor Parcial', markers=True, title="Evolução Diária da Produção")
                    fig_line.update_traces(line_color='#E37026', marker=dict(color='#E37026'))
                    st.plotly_chart(fig_line, use_container_width=True)
                with col_mes:
                    st.subheader("Produção Mensal")
                    prod_mes = df_filtrado_dash.set_index('Data').resample('ME')['Valor Parcial'].sum().reset_index()
                    prod_mes['Mês'] = prod_mes['Data'].dt.strftime('%Y-%m')
                    fig_bar_mes = px.bar(prod_mes, x='Mês', y='Valor Parcial', text_auto=True, title="Produção Total Mensal")
                    fig_bar_mes.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color='#E37026')
                    st.plotly_chart(fig_bar_mes, use_container_width=True)

    elif st.session_state.page == "Auditoria ✏️" and st.session_state['role'] == 'admin':
        st.header("Auditoria de Lançamentos")
        lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
        col_filtro1, col_filtro2 = st.columns(2)
        obras_disponiveis = sorted(lancamentos_df['Obra'].unique())
        obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra para auditar", options=obras_disponiveis, index=None, placeholder="Selecione uma obra...")
        funcionarios_filtrados = []
        if obra_selecionada:
            funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
            funcionarios_filtrados = col_filtro2.multiselect("2. Filtre por Funcionário (Opcional)", options=funcionarios_da_obra)
        if obra_selecionada:
            st.markdown("---")
            col_status, col_total_obra = st.columns([1, 2])
            lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
            funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
            producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
            producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
            resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            if 'Funcionário' in resumo_df.columns:
                resumo_df = resumo_df.drop(columns=['Funcionário'])
            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            resumo_df = resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
            resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(calcular_salario_final, axis=1)
            with col_status:
                st.markdown("##### Status Geral da Obra")
                status_geral_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == 'GERAL')]
                status_atual_obra = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"
                st.markdown(get_status_color_html(status_atual_obra, font_size='1.2em'), unsafe_allow_html=True)
                with st.popover("Alterar Status"):
                    todos_aprovados = True
                    nomes_funcionarios_obra = funcionarios_obra_df['NOME'].unique()
                    if len(nomes_funcionarios_obra) > 0:
                        status_funcionarios_obra = status_df[status_df['Obra'] == obra_selecionada]
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
                            status_df = save_status_data(status_df, obra_selecionada, 'GERAL', selected_status_obra)
                            st.rerun()
            with col_total_obra:
                total_produzido_obra = resumo_df['PRODUÇÃO (R$)'].sum()
                st.metric("Total Produzido na Obra", format_currency(total_produzido_obra))
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
                    status_func_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario)]
                    status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    header_cols[4].markdown(f"**Status:** {get_status_color_html(status_atual_func, font_size='1em')}", unsafe_allow_html=True)
                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações", expanded=False):
                        st.markdown("##### Status do Funcionário")
                        status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                        idx_func = status_options_func.index(status_atual_func)
                        selected_status_func = st.radio("Definir Status:", options=status_options_func, index=idx_func, horizontal=True, key=f"status_{obra_selecionada}_{funcionario}")
                        if st.button("Salvar Status do Funcionário", key=f"btn_func_{obra_selecionada}_{funcionario}"):
                            if selected_status_func != status_atual_func:
                                status_df = save_status_data(status_df, obra_selecionada, funcionario, selected_status_func)
                                st.rerun()
                        st.markdown("---")
                        st.markdown("##### Lançamentos e Observações")
                        lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario].copy()
                        if lancamentos_do_funcionario.empty:
                            st.info("Nenhum lançamento de produção para este funcionário.")
                        else:
                            colunas_para_editar = {"id_lancamento": None, "Observação": st.column_config.TextColumn("Observação (Editável)", width="large")}
                            colunas_visiveis = ['Data', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação', 'id_lancamento']
                            edited_df = st.data_editor(
                                lancamentos_do_funcionario[colunas_visiveis],
                                key=f"editor_{obra_selecionada}_{funcionario}",
                                hide_index=True,
                                column_config=colunas_para_editar,
                                disabled=['Data', 'Serviço', 'Quantidade', 'Valor Parcial']
                            )
                            if not edited_df.equals(lancamentos_do_funcionario[colunas_visiveis]):
                                if st.button("Salvar Alterações nas Observações", key=f"save_obs_{obra_selecionada}_{funcionario}", type="primary"):
                                    try:
                                        lancamentos_df.set_index('id_lancamento', inplace=True)
                                        edited_df.set_index('id_lancamento', inplace=True)
                                        lancamentos_df.update(edited_df[['Observação']])
                                        lancamentos_df.reset_index(inplace=True)
                                        gc = get_gsheets_connection()
                                        spreadsheet = gc.open_by_url(SHEET_URL)
                                        ws_lancamentos = spreadsheet.worksheet("Lançamentos")
                                        df_to_save = lancamentos_df.drop(columns=['id_lancamento'])
                                        set_with_dataframe(ws_lancamentos, df_to_save, include_index=False, resize=True)
                                        st.session_state.lancamentos = lancamentos_df.to_dict('records')
                                        st.toast("Observações salvas com sucesso!", icon="✅")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Ocorreu um erro ao salvar as observações: {e}")






