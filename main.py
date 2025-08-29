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
    page_title="App de Produção",
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
        st.image("Lavie.png", width=1000) 
    
    st.header("Login por Obra")
    
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

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
        
        st.markdown("---")
        st.subheader("Menu")
        
        if 'page' not in st.session_state:
            st.session_state.page = "Lançamento Folha 📝"

        if st.button("Lançamento Folha 📝", use_container_width=True):
            st.session_state.page = "Lançamento Folha 📝"
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
            del st.session_state['logged_in']
            del st.session_state['obra_logada']
            if 'page' in st.session_state:
                del st.session_state['page']
            st.rerun()
            
    if st.session_state.page == "Lançamento Folha 📝":
        st.header("Adicionar Novo Lançamento de Produção")
        col_form, col_view = st.columns(2)

        with col_form:
            # Inicialização das variáveis para evitar NameError
            quantidades_extras = {}
            observacoes_extras = {}
            datas_servico_extras = {}
            descricao_diverso = ""
            valor_diverso = 0.0
            quantidade_diverso = 0
            obs_diverso = ""
            data_servico_diverso = None
            quantidade = 0
            servico_info = None
            obs_principal = ""
            data_servico_principal = None
            
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
                if servico_selecionado:
                    servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                    kpi1, kpi2 = st.columns(2)
                    kpi1.metric(label="Unidade", value=servico_info['UNIDADE'])
                    kpi2.metric(label="Valor Unitário", value=format_currency(servico_info['VALOR']))
                    col_qtd, col_parcial = st.columns(2)
                    with col_qtd:
                        quantidade = st.number_input("Quantidade", min_value=0, step=1, key="qty_principal")
                    with col_parcial:
                        valor_unitario = safe_float(servico_info.get('VALOR'))
                        valor_parcial_servico = quantidade * valor_unitario
                        st.metric(label="Subtotal do Serviço", value=format_currency(valor_parcial_servico))
                    
                    col_data_princ, col_obs_princ = st.columns(2)
                    with col_data_princ:
                        data_servico_principal = st.date_input("Data do Serviço", value=None, key="data_principal")
                    with col_obs_princ:
                        obs_principal = st.text_area("Observação", key="obs_principal")
            
            st.markdown("##### Adicione Itens Extras")
            with st.expander("📝 Lançar Item Diverso"):
                descricao_diverso = st.text_input("Descrição do Item Diverso")
                valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=0.01, format="%.2f", key="valor_diverso")
                quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="qty_diverso")
                col_data_div, col_obs_div = st.columns(2)
                with col_data_div:
                    data_servico_diverso = st.date_input("Data do Serviço", value=None, key="data_diverso")
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
                            col_qtd, col_parcial = st.columns(2)
                            key_slug = re.sub(r'[^a-zA-Z0-9]', '', extra)
                            with col_qtd:
                                qty_extra = st.number_input("Quantidade", min_value=0, step=1, key=f"qty_{key_slug}")
                            with col_parcial:
                                valor_unitario = safe_float(extra_info.get('VALOR'))
                                valor_parcial_extra = qty_extra * valor_unitario
                                st.metric(label="Subtotal do Extra", value=format_currency(valor_parcial_extra))
                            
                            col_data_extra, col_obs_extra = st.columns(2)
                            with col_data_extra:
                                datas_servico_extras[extra] = st.date_input("Data do Serviço", value=None, key=f"data_{key_slug}", help="Este campo é obrigatório")
                            with col_obs_extra:
                                observacoes_extras[extra] = st.text_area("Observação", key=f"obs_{key_slug}")
                            quantidades_extras[extra] = qty_extra

            with st.form("lancamento_form"):
                submitted = st.form_submit_button("✅ Adicionar Lançamento", use_container_width=True)
                if submitted:
                    erro_validacao = False
                    if quantidade > 0 and (not obs_principal or not obs_principal.strip()):
                        st.error("Erro no Serviço Principal: A observação é obrigatória.")
                        erro_validacao = True
                    if quantidade_diverso > 0 and (not obs_diverso or not obs_diverso.strip()):
                        st.error("Erro no Item Diverso: A observação é obrigatória.")
                        erro_validacao = True
                    for extra, qty in quantidades_extras.items():
                        if qty > 0:
                            if not observacoes_extras.get(extra) or not observacoes_extras.get(extra).strip():
                                st.error(f"Erro em '{extra}': A observação é obrigatória.")
                                erro_validacao = True
                            if not datas_servico_extras.get(extra):
                                st.error(f"Erro em '{extra}': A data de realização é obrigatória.")
                                erro_validacao = True
                    
                    if not erro_validacao:
                        if not all([obra_selecionada, funcionario_selecionado]):
                            st.warning("Selecione o Funcionário.")
                        elif quantidade == 0 and not any(q > 0 for q in quantidades_extras.values()) and quantidade_diverso == 0:
                            st.warning("Adicione uma quantidade para o serviço principal, um valor extra ou um item diverso.")
                        else:
                            gc = get_gsheets_connection()
                            ws_lancamentos = gc.open_by_url(SHEET_URL).worksheet("Lançamentos")
                            
                            def prepare_row_for_gsheet(data_dict):
                                ordered_values = [data_dict.get(col, '') for col in COLUNAS_LANCAMENTOS]
                                for i, v in enumerate(ordered_values):
                                    if isinstance(v, (datetime, pd.Timestamp, pd.core.indexes.datetimes.DatetimeIndex, type(pd.to_datetime('today').date()))):
                                        ordered_values[i] = v.strftime("%Y-%m-%d") if i == 9 else v.strftime("%Y-%m-%d %H:%M:%S")
                                return [str(val) for val in ordered_values]

                            if quantidade > 0 and servico_selecionado:
                                valor_calculado = quantidade * safe_float(servico_info['VALOR'])
                                novo_lancamento = {"Data": datetime.now(), "Obra": obra_selecionada, "Funcionário": funcionario_selecionado, "Disciplina": disciplina_selecionada, "Serviço": servico_selecionado, "Quantidade": quantidade, "Unidade": servico_info['UNIDADE'], "Valor Unitário": servico_info['VALOR'], "Valor Parcial": valor_calculado, "Data do Serviço": data_servico_principal, "Observação": obs_principal}
                                ws_lancamentos.append_row(prepare_row_for_gsheet(novo_lancamento), value_input_option='USER_ENTERED')
                                st.session_state.lancamentos.append(novo_lancamento)
                            for extra, qty_extra_val in quantidades_extras.items():
                                if qty_extra_val > 0:
                                    extra_info = valores_extras_df[valores_extras_df['VALORES EXTRAS'] == extra].iloc[0]
                                    valor_calculado_extra = qty_extra_val * safe_float(extra_info['VALOR'])
                                    novo_extra = {"Data": datetime.now(), "Obra": obra_selecionada, "Funcionário": funcionario_selecionado, "Disciplina": "VALOR EXTRA", "Serviço": extra, "Quantidade": qty_extra_val, "Unidade": extra_info['UNIDADE'], "Valor Unitário": extra_info['VALOR'], "Valor Parcial": valor_calculado_extra, "Data do Serviço": datas_servico_extras[extra], "Observação": observacoes_extras[extra]}
                                    ws_lancamentos.append_row(prepare_row_for_gsheet(novo_extra), value_input_option='USER_ENTERED')
                                    st.session_state.lancamentos.append(novo_extra)
                            if descricao_diverso and valor_diverso > 0 and quantidade_diverso > 0:
                                valor_calculado_diverso = quantidade_diverso * valor_diverso
                                novo_diverso = {"Data": datetime.now(), "Obra": obra_selecionada, "Funcionário": funcionario_selecionado, "Disciplina": "DIVERSOS", "Serviço": descricao_diverso, "Quantidade": quantidade_diverso, "Unidade": "UN", "Valor Unitário": valor_diverso, "Valor Parcial": valor_calculado_diverso, "Data do Serviço": data_servico_diverso, "Observação": obs_diverso}
                                ws_lancamentos.append_row(prepare_row_for_gsheet(novo_diverso), value_input_option='USER_ENTERED')
                                st.session_state.lancamentos.append(novo_diverso)
                            
                            if not erro_validacao:
                                st.toast(f"Lançamento para **{funcionario_selecionado}** salvo!", icon="✅")
                                st.rerun()
        
        with col_view:
            st.subheader("Histórico Recente na Obra")
            if st.session_state.lancamentos:
                lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
                lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
                colunas_display = ['Data', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Data do Serviço', 'Observação']
                st.dataframe(lancamentos_da_obra[colunas_display].tail(10).style.format({'Valor Unitário': 'R$ {:,.2f}', 'Valor Parcial': 'R$ {:,.2f}'}), use_container_width=True)
            else:
                st.info("Nenhum lançamento adicionado ainda.")

    elif st.session_state.page == "Resumo da Folha 📊":
        st.header(f"Resumo da Folha - Obra: {st.session_state['obra_logada']}")
        funcionarios_da_obra = funcionarios_df[funcionarios_df['OBRA'] == st.session_state['obra_logada']]
        funcionarios_disponiveis = funcionarios_da_obra['NOME'].unique()
        
        funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s) específico(s):", options=funcionarios_disponiveis)
        
        base_para_resumo = funcionarios_da_obra.copy()
        if funcionarios_filtrados:
            base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]

        if base_para_resumo.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            if st.session_state.lancamentos:
                lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
                lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
                
                if not lancamentos_da_obra.empty:
                    producao_por_funcionario = lancamentos_da_obra.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
                    producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
                    resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
                    if 'Funcionário' in resumo_df.columns:
                        resumo_df = resumo_df.drop(columns=['Funcionário'])
                else:
                    resumo_df = base_para_resumo.copy()
                    resumo_df['PRODUÇÃO (R$)'] = 0.0
            else:
                resumo_df = base_para_resumo.copy()
                resumo_df['PRODUÇÃO (R$)'] = 0.0

            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            resumo_final_df = resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
            resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(calcular_salario_final, axis=1)
            colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)']
            resumo_final_df = resumo_final_df[colunas_finais].reset_index(drop=True)
            st.dataframe(resumo_final_df.style.format(formatter={'SALÁRIO BASE (R$)': '{:,.2f}', 'PRODUÇÃO (R$)': '{:,.2f}', 'SALÁRIO A RECEBER (R$)': '{:,.2f}'}), use_container_width=True)

    elif st.session_state.page == "Editar Lançamentos ✏️":
        st.header(f"Gerenciar Lançamentos - Obra: {st.session_state['obra_logada']}")
        
        if not st.session_state.lancamentos:
            st.info("Nenhum lançamento na planilha para editar.")
        else:
            lancamentos_df = pd.DataFrame(st.session_state.lancamentos).copy()
            lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']].reset_index(drop=True)
            lancamentos_da_obra.reset_index(inplace=True)
            lancamentos_da_obra.rename(columns={'index': 'id_lancamento'}, inplace=True)
            
            funcionarios_para_filtrar = sorted(lancamentos_da_obra['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar)

            df_filtrado = lancamentos_da_obra.copy()
            if funcionario_filtrado:
                df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]

            if df_filtrado.empty:
                st.warning("Nenhum lançamento encontrado.")
            else:
                df_filtrado['Remover'] = False
                colunas_visiveis = ['Remover', 'Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação', 'Data do Serviço', 'id_lancamento']
                st.write("Marque as caixas dos lançamentos que deseja apagar e clique no botão de remoção.")
                df_modificado = st.data_editor(
                    df_filtrado[colunas_visiveis],
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
                        df_original_obra = lancamentos_da_obra.copy()
                        df_outras_obras = pd.DataFrame(st.session_state.lancamentos)[pd.DataFrame(st.session_state.lancamentos)['Obra'] != st.session_state['obra_logada']]
                        df_obra_atualizada = df_original_obra[~df_original_obra['id_lancamento'].isin(ids_para_remover_local)].drop(columns=['id_lancamento'])
                        df_final_completo = pd.concat([df_outras_obras, df_obra_atualizada], ignore_index=True)

                        try:
                            gc = get_gsheets_connection()
                            ws_lancamentos = gc.open_by_url(sheet_url).worksheet("Lançamentos")
                            ws_lancamentos.clear()
                            set_with_dataframe(ws_lancamentos, df_final_completo, include_index=False, resize=True)
                            st.session_state.lancamentos = df_final_completo.to_dict('records')
                            st.toast("Lançamentos removidos com sucesso!", icon="🗑️")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ocorreu um erro ao atualizar a planilha: {e}")

    elif st.session_state.page == "Dashboard de Análise 📈":
        st.header(f"Dashboard de Análise - Obra: {st.session_state['obra_logada']}")
        lancamentos_df = pd.DataFrame(st.session_state.lancamentos)
        lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
        
        if lancamentos_da_obra.empty:
            st.info("Ainda não há lançamentos nesta obra para analisar.")
        else:
            st.markdown("#### Filtros do Dashboard")
            col1, col2 = st.columns(2)
            
            with col1:
                data_inicio = st.date_input("Data de Início", value=(datetime.now() - timedelta(days=30)).date())
            with col2:
                data_fim = st.date_input("Data de Fim", value=datetime.now().date())
            
            data_inicio_ts = pd.to_datetime(data_inicio)
            data_fim_ts = pd.to_datetime(data_fim) + timedelta(days=1)

            df_filtrado_dash = lancamentos_da_obra[(lancamentos_da_obra['Data'] >= data_inicio_ts) & (lancamentos_da_obra['Data'] < data_fim_ts)]

            funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
            funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s)", options=funcionarios_disponiveis)

            if funcionarios_filtrados:
                df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados)]

            if df_filtrado_dash.empty:
                st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
            else:
                st.markdown("---")
                st.subheader("Visão Geral do Período")
                kpi1, kpi2, kpi3 = st.columns(3)
                total_produzido = df_filtrado_dash['Valor Parcial'].sum()
                kpi1.metric("Produção Total", format_currency(total_produzido))
                
                if not df_filtrado_dash.empty:
                    top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
                    kpi2.metric("Funcionário Destaque", top_funcionario)
                    
                    top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()
                    kpi3.metric("Serviço de Maior Custo", top_servico)

                st.markdown("---")
                
                st.subheader("Produção por Funcionário")
                prod_func = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                fig_bar = px.bar(prod_func, x='Funcionário', y='Valor Parcial', text_auto=True, title="Produção Total por Funcionário")
                fig_bar.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color='#E37731')
                st.plotly_chart(fig_bar, use_container_width=True)
                
                st.subheader("Produção Diária")
                prod_dia = df_filtrado_dash.set_index('Data').resample('D')['Valor Parcial'].sum().reset_index()
                fig_line = px.line(prod_dia, x='Data', y='Valor Parcial', markers=True, title="Evolução da Produção Diária")
                fig_line.update_traces(marker=dict(color='#E37731', size=8))
                st.plotly_chart(fig_line, use_container_width=True)

                st.markdown("---")
                st.subheader("Análise Mensal")
                
                prod_mes = df_filtrado_dash.set_index('Data').resample('M')['Valor Parcial'].sum().reset_index()
                prod_mes['Mês'] = prod_mes['Data'].dt.strftime('%b/%Y')
                
                if not prod_mes.empty and prod_mes['Valor Parcial'].sum() > 0:
                    mes_destaque = prod_mes.loc[prod_mes['Valor Parcial'].idxmax()]
                    st.metric("Mês de Maior Produção", f"{mes_destaque['Mês']}", f"{format_currency(mes_destaque['Valor Parcial'])}")

                    fig_mes = px.bar(prod_mes, x='Mês', y='Valor Parcial', text_auto=True, title="Produção Mensal Total")
                    fig_mes.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color='#E37731')
                    st.plotly_chart(fig_mes, use_container_width=True)





