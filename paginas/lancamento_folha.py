import streamlit as st
import pandas as pd
from datetime import datetime, date
import db_utils
import utils

def render_page():
    if st.session_state['role'] != 'user':
        st.error("Acesso negado.")
        st.stop()
   
    mes_selecionado = st.session_state.selected_month
    
    funcionarios_df = db_utils.get_funcionarios()
    precos_df = db_utils.get_precos()
    obras_df = db_utils.get_obras()
    lancamentos_do_mes_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    folhas_df = db_utils.get_folhas(mes_selecionado)

    st.header("Adicionar Novo Lançamento de Produção")
    
    obra_logada = st.session_state['obra_logada']
    obra_logada_id_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'id']
    if obra_logada_id_info.empty:
        st.error("Não foi possível identificar a obra logada. Por favor, faça login novamente.")
        st.stop()
    obra_logada_id = int(obra_logada_id_info.iloc[0])
    
    folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_logada_id]
    status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"

    edicao_bloqueada = status_folha in ['Enviada para Auditoria', 'Finalizada']

    if edicao_bloqueada:
        st.error(f" Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi enviada e está com status '{status_folha}'. Não é possível adicionar novos lançamentos.")
        st.stop()
    else:
        if status_folha == 'Devolvida para Revisão':
            st.warning("Atenção: A folha foi devolvida pela auditoria. Você pode adicionar ou remover lançamentos antes de reenviar.")

        col_form, col_view = st.columns(2)
        with col_form:
            st.markdown(f"##### 📍 Lançamento para a Obra: **{st.session_state['obra_logada']}**")
            with st.container(border=True):
                opcoes_funcionario = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_logada]['NOME'].unique())
                funcionario_selecionado = st.selectbox(
                    "Selecione o Funcionário", 
                    options=opcoes_funcionario, 
                    index=None,
                    placeholder="Selecione um funcionário...",
                    key="lf_func_select"
                )
                
                if funcionario_selecionado:
                    funcao_selecionada = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'FUNÇÃO'].iloc[0]
                    st.metric(label="Função do Colaborador", value=funcao_selecionada)

            st.markdown("##### 🛠️ Selecione o Serviço Principal")
            with st.container(border=True):
                disciplinas = sorted(precos_df['DISCIPLINA'].unique())
                disciplina_selecionada = st.selectbox("Disciplina", options=disciplinas, index=None, placeholder="Selecione...", key="lf_disciplina_select")
                
                opcoes_servico = []
                if disciplina_selecionada:
                    opcoes_servico = sorted(precos_df[precos_df['DISCIPLINA'] == disciplina_selecionada]['DESCRIÇÃO DO SERVIÇO'].unique())
                
                servico_selecionado = st.selectbox("Descrição do Serviço", options=opcoes_servico, index=None, placeholder="Selecione uma disciplina primeiro...", disabled=not disciplina_selecionada, key="lf_servico_select")
                
                quantidade_principal = 0 
                if servico_selecionado:
                    servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                    kpi1, kpi2 = st.columns(2)
                    kpi1.metric(label="Unidade", value=servico_info['UNIDADE'])
                    kpi2.metric(label="Valor Unitário", value=utils.format_currency(servico_info['VALOR']))
                    
                    col_qtd, col_parcial = st.columns(2)
                    with col_qtd:
                        quantidade_principal = st.number_input("Quantidade", min_value=0, step=1, key="lf_qty_principal")
                    with col_parcial:
                        valor_unitario = utils.safe_float(servico_info.get('VALOR'))
                        valor_parcial_servico = quantidade_principal * valor_unitario
                        st.metric(label="Subtotal do Serviço", value=utils.format_currency(valor_parcial_servico))
                    
                    col_data_princ, col_obs_princ = st.columns(2)
                    with col_data_princ:
                        data_servico_principal = st.date_input("Data do Serviço", value=datetime.now(), key="lf_data_principal", format="DD/MM/YYYY")
                    with col_obs_princ:
                        obs_principal = st.text_area("Observação (Opcional)", key="lf_obs_principal")
            
            st.markdown("##### Adicione Itens Diversos")
            with st.expander("📝 Lançar Item Diverso"):
                descricao_diverso = st.text_input("Descrição do Item Diverso", key="lf_desc_diverso")
                
                col_valor_div, col_qtd_div = st.columns(2)
                with col_valor_div:
                    valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="lf_valor_diverso")
                with col_qtd_div:
                    quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="lf_qty_diverso")

                valor_parcial_diverso = quantidade_diverso * valor_diverso
                st.metric(label="Subtotal do Item Diverso", value=utils.format_currency(valor_parcial_diverso))
                
                col_data_div, col_obs_div = st.columns(2)
                with col_data_div:
                    data_servico_diverso = st.date_input("Data do Serviço", value=datetime.now(), key="lf_data_diverso", format="DD/MM/YYYY")
                with col_obs_div:
                    obs_diverso = st.text_area("Observação (Opcional)", key="lf_obs_diverso")

            if st.button("✅ Adicionar Lançamento", use_container_width=True, type="primary", key="lf_add_btn"):
                if not funcionario_selecionado:
                    st.warning("Por favor, selecione um funcionário.")
                else:
                    novos_lancamentos = []
                    agora = datetime.now()

                    func_id_info = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id']
                    if func_id_info.empty:
                        st.error("Funcionário não encontrado no banco de dados.")
                    else:
                        func_id = int(func_id_info.iloc[0])

                        if servico_selecionado and quantidade_principal > 0:
                            servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                            novos_lancamentos.append({
                                'data_servico': data_servico_principal, 'obra_id': obra_logada_id,
                                'funcionario_id': func_id, 'servico_id': int(servico_info['id']),
                                'servico_diverso_descricao': None, 'quantidade': quantidade_principal,
                                'valor
