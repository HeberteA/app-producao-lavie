import streamlit as st
import sys
import os
from datetime import datetime, timedelta, date
import pandas as pd
import base64
import io

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
            current_index = 0
            st.session_state.selected_month = available_months[0] 
            
        selected_month = st.selectbox("Selecione o Mês", options=available_months, index=current_index, label_visibility="collapsed")
        if selected_month != st.session_state.selected_month:
            st.session_state.selected_month = selected_month
            st.rerun() 
        st.markdown("---")
        st.header("Navegação")
        if st.session_state.role == 'user':
            if st.button("📝 Lançamento Folha", use_container_width=True):
                st.session_state.page = 'lancamento_folha'
        if st.session_state.role == 'admin':
            if st.button("✏️ Auditoria", use_container_width=True):
                st.session_state.page = 'auditoria'
            if st.button("👥 Gerenciar Funcionários", use_container_width=True):
                st.session_state.page = 'gerenciar_funcionarios'
            if st.button("🔧 Gerenciar Funções", use_container_width=True): 
                st.session_state.page = 'gerenciar_funcoes'
            if st.button("🛠️ Gerenciar Serviços", use_container_width=True):
                st.session_state.page = 'gerenciar_servicos'
            if st.button("🏗️ Gerenciar Obras", use_container_width=True):
                st.session_state.page = 'gerenciar_obras'
        if st.button("📊 Resumo da Folha", use_container_width=True):
            st.session_state.page = 'resumo_da_folha'
        if st.button("🗑️ Gerenciar Lançamentos", use_container_width=True):
            st.session_state.page = 'remover_lancamentos'
        if st.button("📈 Dashboard de Análise", use_container_width=True):
            st.session_state.page = 'dashboard_de_analise'
        st.markdown("---")
        
        if st.session_state.role == 'user':
            folhas_df = db_utils.get_folhas_mensais()
            obras_df = db_utils.get_obras()
            obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == st.session_state['obra_logada']]
            
            if not obra_info.empty:
                obra_id = int(obra_info.iloc[0]['id'])
                
                hoje = date.today()
                mes_referencia_envio = hoje.replace(day=1) 
                mes_ref_str = mes_referencia_envio.strftime('%Y-%m')
                
                st.subheader(f"Envio da Folha ({mes_referencia_envio.strftime('%m/%Y')})")

                folha_do_mes = folhas_df[
                    (folhas_df['obra_id'] == obra_id) &
                    (folhas_df['Mes'] == mes_referencia_envio)
                ]
                status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"

                if status_folha == "Não Enviada":
                    DIA_LIMITE = 23
                    dias_para_o_prazo = DIA_LIMITE - hoje.day
                    
                    if dias_para_o_prazo < 0:
                        st.error(f"Prazo de envio vencido há {abs(dias_para_o_prazo)} dia(s)!")
                    elif dias_para_o_prazo <= 7:
                        st.warning(f"Atenção: O prazo de envio vence em {dias_para_o_prazo} dia(s).")
                    else:
                        st.info(f"Prazo de envio: Dia {DIA_LIMITE}.")
                
                st.info(f"Status do Envio: {status_folha}")
                if not folha_do_mes.empty and pd.notna(folha_do_mes.iloc[0]['data_lancamento']):
                    data_envio = pd.to_datetime(folha_do_mes.iloc[0]['data_lancamento'])
                    st.caption(f"Último envio em: {data_envio.strftime('%d/%m/%Y às %H:%M')}")

                btn_enviar_desabilitado = status_folha in ['Enviada para Auditoria', 'Finalizada']
                if st.button("Enviar para Auditoria", use_container_width=True, type="primary", disabled=btn_enviar_desabilitado):
                    with st.spinner("Enviando folha..."):
                        if db_utils.enviar_folha_para_auditoria(obra_id, mes_ref_str, st.session_state['obra_logada']):
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
        if st.button("📄 Gerar Relatório em PDF", use_container_width=True):
            with st.spinner("Gerando relatório..."):
                funcionarios_pdf = db_utils.get_funcionarios() 
                lancamentos_pdf = db_utils.get_lancamentos_do_mes(st.session_state.selected_month) 
                
                if funcionarios_pdf.empty:
                    st.toast("Nenhum funcionário ativo para gerar relatório.", icon="🤷")
                else:
                    base_para_resumo = funcionarios_pdf.copy()
                    base_para_resumo['funcionario_id'] = base_para_resumo['id']
                    base_para_resumo['SALARIO_BASE'] = base_para_resumo['SALARIO_BASE'].apply(utils.safe_float)

                    if not lancamentos_pdf.empty:
                         lancamentos_pdf['Valor Parcial'] = lancamentos_pdf['Valor Parcial'].apply(utils.safe_float)
                         producao_bruta_pdf = lancamentos_pdf.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                         producao_bruta_pdf.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
                         resumo_pdf = pd.merge(base_para_resumo, producao_bruta_pdf, on='funcionario_id', how='left')
                    else:
                         resumo_pdf = base_para_resumo.copy()
                         resumo_pdf['PRODUÇÃO BRUTA (R$)'] = 0.0

                    resumo_pdf.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
                    resumo_pdf['PRODUÇÃO BRUTA (R$)'] = resumo_pdf['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
                    resumo_pdf['SALÁRIO BASE (R$)'] = resumo_pdf['SALÁRIO BASE (R$)'].fillna(0.0)

                    resumo_pdf['PRODUÇÃO LÍQUIDA (R$)'] = resumo_pdf.apply(utils.calcular_producao_liquida, axis=1)
                    resumo_pdf['SALÁRIO A RECEBER (R$)'] = resumo_pdf.apply(utils.calcular_salario_final, axis=1)

                    status_pdf = db_utils.get_status_do_mes(st.session_state.selected_month) # Cacheado
                    concluidos_df = status_pdf[status_pdf['Lancamentos Concluidos'] == True][['funcionario_id']]
                    if not concluidos_df.empty:
                         resumo_pdf = pd.merge(resumo_pdf, concluidos_df, on='funcionario_id', how='left', indicator=True)
                         resumo_pdf['Situação'] = resumo_pdf['_merge'].apply(lambda x: 'Concluído' if x == 'both' else 'Pendente')
                         resumo_pdf.drop(columns=['_merge'], inplace=True)
                    else:
                         resumo_pdf['Situação'] = 'Pendente'
                    if obra_pdf_selecionada != "Todas":
                        resumo_pdf = resumo_pdf[resumo_pdf['OBRA'] == obra_pdf_selecionada]
                        if not lancamentos_pdf.empty:
                            lancamentos_pdf = lancamentos_pdf[lancamentos_pdf['Obra'] == obra_pdf_selecionada]
                    
                    if resumo_pdf.empty:
                         st.warning(f"Nenhum dado encontrado para a obra '{obra_pdf_selecionada}' no mês {st.session_state.selected_month}.")
                    else:
                        colunas_resumo_pdf = [
                            'Funcionário', 'OBRA', 'FUNÇÃO', 
                            'SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)', 
                            'PRODUÇÃO LÍQUIDA (R$)', 'SALÁRIO A RECEBER (R$)', 
                            'Situação'
                        ]
                        if obra_pdf_selecionada != "Todas":
                             if 'OBRA' in colunas_resumo_pdf: colunas_resumo_pdf.remove('OBRA')
                        
                        colunas_lancamentos_pdf = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
                        if obra_pdf_selecionada != "Todas":
                             if 'Obra' in colunas_lancamentos_pdf: colunas_lancamentos_pdf.remove('Obra')

                        if lancamentos_pdf.empty:
                            lancamentos_pdf = pd.DataFrame(columns=colunas_lancamentos_pdf)

                        pdf_data = utils.gerar_relatorio_pdf( 
                            resumo_df=resumo_pdf[colunas_resumo_pdf],
                            lancamentos_df=lancamentos_pdf[colunas_lancamentos_pdf],
                            logo_path="Lavie.png",
                            mes_referencia=st.session_state.selected_month,
                            obra_nome=obra_pdf_titulo
                        )
                            
                        if pdf_data: 
                            st.download_button(
                                label="⬇️ Clique aqui para baixar o Relatório",
                                data=pdf_data,
                                type="primary",
                                file_name=f"Relatorio_{st.session_state.selected_month}_{obra_pdf_nome_arquivo}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
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







