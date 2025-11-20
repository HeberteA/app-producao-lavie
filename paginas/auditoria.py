import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    st.markdown("""
    <style>
    .audit-stat-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        background-color: rgba(255, 255, 255, 0.05);
        padding: 8px 12px;
        border-radius: 6px;
        border-left: 3px solid #444;
        transition: background-color 0.3s;
    }
    .audit-stat-container:hover {
        background-color: rgba(255, 255, 255, 0.1);
        weight: 100;
    }
    .audit-stat-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        color: #A0A0A0;
        margin-bottom: 2px;
        font-weight: 600;
    }
    .audit-stat-value {
        font-size: 1rem;
        font-weight: 700;
        color: #EEE;
    }
    /* Cores de Destaque */
    .border-blue { border-left-color: #3b82f6 !important; }
    .border-orange { border-left-color: #E37026 !important; }
    .border-green { border-left-color: #10b981 !important; }
    .border-purple { border-left-color: #8b5cf6 !important; }
    </style>
    """, unsafe_allow_html=True)

    def make_audit_stat(label, value, color_class=""):
        return f"""
        <div class="audit-stat-container {color_class}">
            <div class="audit-stat-label">{label}</div>
            <div class="audit-stat-value">{value}</div>
        </div>
        """

    mes_selecionado = st.session_state.selected_month

    @st.cache_data
    def get_audit_data(mes):
        return db_utils.get_lancamentos_do_mes(mes), db_utils.get_funcionarios(), db_utils.get_obras(), db_utils.get_status_do_mes(mes), db_utils.get_folhas_mensais(mes)

    lancamentos_df, funcionarios_df, obras_df, status_df, folhas_df = get_audit_data(mes_selecionado)

    st.header(f"Auditoria de Lançamentos - {mes_selecionado}")

    col_filtro1, col_filtro2 = st.columns(2)
    obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra", options=sorted(obras_df['NOME DA OBRA'].unique()), index=None, placeholder="Selecione...", key="aud_obra_select")
    
    if not obra_selecionada: st.info("Selecione uma obra para começar."); st.stop()

    funcionarios_filtrados_nomes = []
    funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
    funcionarios_filtrados_nomes = col_filtro2.multiselect("2. Filtrar Funcionário (Opcional)", options=funcionarios_da_obra, key="aud_func_multiselect")

    obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
    lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
    funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
    if funcionarios_filtrados_nomes: funcionarios_obra_df = funcionarios_obra_df[funcionarios_obra_df['NOME'].isin(funcionarios_filtrados_nomes)]

    folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_selecionada]
    status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"
    edicao_bloqueada = status_folha == "Finalizada"

    if edicao_bloqueada: st.success(f"Folha Finalizada.")
    elif status_folha == "Enviada para Auditoria": st.info(f"Aguardando Auditoria.")
    elif status_folha == 'Devolvida para Revisão': st.warning("Devolvida para Revisão.")

    st.markdown("---")
    st.subheader("Gerenciamento da Obra")

    status_geral_row = status_df[(status_df['obra_id'] == obra_id_selecionada) & (status_df['funcionario_id'] == 0)]
    status_auditoria_interno = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"

    col_status_geral, col_aviso_geral = st.columns(2)
    with col_status_geral:
        st.markdown("##### Ações")
        with st.popover("Alterar Status Obra", disabled=edicao_bloqueada):
            status_options = ['A Revisar', 'Analisar', 'Aprovado']
            selected_status_obra = st.radio("Novo Status:", options=status_options, index=status_options.index(status_auditoria_interno) if status_auditoria_interno in status_options else 0)
            if st.button("Salvar Status Obra"):
                db_utils.upsert_status_auditoria(obra_id_selecionada, 0, mes_selecionado, status=selected_status_obra) 
                st.toast("Salvo!", icon="✅"); st.cache_data.clear(); st.rerun()
        utils.display_status_box("Status Obra", status_auditoria_interno)
        if st.button("Finalizar Folha", use_container_width=True, type="primary", disabled=not (status_auditoria_interno == "Aprovado" and status_folha == "Enviada para Auditoria")):
            if db_utils.launch_monthly_sheet(obra_id_selecionada, pd.to_datetime(mes_selecionado, format='%Y-%m'), obra_selecionada): st.cache_data.clear(); st.rerun()
        if st.button("Devolver para Revisão", use_container_width=True, disabled=not (status_auditoria_interno == "Analisar" and status_folha == "Enviada para Auditoria")):
            if db_utils.devolver_folha_para_revisao(obra_id_selecionada, mes_selecionado): st.cache_data.clear(); st.rerun()

    with col_aviso_geral:
        st.markdown("##### Avisos")
        aviso_val = obras_df.loc[obras_df['id'] == obra_id_selecionada, 'aviso'].iloc[0]
        novo_aviso = st.text_area("Aviso aos Engenheiros:", value=aviso_val if pd.notna(aviso_val) else "", key=f"aviso_{obra_selecionada}")
        if st.button("Salvar Aviso"):
             db_utils.save_aviso_data(obra_id_selecionada, novo_aviso); st.toast("Salvo!"); st.cache_data.clear(); st.rerun()

    st.markdown("---")

    if not funcionarios_obra_df.empty:
        funcionarios_obra_df['SALARIO_BASE'] = funcionarios_obra_df['SALARIO_BASE'].apply(utils.safe_float)
        
        producao_bruta_df = pd.DataFrame()
        total_gratificacoes_df = pd.DataFrame()

        if not lancamentos_obra_df.empty:
            lancamentos_obra_df['Valor Parcial'] = lancamentos_obra_df['Valor Parcial'].apply(utils.safe_float)
            
            lanc_producao = lancamentos_obra_df[lancamentos_obra_df['Disciplina'] != 'GRATIFICAÇÃO']
            if not lanc_producao.empty:
                producao_bruta_df = lanc_producao.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                producao_bruta_df.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
            
            lanc_gratificacoes = lancamentos_obra_df[lancamentos_obra_df['Disciplina'] == 'GRATIFICAÇÃO']
            if not lanc_gratificacoes.empty:
                total_gratificacoes_df = lanc_gratificacoes.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
                total_gratificacoes_df.rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'}, inplace=True)

        resumo_df = funcionarios_obra_df.copy()
        
        if not producao_bruta_df.empty:
            resumo_df = pd.merge(resumo_df, producao_bruta_df, left_on='id', right_on='funcionario_id', how='left')
            if 'funcionario_id' in resumo_df.columns: resumo_df.drop(columns=['funcionario_id'], inplace=True)
        else:
            resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0
            
        if not total_gratificacoes_df.empty:
             resumo_df = pd.merge(resumo_df, total_gratificacoes_df, left_on='id', right_on='funcionario_id', how='left', suffixes=('', '_grat'))
             if 'funcionario_id_grat' in resumo_df.columns: resumo_df.drop(columns=['funcionario_id_grat'], inplace=True)
             if 'funcionario_id' in resumo_df.columns and 'id' in resumo_df.columns and 'funcionario_id' != 'id': resumo_df.drop(columns=['funcionario_id'], inplace=True)
        else:
             resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = 0.0
        resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
        resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = resumo_df['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0)

        resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

        st.subheader("Análise por Funcionário")

        if resumo_df.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            for index, row in resumo_df.iterrows():
                with st.container(border=True):
                    funcionario_nome = row['Funcionário']
                    func_id = row['id']

                    col_header_info, col_header_status = st.columns([5, 2])
                    
                    with col_header_info:
                        st.markdown(f"### {funcionario_nome} <span style='color:#E37026; font-size:0.8em'>| {row['FUNÇÃO']}</span>", unsafe_allow_html=True)
                        
                        c1, c2, c3, c4, c5 = st.columns(5)
                        with c1: st.markdown(make_audit_stat("Sal. Base", utils.format_currency(row['SALÁRIO BASE (R$)'])), unsafe_allow_html=True)
                        with c2: st.markdown(make_audit_stat("Prod. Bruta", utils.format_currency(row['PRODUÇÃO BRUTA (R$)']), "border-orange"), unsafe_allow_html=True)
                        with c3: st.markdown(make_audit_stat("Prod. Líquida", utils.format_currency(row['PRODUÇÃO LÍQUIDA (R$)']), "border-blue"), unsafe_allow_html=True)
                        with c4: st.markdown(make_audit_stat("Gratificações", utils.format_currency(row['TOTAL GRATIFICAÇÕES (R$)']), "border-purple"), unsafe_allow_html=True)
                        with c5: st.markdown(make_audit_stat("A Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']), "border-green"), unsafe_allow_html=True)

                    status_func_row = status_df[(status_df['funcionario_id'] == func_id) & (status_df['obra_id'] == obra_id_selecionada)] 
                    status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"

                    with col_header_status:
                        st.caption("Status Auditoria")
                        utils.display_status_box("Status", status_atual_func)
                        
                        lanc_concluido = status_func_row['Lancamentos Concluidos'].iloc[0] if not status_func_row.empty and 'Lancamentos Concluidos' in status_func_row.columns and pd.notna(status_func_row['Lancamentos Concluidos'].iloc[0]) else False
                        if lanc_concluido:
                            st.success("Lançamentos: OK") 
                        else:
                            st.warning("Lançamentos: Pendente")

                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações"):
                        col_status, col_comment = st.columns(2)
                        with col_status:
                            st.markdown("##### Status de Auditoria")
                            status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                            idx_func = status_options_func.index(status_atual_func) if status_atual_func in status_options_func else 0
                            selected_status_func = st.radio("Definir Status:", options=status_options_func, index=idx_func, horizontal=True, key=f"status_{obra_selecionada}_{funcionario_nome}", disabled=edicao_bloqueada)
                            if st.button("Salvar Status", key=f"btn_func_{obra_selecionada}_{funcionario_nome}", disabled=edicao_bloqueada):
                                if selected_status_func != status_atual_func:
                                    db_utils.upsert_status_auditoria(obra_id_selecionada, func_id, mes_selecionado, status=selected_status_func)
                                    st.toast(f"Status de {funcionario_nome} atualizado!", icon="✅"); st.cache_data.clear(); st.rerun()
                        with col_comment:
                            st.markdown("##### Comentário de Auditoria")
                            comment_row = status_df[(status_df['funcionario_id'] == func_id) & (status_df['obra_id'] == obra_id_selecionada)] 
                            current_comment = comment_row['Comentario'].iloc[0] if not comment_row.empty and pd.notna(comment_row['Comentario'].iloc[0]) else ""
                            new_comment = st.text_area("Adicionar/Editar Comentário:", value=str(current_comment), key=f"comment_{obra_selecionada}_{funcionario_nome}", help="Visível na tela de lançamento.", disabled=edicao_bloqueada)
                            if st.button("Salvar Comentário", key=f"btn_comment_{obra_selecionada}_{funcionario_nome}", disabled=edicao_bloqueada):
                                db_utils.upsert_status_auditoria(obra_id_selecionada, func_id, mes_selecionado, comentario=new_comment)
                                st.toast("Comentário salvo!", icon="💬"); st.cache_data.clear(); st.rerun()
                        
                        st.markdown("---")
                        st.markdown("##### Lançamentos e Observações")
                        lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario_nome].copy()
                        if lancamentos_do_funcionario.empty:
                            st.info("Nenhum lançamento de produção para este funcionário.")
                        else:
                            colunas_visiveis_lanc = ['id', 'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
                            
                            edited_df = st.data_editor(
                                lancamentos_do_funcionario[colunas_visiveis_lanc], 
                                key=f"editor_{obra_selecionada}_{funcionario_nome}", 
                                hide_index=True, 
                                column_config={
                                    "id": None, 
                                    "Data": st.column_config.DatetimeColumn("Data Lançamento", format="DD/MM/YYYY HH:mm"), 
                                    "Data do Serviço": st.column_config.DateColumn("Data Serviço", format="DD/MM/YYYY"),
                                    "Observação": st.column_config.TextColumn("Observação (Editável)", width="medium"),
                                    "Quantidade": st.column_config.NumberColumn(format="%.2f"),
                                    "Valor Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
                                    "Valor Parcial": st.column_config.NumberColumn(format="R$ %.2f")
                                }, 
                                disabled=['id', 'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial'] 
                            )
                            
                            if st.button("Salvar Alterações nas Observações", key=f"save_obs_{obra_selecionada}_{funcionario_nome}", type="primary", disabled=edicao_bloqueada):
                                try:
                                    original_obs = lancamentos_do_funcionario.set_index('id')['Observação'].fillna('') 
                                    edited_obs = edited_df.set_index('id')['Observação'].fillna('') 
                                    alteracoes = edited_obs[original_obs != edited_obs]
                                    
                                    if not alteracoes.empty:
                                        updates_list = [{'id': int(lanc_id), 'obs': str(nova_obs)} for lanc_id, nova_obs in alteracoes.items()]
                                        if db_utils.atualizar_observacoes(updates_list):
                                            st.toast("Observações salvas!", icon="✅"); st.cache_data.clear(); st.rerun()
                                    else: 
                                        st.toast("Nenhuma alteração detectada.", icon="🤷")
                                except Exception as e:
                                     st.error(f"Erro ao processar alterações: {e}")

    else:
         st.info("Nenhum funcionário encontrado para a obra selecionada ou filtros aplicados.")
