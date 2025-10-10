import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    engine = db_utils.get_db_connection()
    if engine is None:
        st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
        st.stop()

    mes_selecionado = st.session_state.selected_month
    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    funcionarios_df = db_utils.get_funcionarios()
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    folhas_df = db_utils.get_folhas(mes_selecionado)

    st.header(f"Auditoria de Lançamentos - {st.session_state.selected_month}")
    
    col_filtro1, col_filtro2 = st.columns(2)
    nomes_obras_disponiveis = sorted(obras_df['NOME DA OBRA'].unique())
    obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra para auditar", options=nomes_obras_disponiveis, index=None, placeholder="Selecione uma obra...")
    
    funcionarios_filtrados = []
    if obra_selecionada:
        funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
        funcionarios_filtrados = col_filtro2.multiselect("2. Filtre por Funcionário (Opcional)", options=funcionarios_da_obra)
    
    if obra_selecionada:
        obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
        lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
        funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
        
        folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_selecionada]
        status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"

        edicao_bloqueada = status_folha in ["Finalizada", "Enviada para Auditoria"]
        if edicao_bloqueada:
            st.success(f"✅ A folha para {obra_selecionada} em {mes_selecionado} está com status '{status_folha}'. Nenhuma edição é permitida.")

        st.markdown("---")
        
        if not funcionarios_obra_df.empty:
            producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
            producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
            
            resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            
            if 'Funcionário' in resumo_df.columns:
                resumo_df = resumo_df.drop(columns=['Funcionário'])

            resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
            
            resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

            if funcionarios_filtrados:
                resumo_df = resumo_df[resumo_df['Funcionário'].isin(funcionarios_filtrados)]
            
            total_producao_obra = resumo_df['PRODUÇÃO (R$)'].sum()
            num_funcionarios = len(resumo_df)

            col1, col2 = st.columns(2)
            col1.metric("Produção Total da Obra", f"R$ {total_producao_obra:,.2f}")
            col2.metric("Nº de Funcionários", num_funcionarios)
        
            st.markdown("---")
            st.subheader("Análise por Funcionário")

            if resumo_df.empty:
                st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
            else:
                for index, row in resumo_df.iterrows():
                    with st.container(border=True):
                        funcionario = row['Funcionário']
                        func_id = row['id']
                        
                        header_cols = st.columns([3, 2, 2, 2, 2])
                        header_cols[0].markdown(f"**Funcionário:** {row['Funcionário']} ({row['FUNÇÃO']})")
                        header_cols[1].metric("Salário Base", utils.format_currency(row['SALÁRIO BASE (R$)']))
                        header_cols[2].metric("Produção", utils.format_currency(row['PRODUÇÃO (R$)']))
                        header_cols[3].metric("Salário a Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']))
                        
                        status_func_row = status_df[(status_df['funcionario_id'] == func_id)]
                        status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    
                    with header_cols[4]:
                        utils.display_status_box("Status", status_atual_func)

                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações"):
                    col_status, col_comment = st.columns(2)
                    with col_status:
                        st.markdown("##### Status do Funcionário")
                        status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                        idx_func = status_options_func.index(status_atual_func)
                        selected_status_func = st.radio("Definir Status:", options=status_options_func, index=idx_func, horizontal=True, key=f"status_{funcionario_id}", disabled=edicao_bloqueada)
                        if st.button("Salvar Status do Funcionário", key=f"btn_func_{funcionario_id}", disabled=edicao_bloqueada):
                            if db_utils.upsert_status_auditoria(engine, obra_id_selecionada, funcionario_id, selected_status_func, mes_selecionado, funcionario, obra_selecionada, current_comment):
                                st.cache_data.clear()
                                st.rerun()
                                
                    with col_comment:
                        st.markdown("##### Comentário de Auditoria")
                        new_comment = st.text_area("Adicionar/Editar Comentário:", value=current_comment, key=f"comment_{funcionario_id}", label_visibility="collapsed", disabled=edicao_bloqueada)
                        if st.button("Salvar Comentário", key=f"btn_comment_{funcionario_id}", disabled=edicao_bloqueada):
                            if db_utils.upsert_status_auditoria(engine, obra_id_selecionada, funcionario_id, status_atual_func, mes_selecionado, funcionario, obra_selecionada, new_comment):
                                st.toast("Comentário salvo!", icon="💬")
                                st.cache_data.clear()
                                st.rerun()
                                    
                    st.markdown("---")
                    st.markdown("##### Lançamentos e Observações")
                    lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario].copy()
                    if lancamentos_do_funcionario.empty:
                        st.info("Nenhum lançamento para este funcionário.")
                    else:
                        edited_df = st.data_editor(
                            lancamentos_do_funcionario,
                            key=f"editor_{funcionario_id}",
                            hide_index=True,
                            disabled=['id', 'Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial'],
                            column_config={ "id": None, "Observação": st.column_config.TextColumn(width="medium") }
                        )
                        if not edited_df.equals(lancamentos_do_funcionario):
                            if st.button("Salvar Observações", key=f"save_obs_{funcionario_id}", type="primary", disabled=edicao_bloqueada):
                                original_obs = lancamentos_do_funcionario.set_index('id')['Observação']
                                edited_obs = edited_df.set_index('id')['Observação']
                                alteracoes = edited_obs[original_obs != edited_obs]
                                if not alteracoes.empty:
                                    updates_list = [{'id': lanc_id, 'obs': nova_obs} for lanc_id, nova_obs in alteracoes.items()]
                                    if db_utils.atualizar_observacoes(engine, updates_list):
                                        st.toast("Observações salvas!", icon="✅")
                                        st.cache_data.clear()
                                        st.rerun()
