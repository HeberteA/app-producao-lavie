import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    mes_selecionado = st.session_state.selected_month

    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    funcionarios_df = db_utils.get_funcionarios()
    obras_df = db_utils.get_obras()
    status_df = db_utils.get_status_do_mes(mes_selecionado) 
    folhas_df = db_utils.get_folhas_mensais(mes_selecionado)

    st.header(f"Auditoria de Lançamentos - {mes_selecionado}")

    col_filtro1, col_filtro2 = st.columns(2)
    nomes_obras_disponiveis = sorted(obras_df['NOME DA OBRA'].unique())
    obra_selecionada = col_filtro1.selectbox(
        "1. Selecione a Obra para auditar",
        options=nomes_obras_disponiveis, index=None,
        placeholder="Selecione uma obra...", key="aud_obra_select"
    )
    funcionarios_filtrados = []
    if obra_selecionada:
        funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
        funcionarios_filtrados = col_filtro2.multiselect(
            "2. Filtre por Funcionário (Opcional)",
            options=funcionarios_da_obra, key="aud_func_multiselect"
        )
    if not obra_selecionada:
        st.info("Por favor, selecione uma obra no menu acima para iniciar a auditoria."); st.stop()

    obra_id_selecionada_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id']
    if obra_id_selecionada_info.empty: st.error("Obra selecionada não encontrada."); st.stop()
    obra_id_selecionada = int(obra_id_selecionada_info.iloc[0])

    lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
    funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]

    folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_selecionada]
    status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"
    edicao_bloqueada = status_folha == "Finalizada"

    if edicao_bloqueada: st.success(f"✅ Folha finalizada. Nenhuma edição permitida.")
    elif status_folha == "Enviada para Auditoria": st.info(f"ℹ️ Aguardando auditoria.")

    st.markdown("---")
    st.subheader("Gerenciamento Geral da Obra")

    status_geral_row = status_df[(status_df['obra_id'] == obra_id_selecionada) & (status_df['funcionario_id'] == 0)]
    status_auditoria_interno = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"

    col_status_geral, col_aviso_geral = st.columns(2)

    with col_status_geral:
        st.markdown("##### Status da Obra e Ações")
        utils.display_status_box("Status da Obra", status_auditoria_interno)
        with st.popover("Alterar Status da Obra", disabled=edicao_bloqueada):
            todos_funcionarios_aprovados = True
            folha_foi_enviada = (status_folha == "Enviada para Auditoria") 

            funcionarios_com_producao = lancamentos_obra_df['Funcionário'].unique()

            if len(funcionarios_com_producao) > 0:
                for nome_func in funcionarios_com_producao:
                    id_func_info = funcionarios_df.loc[funcionarios_df['NOME'] == nome_func, 'id']
                    if not id_func_info.empty:
                        id_func = int(id_func_info.iloc[0])
                        status_func_row = status_df[(status_df['funcionario_id'] == id_func) & (status_df['obra_id'] == obra_id_selecionada)]
                        status_do_funcionario = status_func_row['Status'].iloc[0] if not status_func_row.empty else 'A Revisar'
                        if status_do_funcionario != 'Aprovado':
                            todos_funcionarios_aprovados = False
                            break

            status_options = ['A Revisar', 'Analisar']
            pode_aprovar_obra = todos_funcionarios_aprovados and folha_foi_enviada 

            if pode_aprovar_obra:
                status_options.append('Aprovado')
            else: st.info("Opção 'Aprovado' só disponível quando todos ps Funcionários estiverem 'Aprovados'.")
            idx = status_options.index(status_auditoria_interno) if status_auditoria_interno in status_options else 0
            selected_status_obra = st.radio("Defina o status:", options=status_options, index=idx, horizontal=True)
            if st.button("Salvar Status da Obra"):
                if selected_status_obra != status_auditoria_interno:
                    db_utils.upsert_status_auditoria(obra_id_selecionada, 0, mes_selecionado, status=selected_status_obra) # Modificado para usar a função nova
                    st.toast("Status da Obra atualizado!", icon="✅"); st.cache_data.clear(); st.rerun()
        pode_finalizar = status_auditoria_interno == "Aprovado" and status_folha == "Enviada para Auditoria"
        if st.button("Finalizar e Arquivar Folha", use_container_width=True, type="primary", disabled=not pode_finalizar, help="Status interno 'Aprovado' e folha 'Enviada' necessários."):
            mes_dt = pd.to_datetime(mes_selecionado, format='%Y-%m')
            if db_utils.launch_monthly_sheet(obra_id_selecionada, mes_dt, obra_selecionada): st.cache_data.clear(); st.rerun()
        pode_devolver = status_auditoria_interno == "Analisar" and status_folha == "Enviada para Auditoria"
        if st.button("Devolver Folha para Revisão", use_container_width=True, disabled=not pode_devolver, help="Status interno 'Analisar' e folha 'Enviada' necessários."):
            if db_utils.devolver_folha_para_revisao(obra_id_selecionada, mes_selecionado): st.cache_data.clear(); st.rerun()

    with col_aviso_geral:
        st.markdown("##### Status de Envio e Aviso")
        if not folha_do_mes.empty:
            data_envio = pd.to_datetime(folha_do_mes['data_lancamento'].iloc[0]); contador = folha_do_mes['contador_envios'].iloc[0]
            st.info(f"Status: **{status_folha}** | Envios: **{contador}**")
            st.caption(f"Último envio: {data_envio.strftime('%d/%m/%Y às %H:%M')}")
        else: st.warning("⚠️ Aguardando envio da folha.")
        aviso_atual_info = obras_df.loc[obras_df['id'] == obra_id_selecionada, 'aviso']
        aviso_atual = aviso_atual_info.iloc[0] if not aviso_atual_info.empty else ""
        novo_aviso = st.text_area("Aviso para a Obra:", value=aviso_atual or "", key=f"aviso_{obra_selecionada}", help="Aparecerá na sidebar do usuário.")
        if st.button("Salvar Aviso", key=f"btn_aviso_{obra_selecionada}", disabled=edicao_bloqueada):
            if db_utils.save_aviso_data(obra_id_selecionada, novo_aviso): st.toast("Aviso salvo!", icon="✅"); st.cache_data.clear(); st.rerun()

    st.markdown("---")

    if not funcionarios_obra_df.empty:
        producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
        resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
        resumo_df.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True); resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
        if 'Funcionário' in resumo_df.columns: resumo_df = resumo_df.drop(columns=['Funcionário'])
        resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)
        if funcionarios_filtrados: resumo_df = resumo_df[resumo_df['Funcionário'].isin(funcionarios_filtrados)]

        st.subheader("Análise por Funcionário")

        if resumo_df.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:

            for index, row in resumo_df.iterrows():
                with st.container(border=True):
                    funcionario = row['Funcionário']
                    func_id = row['id']

                    header_cols = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1.5]) 
                    header_cols[0].markdown(f"**Funcionário:** {row['Funcionário']} ({row['FUNÇÃO']})")
                    header_cols[1].metric("Salário Base", utils.format_currency(row['SALÁRIO BASE (R$)']))
                    header_cols[2].metric("Produção", utils.format_currency(row['PRODUÇÃO (R$)']))
                    header_cols[3].metric("A Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']))

                    status_func_row = status_df[status_df['funcionario_id'] == func_id]
                    status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"

                    with header_cols[4]:
                        utils.display_status_box("Auditoria", ****status_atual_func)

                    with header_cols[5]:
                        lanc_concluido = status_func_row['Lancamentos Concluidos'].iloc[0] if not status_func_row.empty and 'Lancamentos Concluidos' in status_func_row.columns and pd.notna(status_func_row['Lancamentos Concluidos'].iloc[0]) else False
                        if lanc_concluido:
                            st.success("Lançamento: Concluído")
                        else:
                            st.warning("Lançamento: Pendente")

                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações"):
                        col_status, col_comment = st.columns(2)
                        with col_status:
                            st.markdown("##### Status de Auditoria")
                            status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                            idx_func = status_options_func.index(status_atual_func) if status_atual_func in status_options_func else 0
                            selected_status_func = st.radio("Definir Status:", options=status_options_func, index=idx_func, horizontal=True, key=f"status_{obra_selecionada}_{funcionario}", disabled=edicao_bloqueada)
                            if st.button("Salvar Status", key=f"btn_func_{obra_selecionada}_{funcionario}", disabled=edicao_bloqueada):
                                if selected_status_func != status_atual_func:
                                    db_utils.upsert_status_auditoria(obra_id_selecionada, func_id, mes_selecionado, status=selected_status_func)
                                    st.toast(f"Status de {funcionario} atualizado!", icon="✅"); st.cache_data.clear(); st.rerun()
                        with col_comment:
                            st.markdown("##### Comentário de Auditoria")
                            comment_row = status_df[status_df['funcionario_id'] == func_id]
                            current_comment = comment_row['Comentario'].iloc[0] if not comment_row.empty and pd.notna(comment_row['Comentario'].iloc[0]) else ""
                            new_comment = st.text_area("Adicionar/Editar Comentário:", value=str(current_comment), key=f"comment_{obra_selecionada}_{funcionario}", help="Visível na tela de lançamento.", disabled=edicao_bloqueada)
                            if st.button("Salvar Comentário", key=f"btn_comment_{obra_selecionada}_{funcionario}", disabled=edicao_bloqueada):
                                db_utils.upsert_status_auditoria(obra_id_selecionada, func_id, mes_selecionado, comentario=new_comment)
                                st.toast("Comentário salvo!", icon="💬"); st.cache_data.clear(); st.rerun()
                        st.markdown("---")
                        st.markdown("##### Lançamentos e Observações")
                        lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario].copy()
                        if lancamentos_do_funcionario.empty:
                            st.info("Nenhum lançamento de produção para este funcionário.")
                        else:
                            colunas_visiveis = ['id', 'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
                            edited_df = st.data_editor(lancamentos_do_funcionario[colunas_visiveis], key=f"editor_{obra_selecionada}_{funcionario}", hide_index=True, column_config={"id": None, "Data": st.column_config.DatetimeColumn("Data Lançamento", format="DD/MM/YYYY HH:mm"), "Observação": st.column_config.TextColumn("Observação (Editável)", width="medium")}, disabled=['id', 'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial'])
                            if st.button("Salvar Alterações nas Observações", key=f"save_obs_{obra_selecionada}_{funcionario}", type="primary", disabled=edicao_bloqueada):
                                original_obs = lancamentos_do_funcionario.set_index('id')['Observação']
                                edited_obs = edited_df.set_index('id')['Observação']
                                alteracoes = edited_obs[original_obs != edited_obs]
                                if not alteracoes.empty:
                                    updates_list = [{'id': int(lanc_id), 'obs': nova_obs} for lanc_id, nova_obs in alteracoes.items()]
                                    if db_utils.atualizar_observacoes(updates_list):
                                        st.toast("Observações salvas!", icon="✅"); st.cache_data.clear(); st.rerun()
                                else: st.toast("Nenhuma alteração detectada.", icon="🤷")
