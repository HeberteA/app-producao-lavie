import streamlit as st
from datetime import datetime, timedelta, date
import io
import pandas as pd
import db_utils
import utils

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
        st.error("Não foi possível carregar os dados das obras para o login. Verifique a conexão e as configurações do banco.")
        return

    admin_login = st.checkbox("Entrar como Administrador")

    if admin_login:
        admin_password = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar como Admin", use_container_width=True, type="primary"):
            if 'admin' in st.secrets and st.secrets.admin.password == admin_password:
                st.session_state['logged_in'] = True
                st.session_state['role'] = 'admin'
                st.session_state['obra_logada'] = 'Todas'
                st.session_state['user_identifier'] = 'admin'
                db_utils.registrar_log('admin', "LOGIN_SUCCESS")
                st.rerun()
            else:
                db_utils.registrar_log('admin', "LOGIN_FAIL", "Senha incorreta.")
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
                        st.session_state['logged_in'] = True
                        st.session_state['role'] = 'user'
                        st.session_state['obra_logada'] = obra_login
                        st.session_state['user_identifier'] = f"user:{obra_login}"
                        db_utils.registrar_log(f"user:{obra_login}", "LOGIN_SUCCESS")
                        st.rerun()
                    else:
                        db_utils.registrar_log(f"user:{obra_login}", "LOGIN_FAIL", "Código incorreto.")
                        st.error("Obra ou código de acesso incorreto.")
                except IndexError:
                    st.error("Obra ou código de acesso incorreto.")
            else:
                st.warning("Por favor, selecione a obra e insira o código.")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.set_page_config(page_title="Login") 
    login_page()
else:
    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obras_df = db_utils.get_obras()
            obra_logada_info = obras_df.loc[obras_df['NOME DA OBRA'] == st.session_state['obra_logada']]
            if not obra_logada_info.empty:
                obra_logada_id = obra_logada_info.iloc[0]['id']
                aviso_obra = obra_logada_info.iloc[0]['aviso']

        st.markdown("---")

        st.header("Navegação")
        
        if st.session_state['role'] == 'user':
            st.page_link("1_📝_Lançamento_Folha.py", label="Lançamento Folha", icon="📝")

        if st.session_state['role'] == 'admin':
            st.page_link("2_✏️_Auditoria.py", label="Auditoria", icon="✏️")
            st.page_link("3_👥_Gerenciar_Funcionários.py", label="Gerenciar Funcionários", icon="👥")
            st.page_link("4_🏗️_Gerenciar_Obras.py", label="Gerenciar Obras", icon="🏗️")
        
        st.page_link("5_📊_Resumo_da_Folha.py", label="Resumo da Folha", icon="📊")
        st.page_link("6_🗑️_Remover_Lançamentos.py", label="Remover Lançamentos", icon="🗑️")
        st.page_link("7_📈_Dashboard_de_Análise.py", label="Dashboard de Análise", icon="📈")
        
        st.markdown("---")
        st.subheader("Mês de Referência")
        
        current_month_str = datetime.now().strftime('%Y-%m')
        available_months = [current_month_str, (datetime.now() - timedelta(days=30)).strftime('%Y-%m')]
        available_months = sorted(list(set(available_months)), reverse=True)

        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=available_months.index(st.session_state.get('selected_month', current_month_str)),
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
        
        if st.session_state['role'] == 'user':
            if 'aviso_obra' in locals() and aviso_obra and str(aviso_obra).strip():
                st.markdown("---")
                st.error(f"📢 Aviso da Auditoria: {aviso_obra}")

            st.markdown("---")
            
            folhas_df = db_utils.get_folhas(selected_month)
            DIA_LIMITE = 23
            hoje = date.today()
            mes_folha_referencia = hoje.replace(day=1)
            
            st.subheader(f"Folha de {mes_folha_referencia.strftime('%B/%Y')}")

            if 'obra_logada_id' in locals():
                folha_status_row = folhas_df[
                    (folhas_df['obra_id'] == obra_logada_id) &
                    (pd.to_datetime(folhas_df['Mes']).dt.date == mes_folha_referencia)
                ]

                if not folha_status_row.empty:
                    status_folha = folha_status_row['status'].iloc[0]
                    if 'data_lancamento' in folha_status_row and pd.notna(folha_status_row['data_lancamento'].iloc[0]):
                        data_envio = pd.to_datetime(folha_status_row['data_lancamento'].iloc[0])
                        st.info(f"Enviada em: {data_envio.strftime('%d/%m/%Y às %H:%M')}")
                    
                    if status_folha == 'Devolvida para Revisão':
                        st.error(f"Status: {status_folha}")
                        if st.button("Reenviar Folha para Auditoria", use_container_width=True, type="primary"):
                            db_utils.enviar_folha_para_auditoria(obra_logada_id, mes_folha_referencia.strftime('%Y-%m'), st.session_state['obra_logada'])
                            st.rerun()
                    else:
                        st.success(f"Status: {status_folha}")
                else:
                    dias_para_o_prazo = DIA_LIMITE - hoje.day
                    if dias_para_o_prazo < 0:
                        st.error(f"Vencida há {abs(dias_para_o_prazo)} dia(s)!")
                    elif dias_para_o_prazo <= 7:
                        st.warning(f"Vence em {dias_para_o_prazo + 1} dia(s)!")
                    else:
                        st.info(f"Prazo: Dia {DIA_LIMITE}")

                    if st.button("Enviar Folha para Auditoria", use_container_width=True):
                        db_utils.enviar_folha_para_auditoria(obra_logada_id, mes_folha_referencia.strftime('%Y-%m'), st.session_state['obra_logada'])
                        st.rerun()

        st.markdown("---")
        st.header("Ferramentas")
        st.subheader("Backup dos Dados")
        if st.button("📥 Baixar Backup em Excel", use_container_width=True):
            with st.spinner("Gerando backup..."):
                lancamentos_backup = db_utils.get_lancamentos_do_mes(selected_month)
                funcionarios_backup = db_utils.get_funcionarios()
                precos_backup = db_utils.get_precos()
                obras_backup = db_utils.get_obras()
                
                excel_data = utils.to_excel({
                    'Lançamentos': lancamentos_backup,
                    'Funcionários': funcionarios_backup,
                    'Tabela de Preços': precos_backup,
                    'Obras': obras_backup
                })
                st.download_button(
                    label="Clique para baixar o backup",
                    data=excel_data,
                    file_name=f"backup_producao_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            db_utils.registrar_log(st.session_state.get('user_identifier', 'unknown'), "LOGOUT")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.title("Bem-vindo ao Sistema de Produção Lavie!")
    st.markdown("---")
    st.header("Utilize o menu de navegação à esquerda para começar.")

    if st.session_state['role'] == 'admin':
        st.info("Você está logado como **Administrador**. Você tem acesso a todas as páginas de gerenciamento e auditoria.")
    else:
        st.info(f"Você está logado na obra **{st.session_state['obra_logada']}**. Use o menu para lançar a produção ou ver os resumos.")

   

