import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import io
import db_utils
import utils

st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

def login_page(obras_df, acessos_df, engine):
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
                st.session_state['user_identifier'] = 'admin'
                db_utils.registrar_log(engine, 'admin', "LOGIN_SUCCESS")
                st.rerun()
            else:
                db_utils.registrar_log(engine, 'admin', "LOGIN_FAIL", "Senha incorreta.")
                st.error("Senha de administrador incorreta.")
    else:
        obras_com_acesso = pd.merge(obras_df, acessos_df, left_on='id', right_on='obra_id')
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
                        db_utils.registrar_log(engine, f"user:{obra_login}", "LOGIN_SUCCESS")
                        st.rerun()
                    else:
                        db_utils.registrar_log(engine, f"user:{obra_login}", "LOGIN_FAIL", "Código incorreto.")
                        st.error("Obra ou código de acesso incorreto.")
                except IndexError:
                    st.error("Obra ou código de acesso incorreto.")
            else:
                st.warning("Por favor, selecione a obra e insira o código.")

engine = db_utils.get_db_connection()

if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    if engine:
        obras_df_login = db_utils.get_obras(engine)
        acessos_df_login = db_utils.get_acessos(engine)
        login_page(obras_df_login, acessos_df_login, engine)
    else:
        st.error("Falha na conexão com o banco de dados. Verifique as configurações.")
else:
    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = datetime.now().strftime('%Y-%m')
    
    db_utils.garantir_funcionario_geral(engine)

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            obras_df = db_utils.get_obras(engine)
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obra_logada_nome = st.session_state['obra_logada']
            obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada_nome].iloc[0]
            obra_logada_id = obra_info['id']
            aviso_obra = obra_info['Aviso']

        st.markdown("---")
        st.subheader("Mês de Referência")
        
        lancamentos_df = db_utils.get_lancamentos(engine)
        all_months = set()
        if not lancamentos_df.empty:
            all_months.update(pd.to_datetime(lancamentos_df['Data do Serviço']).dt.to_period('M').unique())
        
        current_month_period = pd.Period(datetime.now(), 'M')
        all_months.add(current_month_period)
        
        available_months = sorted([p.strftime('%Y-%m') for p in all_months], reverse=True)
        
        if 'selected_month' not in st.session_state or st.session_state.selected_month not in available_months:
            st.session_state.selected_month = current_month_period.strftime('%Y-%m')

        selected_month_index = available_months.index(st.session_state.selected_month)
        
        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=selected_month_index,
            label_visibility="collapsed"
        )
        if selected_month != st.session_state.selected_month:
            st.session_state.selected_month = selected_month
            st.rerun()

        if st.session_state['role'] == 'user':
            st.markdown("---")
            
            folhas_df = db_utils.get_folhas(engine)

            DIA_LIMITE = 23
            hoje = date.today()
            mes_folha_referencia = hoje.replace(day=1)
            
            st.subheader(f"Folha de {mes_folha_referencia.strftime('%B/%Y')}")

            folha_status_row = folhas_df[
                (folhas_df['obra_id'] == obra_logada_id) &
                (folhas_df['Mes'] == mes_folha_referencia)
            ]

            status_folha = None
            if not folha_status_row.empty:
                status_folha = folha_status_row['status'].iloc[0]

            if status_folha:
                if 'data_lancamento' in folha_status_row and pd.notna(folha_status_row['data_lancamento'].iloc[0]):
                    data_envio = pd.to_datetime(folha_status_row['data_lancamento'].iloc[0])
                    st.info(f"Último envio em: {data_envio.strftime('%d/%m/%Y às %H:%M')}")

                if status_folha == 'Devolvida para Revisão':
                    st.error(f"Status: {status_folha} ⚠️")
                    st.warning("A auditoria solicitou correções. Ajuste os lançamentos e reenvie a folha.")
                    if st.button("Reenviar Folha para Auditoria", use_container_width=True, type="primary"):
                        if db_utils.enviar_folha_para_auditoria(engine, obra_logada_id, mes_folha_referencia.strftime('%Y-%m'), obra_logada_nome):
                            st.rerun()
                elif status_folha == 'Enviada para Auditoria':
                    st.success(f"Status: {status_folha} ✅")
                elif status_folha == 'Finalizada':
                     st.success(f"Status: {status_folha} 🚀")
                else:
                    st.info(f"Status: {status_folha}")
            else:
                dias_para_o_prazo = DIA_LIMITE - hoje.day
                if dias_para_o_prazo < 0:
                    st.error(f"Vencida há {abs(dias_para_o_prazo)} dia(s)!")
                elif dias_para_o_prazo <= 7:
                    st.warning(f"Vence em {dias_para_o_prazo + 1} dia(s)!")
                else:
                    st.info(f"Prazo: Dia {DIA_LIMITE}")

                if st.button("Enviar Folha para Auditoria", use_container_width=True):
                    if db_utils.enviar_folha_para_auditoria(engine, obra_logada_id, mes_folha_referencia.strftime('%Y-%m'), obra_logada_nome):
                        st.rerun()

        st.markdown("---")
        st.header("Ferramentas")
        st.subheader("Backup dos Dados")
        if st.button("📥 Baixar Backup em Excel", use_container_width=True):
            with st.spinner("Gerando backup..."):
                all_lancamentos = db_utils.get_lancamentos(engine)
                all_funcionarios = db_utils.get_funcionarios(engine)
                all_precos = db_utils.get_precos(engine)
                all_obras = db_utils.get_obras(engine)
                
                output = utils.to_excel({
                    'Lançamentos': all_lancamentos,
                    'Funcionários': all_funcionarios,
                    'Tabela de Preços': all_precos,
                    'Obras': all_obras,
                })
                
                st.download_button(
                    label="Clique para baixar o backup",
                    data=output,
                    file_name=f"backup_producao_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            db_utils.registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "LOGOUT")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.success(f"Página Principal - Mês de Referência: {st.session_state.selected_month}")
    st.info("Selecione uma opção no menu à esquerda para começar.")


