import streamlit as st
import pandas as pd
from datetime import datetime, date
import db_utils
import utils

def render_page(engine):
    if st.session_state['role'] != 'user':
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()

    engine = db_utils.get_db_connection()
    if engine is None:
        st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
        st.stop()
    
    mes_selecionado = st.session_state.selected_month
    
    funcionarios_df = db_utils.get_funcionarios(engine)
    precos_df = db_utils.get_precos(engine)
    obras_df = db_utils.get_obras(engine)
    lancamentos_do_mes_df = db_utils.get_lancamentos_do_mes(engine, mes_selecionado)
    status_df = db_utils.get_status_do_mes(engine, mes_selecionado)
    folhas_df = db_utils.get_folhas(engine, mes_selecionado)

    st.header("Adicionar Novo Lançamento de Produção")
    
    obra_logada = st.session_state['obra_logada']
    obra_logada_id = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'id'].iloc[0]
    mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)

    folha_enviada_row = folhas_df[
        (folhas_df['obra_id'] == obra_logada_id) & 
        (pd.to_datetime(folhas_df['Mes']).dt.date == mes_selecionado_dt)
    ]
    
    is_launched = not folha_enviada_row.empty
    status_folha = folha_enviada_row['status'].iloc[0] if is_launched else None

    if is_launched and status_folha not in ['Devolvida para Revisão']:
        st.error(f" Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi enviada e está com status '{status_folha}'. Não é possível adicionar novos lançamentos.")
    else:
        if is_launched and status_folha == 'Devolvida para Revisão':
            st.warning("A folha foi devolvida pela auditoria. Você pode adicionar ou remover lançamentos antes de reenviar.")

        col_form, col_view = st.columns(2)
        with col_form:
            st.markdown(f"##### 📍 Lançamento para a Obra: **{st.session_state['obra_logada']}**")
            with st.container(border=True):
                opcoes_funcionario = funcionarios_df[funcionarios_df['OBRA'] == obra_logada]['NOME'].unique()
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
                    kpi2.metric(label="Valor Unitário", value=utils.format_currency(servico_info['VALOR']))
                    
                    col_qtd, col_parcial = st.columns(2)
                    with col_qtd:
                        quantidade_principal = st.number_input("Quantidade", min_value=0, step=1, key="qty_principal")
                    with col_parcial:
                        valor_unitario = utils.safe_float(servico_info.get('VALOR'))
                        valor_parcial_servico = quantidade_principal * valor_unitario
                        st.metric(label="Subtotal do Serviço", value=utils.format_currency(valor_parcial_servico))
                    
                    col_data_princ, col_obs_princ = st.columns(2)
                    with col_data_princ:
                        data_servico_principal = st.date_input("Data do Serviço", value=date.today(), key="data_principal", format="DD/MM/YYYY")
                    with col_obs_princ:
                        obs_principal = st.text_area("Observação (Obrigatório)", key="obs_principal")
            
            st.markdown("##### Adicione Itens Extras")
            with st.expander("📝 Lançar Item Diverso"):
                descricao_diverso = st.text_input("Descrição do Item Diverso")
                valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="valor_diverso")
                quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="qty_diverso")
                
                col_data_div, col_obs_div = st.columns(2)
                with col_data_div:
                    data_servico_diverso = st.date_input("Data do Serviço", value=date.today(), key="data_diverso", format="DD/MM/YYYY")
                with col_obs_div:
                    obs_diverso = st.text_area("Observação (Obrigatório)", key="obs_diverso")

            if st.button("✅ Adicionar Lançamento", use_container_width=True, type="primary"):
                if not funcionario_selecionado:
                    st.warning("Por favor, selecione um funcionário.")
                else:
                    erros = []
                    if servico_selecionado and quantidade_principal > 0 and not obs_principal.strip():
                        erros.append("Para o Serviço Principal, o campo 'Observação' é obrigatório.")
                    if descricao_diverso and quantidade_diverso > 0 and not obs_diverso.strip():
                        erros.append("Para o Item Diverso, o campo 'Observação' é obrigatório.")
                    
                    if erros:
                        for erro in erros:
                            st.warning(erro)
                    else:
                        novos_lancamentos_dicts = []
                        agora = datetime.now().replace(microsecond=0)
                        
                        if servico_selecionado and quantidade_principal > 0:
                            servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                            valor_unitario = utils.safe_float(servico_info.get('VALOR', 0))
                            novos_lancamentos_dicts.append({
                                'data_servico': data_servico_principal,
                                'obra_id': obra_logada_id, 
                                'funcionario_id': funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id'].iloc[0],
                                'servico_id': servico_info['id'], 
                                'servico_diverso_descricao': None,
                                'quantidade': quantidade_principal, 
                                'valor_unitario': valor_unitario, 
                                'observacao': obs_principal, 
                                'data_lancamento': agora
                            })
                        if descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                            novos_lancamentos_dicts.append({
                                'data_servico': data_servico_diverso,
                                'obra_id': obra_logada_id,
                                'funcionario_id': funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id'].iloc[0],
                                'servico_id': None, 
                                'servico_diverso_descricao': descricao_diverso,
                                'quantidade': quantidade_diverso, 
                                'valor_unitario': valor_diverso, 
                                'observacao': obs_diverso, 
                                'data_lancamento': agora
                            })
   
                        if novos_lancamentos_dicts:
                            if db_utils.salvar_novos_lancamentos(novos_lancamentos_dicts):
                                st.success("Lançamento(s) adicionado(s) com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            st.info("Nenhum serviço ou item com quantidade maior que zero foi adicionado.")
                                
        with col_view:
            if 'funcionario_selecionado' in locals() and funcionario_selecionado:
                st.subheader("Status")
                status_do_funcionario_row = status_df[
                    (status_df['obra_id'] == obra_logada_id) &
                    (status_df['funcionario_id'] == funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id'].iloc[0])
                ]

                status_atual = 'A Revisar'
                comentario_auditoria = ""
                if not status_do_funcionario_row.empty:
                    status_atual = status_do_funcionario_row['Status'].iloc[0]
                    comentario_auditoria = status_do_funcionario_row['Comentario'].iloc[0]

                utils.display_status_box(f"Status de {funcionario_selecionado}", status_atual)
                
                st.markdown("---")
                st.subheader("Comentário da Auditoria")
                if comentario_auditoria and str(comentario_auditoria).strip():
                    st.warning(f"{comentario_auditoria}")
                else:
                    st.info("Nenhum comentário da auditoria.")
                st.markdown("---")

            st.subheader("Histórico Recente na Obra")
            if not lancamentos_do_mes_df.empty:
                lancamentos_da_obra = lancamentos_do_mes_df[lancamentos_do_mes_df['Obra'] == st.session_state['obra_logada']]
                colunas_display = ['Data', 'Funcionário','Disciplina', 'Serviço','Unidade', 'Quantidade','Valor Unitário', 'Valor Parcial', 'Data do Serviço', 'Observação']
                colunas_existentes = [col for col in colunas_display if col in lancamentos_da_obra.columns]

                st.dataframe(lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[colunas_existentes].style.format({
                    'Data': '{:%d/%m/%Y %H:%M:%S}',
                    'Valor Unitário': 'R$ {:,.2f}', 
                    'Valor Parcial': 'R$ {:,.2f}'
                }), use_container_width=True)
            else:
                st.info("Nenhum lançamento adicionado ainda neste mês.")


