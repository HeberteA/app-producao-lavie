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

def gerar_relatorio_pdf(resumo_df, lancamentos_df, logo_path, mes_referencia, obra_nome=None):
    from weasyprint import HTML
    try:
        with open(logo_path, "rb") as image_file:
            logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        logo_base64 = None
    style = """
    @page { size: A4 landscape; margin: 1.5cm; }
    body { font-family: 'Helvetica', sans-serif; font-size: 10px; }
    .header { text-align: center; margin-bottom: 20px; }
    .logo { width: 200px; height: auto; }
    h1 { font-size: 20px; color: #333; }
    h2 { font-size: 16px; color: #555; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 25px; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #ddd; padding: 6px; text-align: left; }
    th { background-color: #f2f2f2; font-weight: bold; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    """
    html_string = f"""
    <html>
    <head><style>{style}</style></head>
    <body>
        <div class="header">
            {f'<img src="data:image/png;base64,{logo_base64}" class="logo">' if logo_base64 else ''}
            <h1>Relatório de Produção - {mes_referencia}</h1>
            {f'<h2>Obra: {obra_nome}</h2>' if obra_nome else ''}
        </div>
        <h2>Resumo da Folha</h2>
        {resumo_df.to_html(index=False, na_rep='', classes='table', formatters={
            'SALÁRIO BASE (R$)': lambda x: f'R$ {x:,.2f}',
            'PRODUÇÃO (R$)': lambda x: f'R$ {x:,.2f}',
            'SALÁRIO A RECEBER (R$)': lambda x: f'R$ {x:,.2f}'
        })}
        <h2>Histórico de Lançamentos do Mês</h2>
        {lancamentos_df.to_html(index=False, na_rep='', classes='table', formatters={
            'Valor Unitário': lambda x: f'R$ {x:,.2f}',
            'Valor Parcial': lambda x: f'R$ {x:,.2f}'
        })}
    </body>
    </html>
    """
    return HTML(string=html_string).write_pdf()

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
            st.info("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obras_df = db_utils.get_obras()
            obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == st.session_state['obra_logada']]
            if not obra_info.empty:
                obra_id = int(obra_info.iloc[0]['id'])
                hoje = date.today()
                mes_referencia_status = hoje.replace(day=1)
                mes_ref_str = mes_referencia_status.strftime('%Y-%m')
                status_df = db_utils.get_status_do_mes(mes_ref_str)
                status_geral_obra_row = status_df[(status_df['obra_id'] == obra_id) & (status_df['funcionario_id'] == 0)]
                status_auditoria = status_geral_obra_row['Status'].iloc[0] if not status_geral_obra_row.empty else "A Revisar"
                if status_auditoria == 'Aprovado':
                    st.success(f"Status da Auditoria: {status_auditoria}")
                elif status_auditoria == 'Analisar':
                    st.error(f"Status da Auditoria: {status_auditoria}")
                else:
                    st.info(f"Status da Auditoria: {status_auditoria}")
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
        selected_month = st.selectbox("Selecione o Mês", options=available_months, index=current_index, label_visibility="collapsed")
        st.session_state.selected_month = selected_month
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
        if st.button("📄 Gerar Relatório em PDF", use_container_width=True):
            with st.spinner("Gerando relatório..."):
                funcionarios_df = db_utils.get_funcionarios(); lancamentos_df = db_utils.get_lancamentos_do_mes(st.session_state.selected_month)
                
                if funcionarios_df.empty:
                    st.toast("Nenhum funcionário para gerar relatório.", icon="🤷")
                else:
                    base_para_resumo = funcionarios_df.rename(columns={'id': 'funcionario_id'})
                    producao_df = lancamentos_df.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                    producao_df.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
                    resumo_df = pd.merge(base_para_resumo, producao_df, on='funcionario_id', how='left')
                    resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
                    if 'PRODUÇÃO (R$)' not in resumo_df.columns: resumo_df['PRODUÇÃO (R$)'] = 0
                    if 'SALÁRIO BASE (R$)' not in resumo_df.columns: resumo_df['SALÁRIO BASE (R$)'] = 0
                    resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
                    resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0)
                    resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)
                    concluidos_list = st.session_state.get('concluded_employees', [])
                    resumo_df['Situação'] = resumo_df['Funcionário'].apply(lambda nome: 'Concluído' if nome in concluidos_list else 'Pendente')
                    
                    obra_relatorio = None
                    if st.session_state['role'] == 'user':
                        obra_relatorio = st.session_state['obra_logada']
                        resumo_df = resumo_df[resumo_df['OBRA'] == obra_relatorio]
                        lancamentos_df = lancamentos_df[lancamentos_df['Obra'] == obra_relatorio]
                    
                    colunas_resumo = ['Funcionário', 'OBRA', 'FUNÇÃO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)', 'Situação']
                    if st.session_state['role'] == 'user': colunas_resumo.remove('OBRA')
                    
                    colunas_lancamentos = ['Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial']
                    if st.session_state['role'] == 'user': colunas_lancamentos.remove('Obra')

                    pdf_data = gerar_relatorio_pdf( 
                        resumo_df=resumo_df[colunas_resumo],
                        lancamentos_df=lancamentos_df[colunas_lancamentos],
                        logo_path="Lavie.png",
                        mes_referencia=st.session_state.selected_month,
                        obra_nome=obra_relatorio
                    )
                        
                    st.download_button(
                        label="⬇️ Clique aqui para baixar o Relatório",
                        data=pdf_data,
                        type="primary",
                        file_name=f"Relatorio_{st.session_state.selected_month}_{obra_relatorio or 'Geral'}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True, type="primary"):
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




