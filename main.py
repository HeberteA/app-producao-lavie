import streamlit as st
import sys
import os
from datetime import datetime, timedelta, date
import pandas as pd
import base64
import io

try:
    from streamlit_option_menu import option_menu
    STREAMLIT_OPTION_MENU_AVAILABLE = True
except ImportError:
    STREAMLIT_OPTION_MENU_AVAILABLE = False
    st.error("Biblioteca 'streamlit-option-menu' não encontrada. Instale com: pip install streamlit-option-menu")


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_utils
import utils 
from paginas import (
    lancamento_folha, 
    auditoria, 
    gerenciar_funcionarios, 
    gerenciar_obras, 
    resumo_da_folha, 
    remover_lancamentos, 
    dashboard_de_analise,
    gerenciar_funcoes,
    gerenciar_servicos  
)

st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

APP_STYLE_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 10% 20%, #1e1e24 0%, #050505 90%);
    background-attachment: fixed;
}
/* Ajustes de Inputs para contraste */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: white !important;
}
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input {
    color: white !important;
}
/* Steps */
.step-container {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px;
    background: rgba(255,255,255,0.03); padding: 20px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.05);
}
.step-item {
    display: flex; align-items: center; flex-direction: column; color: #666; font-weight: 500; width: 33%; position: relative;
}
.step-item .step-number {
    width: 35px; height: 35px; border-radius: 50%; border: 2px solid #555; display: flex; align-items: center; justify-content: center;
    font-weight: bold; margin-bottom: 8px; transition: all 0.3s ease; background-color: #111;
}
.step-item.active { color: #E37026; }
.step-item.active .step-number { border-color: #E37026; background-color: #E37026; color: #FFFFFF; box-shadow: 0 0 15px rgba(227, 112, 38, 0.5); }
</style>
"""
st.markdown(APP_STYLE_CSS, unsafe_allow_html=True)

if not hasattr(utils, 'gerar_relatorio_pdf'):
     st.error("Função 'gerar_relatorio_pdf' não encontrada em utils.py! Mova a função de main.py para utils.py.")
     def gerar_relatorio_pdf(*args, **kwargs): 
         st.error("gerar_relatorio_pdf não implementado em utils.py")
         return None
else:
     gerar_relatorio_pdf = utils.gerar_relatorio_pdf


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
                st.session_state.user_identifier = 'admin' 
                st.session_state.page = 'auditoria' 
                st.rerun()
            else:
                st.error("Senha de administrador incorreta.")
    else:
        obras_ativas_login = obras_df_login[obras_df_login['status'] == 'Ativa'] 
        if obras_ativas_login.empty:
             st.error("Nenhuma obra ativa encontrada para login.")
             return
        obras_com_acesso = pd.merge(obras_ativas_login, acessos_df_login, left_on='id', right_on='obra_id')
        if obras_com_acesso.empty:
             st.error("Nenhuma obra configurada com código de acesso.")
             return
             
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
                        st.session_state.user_identifier = f"user_{obra_login}" 
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

    @st.cache_data
    def get_sidebar_data(mes_atual):
        obras_df = db_utils.get_obras() 
        folhas_df = db_utils.get_folhas_mensais() 
        status_df = db_utils.get_status_do_mes(mes_atual) 
        return obras_df, folhas_df, status_df

    mes_atual_sidebar = datetime.now().strftime('%Y-%m')
    obras_df_sidebar, folhas_df_sidebar, status_df_sidebar = get_sidebar_data(mes_atual_sidebar)

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.info("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obra_info = obras_df_sidebar.loc[obras_df_sidebar['NOME DA OBRA'] == st.session_state['obra_logada']]
            if not obra_info.empty:
                obra_id = int(obra_info.iloc[0]['id'])
                hoje = date.today()
                mes_referencia_status = hoje.replace(day=1)
                
                status_geral_obra_row = status_df_sidebar[(status_df_sidebar['obra_id'] == obra_id) & (status_df_sidebar['funcionario_id'] == 0)]
                status_auditoria = status_geral_obra_row['Status'].iloc[0] if not status_geral_obra_row.empty else "A Revisar"
                
                utils.display_status_box("Status Auditoria", status_auditoria) 

                if 'aviso' in obra_info.columns:
                    aviso_obra = obra_info['aviso'].iloc[0]
                    if aviso_obra and str(aviso_obra).strip():
                        st.warning(f"Aviso: {aviso_obra}")

        st.markdown("---")
        st.subheader("Mês de Referência")
        current_month_str = datetime.now().strftime('%Y-%m')
        last_month_str = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
        available_months = sorted(list(set([current_month_str, last_month_str])), reverse=True)
        try:
            current_index = available_months.index(st.session_state.selected_month)
        except ValueError:
            available_months.append(st.session_state.selected_month)
            available_months = sorted(list(set(available_months)), reverse=True)
            current_index = available_months.index(st.session_state.selected_month)
            
        selected_month = st.selectbox("Selecione o Mês", options=available_months, index=current_index, label_visibility="collapsed")
        if selected_month != st.session_state.selected_month:
            st.session_state.selected_month = selected_month
            st.rerun() 

        st.markdown("---")
        
        if STREAMLIT_OPTION_MENU_AVAILABLE:
            page_definitions = {
                'lancamento_folha': ("Lançamento Folha", "pencil-square"),
                'auditoria': ("Auditoria", "pencil-fill"),
                'dashboard_de_analise': ("Dashboard", "graph-up"),
                'resumo_da_folha': ("Resumo da Folha", "file-earmark-text"),
                'remover_lancamentos': ("Lançamentos", "trash"),
                'gerenciar_funcionarios': ("Funcionários", "people-fill"),
                'gerenciar_funcoes': ("Funções", "gear-fill"),
                'gerenciar_servicos': ("Serviços", "tools"),
                'gerenciar_obras': ("Obras", "building"),
            }
            admin_pages = ['auditoria', 'resumo_da_folha', 'gerenciar_funcionarios', 'gerenciar_funcoes', 'gerenciar_servicos', 'gerenciar_obras', 'remover_lancamentos', 'dashboard_de_analise']
            user_pages = ['lancamento_folha', 'resumo_da_folha', 'remover_lancamentos', 'dashboard_de_analise']
            pages_to_show_keys = admin_pages if st.session_state.role == 'admin' else user_pages
            menu_titles = [page_definitions[key][0] for key in pages_to_show_keys]
            menu_icons = [page_definitions[key][1] for key in pages_to_show_keys]
            current_page_key = st.session_state.get('page', pages_to_show_keys[0])
            try: default_index = pages_to_show_keys.index(current_page_key)
            except ValueError: default_index = 0
            
            selected_title = option_menu(
                menu_title="Navegação", options=menu_titles, icons=menu_icons,
                menu_icon="list-task", default_index=default_index,
                styles={
                    "container": {"padding": "5px !important", "background-color": "transparent"},
                    "icon": {"font-size": "18px"}, "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px"},
                    "nav-link-selected": {"background-color": "#E37026"}, 
                }
            )
            title_to_key_map = {page_definitions[key][0]: key for key in pages_to_show_keys}
            st.session_state.page = title_to_key_map[selected_title]
        else: 
            st.header("Navegação")
            if st.session_state.role == 'user':
                if st.button("📝 Lançamento Folha", use_container_width=True): st.session_state.page = 'lancamento_folha'
            if st.session_state.role == 'admin':
                if st.button("✏️ Auditoria", use_container_width=True): st.session_state.page = 'auditoria'
                if st.button("👥 Gerenciar Funcionários", use_container_width=True): st.session_state.page = 'gerenciar_funcionarios'
                if st.button("🔧 Gerenciar Funções", use_container_width=True): st.session_state.page = 'gerenciar_funcoes'
                if st.button("🛠️ Gerenciar Serviços", use_container_width=True): st.session_state.page = 'gerenciar_servicos'
                if st.button("🏗️ Gerenciar Obras", use_container_width=True): st.session_state.page = 'gerenciar_obras'
            if st.button("📊 Resumo da Folha", use_container_width=True): st.session_state.page = 'resumo_da_folha'
            if st.button("🗑️ Remover Lançamentos", use_container_width=True): st.session_state.page = 'remover_lancamentos'
            if st.button("📈 Dashboard de Análise", use_container_width=True): st.session_state.page = 'dashboard_de_analise'
        
 

        st.markdown("---")
        
        if st.session_state.role == 'user':
            obra_info_envio = obras_df_sidebar.loc[obras_df_sidebar['NOME DA OBRA'] == st.session_state['obra_logada']]
            if not obra_info_envio.empty:
                obra_id_envio = int(obra_info_envio.iloc[0]['id'])
                
                mes_selecionado_str = st.session_state.selected_month 
                try:
                    mes_referencia_envio = pd.to_datetime(mes_selecionado_str).date().replace(day=1) 
                except Exception as e:
                    st.error(f"Erro ao processar data: {e}")
                    mes_referencia_envio = date.today().replace(day=1) 
                
                st.subheader(f"Envio da Folha ({mes_referencia_envio.strftime('%m/%Y')})")

                folha_do_mes = folhas_df_sidebar[
                    (folhas_df_sidebar['obra_id'] == obra_id_envio) &
                    (folhas_df_sidebar['Mes'] == mes_referencia_envio)
                ]
                status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"

                hoje = date.today()
                mes_atual_str = hoje.strftime('%Y-%m')

                if status_folha == "Não Enviada":
                    if mes_selecionado_str == mes_atual_str:
                        DIA_LIMITE = 23 
                        dias_para_o_prazo = DIA_LIMITE - hoje.day
                        if dias_para_o_prazo < 0: st.error(f"Prazo vencido há {abs(dias_para_o_prazo)} dia(s)!")
                        elif dias_para_o_prazo <= 7: st.warning(f"Prazo vence em {dias_para_o_prazo} dia(s).")
                        else: st.info(f"Prazo de envio: Dia {DIA_LIMITE}.")
                    else:
                        st.warning("Esta folha de um mês anterior ainda não foi enviada.")
                elif status_folha == 'Devolvida para Revisão':
                     st.warning("⚠️ Folha devolvida. Revise e reenvie.")
                
                st.info(f"Status do Envio: {status_folha}")
                if not folha_do_mes.empty and pd.notna(folha_do_mes.iloc[0]['data_lancamento']):
                    data_envio = pd.to_datetime(folha_do_mes.iloc[0]['data_lancamento'])
                    st.caption(f"Último envio em: {data_envio.strftime('%d/%m/%Y às %H:%M')}")

                btn_enviar_desabilitado = status_folha in ['Enviada para Auditoria', 'Finalizada']
                
                if st.button("Enviar para Auditoria", use_container_width=True, type="primary", disabled=btn_enviar_desabilitado):
                    with st.spinner("Enviando folha..."):
                        if db_utils.enviar_folha_para_auditoria(obra_id_envio, mes_selecionado_str, st.session_state['obra_logada']):
                            st.success("Folha enviada com sucesso!")
                            st.cache_data.clear() 
                            st.rerun()
            st.markdown("---")
        st.header("Relatório")
        
        obra_pdf_selecionada = "Todas" 
        obra_pdf_nome_arquivo = "Geral"
        obra_pdf_titulo = None
        
        if st.session_state['role'] == 'admin':
            opcoes_obra_pdf = ["Todas"] + sorted(obras_df_sidebar['NOME DA OBRA'].unique())
            obra_pdf_selecionada = st.selectbox(
                "Gerar relatório para a Obra:", 
                options=opcoes_obra_pdf, 
                key="sidebar_pdf_obra_filter"
            )
            if obra_pdf_selecionada != "Todas":
                 obra_pdf_nome_arquivo = obra_pdf_selecionada.replace(" ", "_") 
                 obra_pdf_titulo = obra_pdf_selecionada
        elif st.session_state['role'] == 'user':
            obra_pdf_selecionada = st.session_state['obra_logada']
            obra_pdf_nome_arquivo = obra_pdf_selecionada.replace(" ", "_")
            obra_pdf_titulo = obra_pdf_selecionada
        
        pdf_download_placeholder = st.empty()
        if pdf_download_placeholder.button("📄 Gerar Relatório em PDF", use_container_width=True, key="gerar_pdf_sidebar"):
            with st.spinner("Gerando relatório..."):
                funcionarios_pdf = db_utils.get_funcionarios() 
                lancamentos_pdf = db_utils.get_lancamentos_do_mes(st.session_state.selected_month) 
                
                if funcionarios_pdf.empty:
                    st.toast("Nenhum funcionário ativo para gerar relatório.", icon="🤷")
                else:
                    base_para_resumo = funcionarios_pdf.copy()
                    base_para_resumo['funcionario_id'] = base_para_resumo['id'] 
                    base_para_resumo['SALARIO_BASE'] = base_para_resumo['SALARIO_BASE'].apply(utils.safe_float)

                    producao_bruta_pdf_df = pd.DataFrame()
                    total_gratificacoes_pdf_df = pd.DataFrame()

                    if not lancamentos_pdf.empty:
                         lancamentos_pdf['Valor Parcial'] = lancamentos_pdf['Valor Parcial'].apply(utils.safe_float)
                         lanc_producao_pdf = lancamentos_pdf[lancamentos_pdf['Disciplina'] != 'GRATIFICAÇÃO']
                         if not lanc_producao_pdf.empty:
                             producao_bruta_pdf_df = lanc_producao_pdf.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                             producao_bruta_pdf_df.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
                         lanc_gratificacoes_pdf = lancamentos_pdf[lancamentos_pdf['Disciplina'] == 'GRATIFICAÇÃO']
                         if not lanc_gratificacoes_pdf.empty:
                             total_gratificacoes_pdf_df = lanc_gratificacoes_pdf.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                             total_gratificacoes_pdf_df.rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'}, inplace=True)
                    
                    resumo_pdf = base_para_resumo.copy()
                    if not producao_bruta_pdf_df.empty:
                        resumo_pdf = pd.merge(resumo_pdf, producao_bruta_pdf_df, on='funcionario_id', how='left')
                    else: resumo_pdf['PRODUÇÃO BRUTA (R$)'] = 0.0
                    if not total_gratificacoes_pdf_df.empty:
                         resumo_pdf = pd.merge(resumo_pdf, total_gratificacoes_pdf_df, on='funcionario_id', how='left')
                    else: resumo_pdf['TOTAL GRATIFICAÇÕES (R$)'] = 0.0

                    resumo_pdf = resumo_pdf.loc[:,~resumo_pdf.columns.duplicated()]
                    if 'funcionario_id' in resumo_pdf.columns and 'id' in resumo_pdf.columns and 'funcionario_id' != 'id':
                         resumo_pdf = resumo_pdf.drop(columns=['funcionario_id'])

                    resumo_pdf.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
                    resumo_pdf['PRODUÇÃO BRUTA (R$)'] = resumo_pdf['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
                    resumo_pdf['TOTAL GRATIFICAÇÕES (R$)'] = resumo_pdf['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
                    resumo_pdf['SALÁRIO BASE (R$)'] = resumo_pdf['SALÁRIO BASE (R$)'].fillna(0.0)

                    resumo_pdf['PRODUÇÃO LÍQUIDA (R$)'] = resumo_pdf.apply(utils.calcular_producao_liquida, axis=1)
                    resumo_pdf['SALÁRIO A RECEBER (R$)'] = resumo_pdf.apply(utils.calcular_salario_final, axis=1)

                    status_pdf = db_utils.get_status_do_mes(st.session_state.selected_month) 
                    concluidos_df = status_pdf[status_pdf['Lancamentos Concluidos'] == True][['funcionario_id']].drop_duplicates()
                    if not concluidos_df.empty:
                         resumo_pdf = pd.merge(resumo_pdf, concluidos_df, left_on='id', right_on='funcionario_id', how='left', indicator=True)
                         resumo_pdf['Situação'] = resumo_pdf['_merge'].apply(lambda x: 'Concluído' if x == 'both' else 'Pendente')
                         resumo_pdf.drop(columns=['_merge'], inplace=True)
                         if 'funcionario_id' in resumo_pdf.columns and 'id' in resumo_pdf.columns and 'funcionario_id' != 'id':
                            resumo_pdf = resumo_pdf.drop(columns=['funcionario_id'])
                    else: resumo_pdf['Situação'] = 'Pendente'

                    if obra_pdf_selecionada != "Todas":
                        resumo_pdf = resumo_pdf[resumo_pdf['OBRA'] == obra_pdf_selecionada]
                        if not lancamentos_pdf.empty:
                            lancamentos_pdf = lancamentos_pdf[lancamentos_pdf['Obra'] == obra_pdf_selecionada]
                    
                    if resumo_pdf.empty:
                         st.warning(f"Nenhum dado encontrado para a obra '{obra_pdf_selecionada}' no mês {st.session_state.selected_month}.")
                    else:
                        colunas_resumo_pdf = ['Funcionário', 'OBRA', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)', 'PRODUÇÃO LÍQUIDA (R$)', 'TOTAL GRATIFICAÇÕES (R$)', 'SALÁRIO A RECEBER (R$)', 'Situação']
                        if obra_pdf_selecionada != "Todas":
                             if 'OBRA' in colunas_resumo_pdf: colunas_resumo_pdf.remove('OBRA')
                        
                        colunas_lancamentos_pdf = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
                        if obra_pdf_selecionada != "Todas":
                             if 'Obra' in colunas_lancamentos_pdf: colunas_lancamentos_pdf.remove('Obra')

                        colunas_resumo_pdf_exist = [col for col in colunas_resumo_pdf if col in resumo_pdf.columns]
                        if lancamentos_pdf.empty: lancamentos_pdf = pd.DataFrame(columns=colunas_lancamentos_pdf)
                        colunas_lancamentos_pdf_exist = [col for col in colunas_lancamentos_pdf if col in lancamentos_pdf.columns]

                        pdf_data = utils.gerar_relatorio_pdf( 
                            resumo_df=resumo_pdf[colunas_resumo_pdf_exist],
                            lancamentos_df=lancamentos_pdf[colunas_lancamentos_pdf_exist],
                            logo_path="Lavie.png",
                            mes_referencia=st.session_state.selected_month,
                            obra_nome=obra_pdf_titulo 
                        )
                            
                        if pdf_data: 
                            pdf_download_placeholder.download_button(
                                label="⬇️ Clique aqui para baixar o Relatório", data=pdf_data,
                                type="primary",
                                file_name=f"Relatorio_{st.session_state.selected_month}_{obra_pdf_nome_arquivo}.pdf",
                                mime="application/pdf", use_container_width=True,
                                key="pdf_download_sidebar_final" 
                            )
                            st.info("Seu download está pronto. Clique no botão acima.")

        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True, type="primary"):
            st.cache_data.clear() 
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
    page_to_render = st.session_state.page
    page_map = {
        'lancamento_folha': lancamento_folha,
        'auditoria': auditoria,
        'gerenciar_funcionarios': gerenciar_funcionarios,
        'gerenciar_funcoes': gerenciar_funcoes, 
        'gerenciar_servicos': gerenciar_servicos, 
        'gerenciar_obras': gerenciar_obras,
        'resumo_da_folha': resumo_da_folha,
        'remover_lancamentos': remover_lancamentos,
        'dashboard_de_analise': dashboard_de_analise
    }
    if page_to_render in page_map:
        page_map[page_to_render].render_page()
    else:
        st.error(f"Página '{page_to_render}' não encontrada. Redirecionando...")
        st.session_state.page = 'auditoria' if st.session_state.role == 'admin' else 'lancamento_folha'
        st.rerun()





