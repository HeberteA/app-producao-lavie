import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    engine = db_utils.get_db_connection()
    if engine is None:
        st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
        st.stop()

    st.header(f"Auditoria de Lançamentos - {st.session_state.selected_month}")
    
    mes_selecionado = st.session_state.selected_month
    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    funcionarios_df = db_utils.get_funcionarios()
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    folhas_df = db_utils.get_folhas(mes_selecionado)
    
 

    col_filtro1, col_filtro2 = st.columns(2)
    nomes_obras_disponiveis = sorted(obras_df['NOME DA OBRA'].unique())
    obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra para auditar", options=nomes_obras_disponiveis, index=None, placeholder="Selecione uma obra...")
    
    funcionarios_filtrados = []
    if obra_selecionada:
        funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
        funcionarios_filtrados = col_filtro2.multiselect("2. Filtre por Funcionário (Opcional)", options=funcionarios_da_obra)
    
    if obra_selecionada:
        obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
        mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)
        
        lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
        funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
        
        status_geral_row = status_df[
            (status_df['obra_id'] == obra_id_selecionada) & 
            (status_df['funcionario_id'] == 0)
        ]
        status_atual_obra = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"
        
        folha_row = folhas_df[(folhas_df['obra_id'] == obra_id_selecionada) & (pd.to_datetime(folhas_df['Mes']).dt.date == mes_selecionado_dt)] 
        status_folha = folha_row['status'].iloc[0] if not folha_row.empty else "Não Enviada"
        
        edicao_bloqueada = status_folha in ['Finalizada']

        if status_folha == "Finalizada":
            st.success(f"✅ A folha para {obra_selecionada} em {mes_selecionado} já foi finalizada. Nenhuma edição é permitida.")
        
        st.markdown("---")
        col_status_geral, col_aviso_geral = st.columns(2)

        with col_status_geral:
            st.markdown("##### Status e Finalização do Mês")
            utils.display_status_box("Status Geral da Folha", status_atual_obra)
            
            with st.popover("Alterar Status", disabled=edicao_bloqueada):
                status_options = ['A Revisar', 'Analisar', 'Aprovado']
                idx = status_options.index(status_atual_obra) if status_atual_obra in status_options else 0
                selected_status_obra = st.radio("Defina um novo status", options=status_options, index=idx, horizontal=True)
                if st.button("Salvar Status da Obra"):
                    if selected_status_obra != status_atual_obra:
                        if db_utils.upsert_status_auditoria(obra_id_selecionada, 0, selected_status_obra, mes_selecionado, ""):
                            st.cache_data.clear()
                            st.rerun()

            if status_folha == 'Devolvida para Revisão':
                st.info("A obra está com a folha para correção. Aguardando reenvio.")

            col1, col2 = st.columns(2)
            with col1:
                is_launch_disabled = (status_atual_obra != 'Aprovado') or (status_folha != 'Enviada para Auditoria')
                if col1.button("Finalizar e Arquivar Folha", type="primary", use_container_width=True, disabled=is_launch_disabled):
                    if db_utils.launch_monthly_sheet(obra_id_selecionada, mes_selecionado_dt, obra_selecionada):
                        st.rerun()
            
            with col2:
                is_devolver_disabled = status_folha != 'Enviada para Auditoria'
                if col2.button("Devolver para Correção", use_container_width=True, disabled=is_devolver_disabled):
                    if db_utils.devolver_folha_para_obra(obra_id_selecionada, mes_selecionado_dt, obra_selecionada):
                        st.rerun()

        with col_aviso_geral:
            st.markdown("##### Status de Envio da Obra")
            if not folha_row.empty:
                data_envio = pd.to_datetime(folha_row['data_lancamento'].iloc[0])
                contador_envios = folha_row['contador_envios'].iloc[0]
                st.info(f"Status: {status_folha} | Enviada em: {data_envio.strftime('%d/%m/%Y')} | Envios: {contador_envios}")
            else:
                st.warning("⚠️ Aguardando o envio da folha pela obra.")
                    
            st.markdown("##### Aviso Geral da Obra")
            aviso_atual = obras_df.loc[obras_df['id'] == obra_id_selecionada, 'aviso'].iloc[0]
            novo_aviso = st.text_area("Aviso para a Obra:", value=aviso_atual, label_visibility="collapsed", disabled=edicao_bloqueada)
            if st.button("Salvar Aviso", disabled=edicao_bloqueada):
                if db_utils.save_aviso_data(obra_selecionada, novo_aviso):
                    st.toast("Aviso salvo com sucesso!", icon="✅")
                    st.cache_data.clear()
                    st.rerun()
        
        producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
        producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
        resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
        if 'PRODUÇÃO (R$)' in resumo_df.columns:
            resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
        else:
            resumo_df['PRODUÇÃO (R$)'] = 0

        if funcionarios_filtrados:
            resumo_df = resumo_df[resumo_df['NOME'].isin(funcionarios_filtrados)]

        st.markdown("---")
        st.subheader("Análise por Funcionário")

        if resumo_df.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            for index, row in resumo_df.iterrows():
                with st.container(border=True):
                    funcionario = row['Funcionário']
                    funcionario_id = int(row['id'])
                    header_cols = st.columns([3, 2, 2, 2, 2])
                    header_cols[0].markdown(f"**Funcionário:** {funcionario} ({row['FUNÇÃO']})")
                    header_cols[1].metric("Salário Base", utils.format_currency(row['SALÁRIO BASE (R$)']))
                    header_cols[2].metric("Produção", utils.format_currency(row['PRODUÇÃO (R$)']))
                    header_cols[3].metric("Salário a Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']))
                
                    status_func_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario)]
                    status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    current_comment = status_func_row['Comentario'].iloc[0] if not status_func_row.empty and pd.notna(status_func_row['Comentario'].iloc[0]) else ""
            
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
