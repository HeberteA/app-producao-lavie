import streamlit as st
import pandas as pd
from datetime import datetime, date
import db_utils
import utils

if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.error("Por favor, faça o login primeiro na página principal.")
    st.stop()

if st.session_state['role'] != 'user':
    st.error("Você não tem permissão para acessar esta página.")
    st.stop()

engine = db_utils.get_db_connection()
if engine is None:
    st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
    st.stop()

funcionarios_df = db_utils.get_funcionarios(engine)
precos_df = db_utils.get_precos(engine)
obras_df = db_utils.get_obras(engine)
lancamentos_df = db_utils.get_lancamentos_do_mes(engine, st.session_state.selected_month)
status_df = db_utils.get_status_do_mes(engine, st.session_state.selected_month)
folhas_df = db_utils.get_folhas(engine)

st.header("Adicionar Novo Lançamento de Produção")

obra_logada = st.session_state['obra_logada']
mes_selecionado = st.session_state.selected_month
obra_logada_id = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'id'].iloc[0]
mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)
folha_do_mes_row = folhas_df[(folhas_df['obra_id'] == obra_logada_id) & (folhas_df['Mes'] == mes_selecionado_dt)]

status_folha = None
if not folha_do_mes_row.empty:
    status_folha = folha_do_mes_row['status'].iloc[0]

if status_folha in ['Enviada para Auditoria', 'Finalizada']:
    st.error(f" Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi enviada ou finalizada. Não é possível adicionar ou alterar lançamentos.")
else:
    col_form, col_view = st.columns(2)
    with col_form:
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
                    agora = datetime.now()
                    data_de_hoje = date.today()
                    obra_selecionada_nome = st.session_state['obra_logada']
                    if servico_selecionado and quantidade_principal > 0:
                        servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                        valor_unitario = utils.safe_float(servico_info.get('VALOR', 0))
                        novos_lancamentos_dicts.append({
                            'data_servico': data_servico_principal if data_servico_principal else data_de_hoje,
                            'obra_nome': obra_selecionada_nome, 'funcionario_nome': funcionario_selecionado,
                            'servico_id': servico_info['id'], 'servico_diverso_descricao': None,
                            'quantidade': quantidade_principal, 'valor_unitario': valor_unitario, 'observacao': obs_principal, 'data_lancamento': agora, 'servico_nome': servico_selecionado
                        })
                    if descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                        novos_lancamentos_dicts.append({
                            'data_servico': data_servico_diverso if data_servico_diverso else data_de_hoje,
                            'obra_nome': obra_selecionada_nome, 'funcionario_nome': funcionario_selecionado,
                            'servico_id': None, 'servico_diverso_descricao': descricao_diverso,
                            'quantidade': quantidade_diverso, 'valor_unitario': valor_diverso, 'observacao': obs_diverso, 'data_lancamento': agora, 'servico_nome': descricao_diverso
                        })

                    if novos_lancamentos_dicts:
                        df_para_salvar = pd.DataFrame(novos_lancamentos_dicts)
                        obra_id_map = obras_df.set_index('NOME DA OBRA')['id']
                        func_id_map = funcionarios_df.set_index('NOME')['id']

                        df_para_salvar['obra_id'] = df_para_salvar['obra_nome'].map(obra_id_map)
                        df_para_salvar['funcionario_id'] = df_para_salvar['funcionario_nome'].map(func_id_map)
                        colunas_db = [
                            'data_servico', 'obra_id', 'funcionario_id', 'servico_id',
                            'servico_diverso_descricao', 'quantidade',
                            'valor_unitario', 'observacao', 'data_lancamento'
                        ]
                        df_final_para_db = df_para_salvar[colunas_db]
                        df_final_para_db['servico_id'] = df_final_para_db['servico_id'].astype('Int64')

                        if db_utils.salvar_novos_lancamentos(df_final_para_db, engine):
                            st.success("Lançamento(s) adicionado(s) com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.info("Nenhum serviço ou item com quantidade maior que zero foi adicionado.")
                            
    with col_view:
        if 'funcionario_selecionado' in locals() and funcionario_selecionado:
            st.subheader("Status")
            status_do_funcionario_row = status_df[
                (status_df['Obra'] == obra_logada) &
                (status_df['Funcionario'] == funcionario_selecionado)
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
                st.warning(f"Comentário: {comentario_auditoria}")
            else:
                st.info("Nenhum comentário da auditoria para este funcionário no mês.")

            st.markdown("---")

        st.subheader("Histórico Recente na Obra")
        lancamentos_da_obra = lancamentos_df[lancamentos_df['Obra'] == st.session_state['obra_logada']]
        if not lancamentos_da_obra.empty:
            colunas_display = ['Data', 'Funcionário','Disciplina', 'Serviço','Unidade', 'Quantidade','Valor Unitário', 'Valor Parcial', 'Data do Serviço', 'Observação']
            st.dataframe(lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[colunas_display].style.format({'Valor Unitário': 'R$ {:,.2f}', 'Valor Parcial': 'R$ {:,.2f}'}), use_container_width=True)
        else:
            st.info("Nenhum lançamento adicionado ainda neste mês.")

