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
        
        padding: 16px 12px; 
        
        min-height: 70px;

        border-radius: 6px;
        border-left: 3px solid #444;
        transition: background-color 0.3s;
    }
    .audit-stat-container:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }
    .audit-stat-label {
        font-size: 0.8rem; /* Aumentei levemente a fonte do label */
        text-transform: uppercase;
        color: #A0A0A0;
        margin-bottom: 4px; /* Mais espaço entre titulo e valor */
        font-weight: 600;
    }
    .audit-stat-value {
        font-size: 1.1rem; /* Aumentei levemente a fonte do valor */
        font-weight: 700;
        color: #EEE;
    }
    /* Cores de Destaque */
    .border-blue { border-left-color: #1E88E5 !important; }
    .border-orange { border-left-color: #E37026 !important; }
    .border-green { border-left-color: #328c11 !important; }
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
    funcionarios_df = utils.filtrar_funcionarios_por_mes(funcionarios_df, mes_selecionado)
    
    snapshots_df = db_utils.get_snapshot_salarios(mes_selecionado)
    if not snapshots_df.empty and not funcionarios_df.empty:
        for index, func in funcionarios_df.iterrows():
            folha_obra = folhas_df[folhas_df['obra_id'] == func['obra_id']]
            status_folha_atual = folha_obra['status'].iloc[0] if not folha_obra.empty else "Aberta"
            
            if status_folha_atual != "Aberta":
                snap = snapshots_df[snapshots_df['funcionario_id'] == func['id']]
                if not snap.empty:
                    funcionarios_df.at[index, 'SALARIO_BASE'] = snap['salario_base_na_epoca'].iloc[0]
                    funcionarios_df.at[index, 'FUNÇÃO'] = snap['funcao_na_epoca'].iloc[0]

    st.header(f"Auditoria de Lançamentos - {mes_selecionado}")

    col_filtro1, col_filtro2 = st.columns(2)
    obra_selecionada = col_filtro1.selectbox("Selecione a Obra", options=sorted(obras_df['NOME DA OBRA'].unique()), index=None, placeholder="Selecione...", key="aud_obra_select")
    
    if not obra_selecionada: st.info("Selecione uma obra para começar."); st.stop()

    funcionarios_filtrados_nomes = []
    funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
    funcionarios_filtrados_nomes = col_filtro2.multiselect("Filtrar Funcionário", options=funcionarios_da_obra, key="aud_func_multiselect")

    obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
    lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
    funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
    if funcionarios_filtrados_nomes: funcionarios_obra_df = funcionarios_obra_df[funcionarios_obra_df['NOME'].isin(funcionarios_filtrados_nomes)]
    folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_selecionada]
    status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"
    edicao_bloqueada = status_folha == "Finalizada"


    st.markdown("---")
    st.subheader("Gerenciamento da Obra")

    status_geral_row = status_df[(status_df['obra_id'] == obra_id_selecionada) & (status_df['funcionario_id'] == 0)]
    status_auditoria_interno = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"

    col_status_geral, col_aviso_geral = st.columns(2)
    with col_status_geral:
        st.markdown("##### Ações")
        
        utils.display_status_box("Status da Obra", status_auditoria_interno)
        st.markdown("")
        with st.popover("Alterar Status da Obra", disabled=edicao_bloqueada):
            todos_funcionarios_aprovados = True
            folha_foi_enviada = (status_folha == "Enviada para Auditoria") 

            funcionarios_com_producao_ids = lancamentos_obra_df['funcionario_id'].unique()
            
            if len(funcionarios_com_producao_ids) > 0:
                status_funcionarios_producao = status_df[
                    (status_df['obra_id'] == obra_id_selecionada) &
                    (status_df['funcionario_id'].isin(funcionarios_com_producao_ids))
                ]
                if not status_funcionarios_producao.empty:
                    if not status_funcionarios_producao['Status'].eq('Aprovado').all():
                         todos_funcionarios_aprovados = False
                else:
                    todos_funcionarios_aprovados = False 
            
            pode_aprovar_obra = todos_funcionarios_aprovados and folha_foi_enviada 

            status_options = ['A Revisar', 'Analisar']
            if pode_aprovar_obra:
                status_options.append('Aprovado')
            else: 
                if not todos_funcionarios_aprovados:
                    st.info("Opção 'Aprovado' só disponível quando todos os funcionários com produção estiverem 'Aprovados'.")
                if not folha_foi_enviada:
                     st.info("Opção 'Aprovado' só disponível após a folha ser enviada.")

            idx = status_options.index(status_auditoria_interno) if status_auditoria_interno in status_options else 0
            selected_status_obra = st.radio("Defina o status:", options=status_options, index=idx, horizontal=True)
            if st.button("Salvar Status da Obra"):
                if selected_status_obra != status_auditoria_interno:
                    db_utils.upsert_status_auditoria(obra_id_selecionada, 0, mes_selecionado, status=selected_status_obra) 
                    st.toast("Status da Obra atualizado!", icon="✅"); st.cache_data.clear(); st.rerun()
        st.space("medium")
        pode_finalizar = status_auditoria_interno == "Aprovado" and status_folha == "Enviada para Auditoria"
        if st.button("Finalizar e Arquivar Folha", use_container_width=True, type="primary", disabled=not pode_finalizar, help="Status interno 'Aprovado' e folha 'Enviada' necessários."):
            mes_dt = pd.to_datetime(mes_selecionado, format='%Y-%m')
            if db_utils.launch_monthly_sheet(obra_id_selecionada, mes_dt, obra_selecionada): st.cache_data.clear(); st.rerun()
        
        pode_devolver = status_auditoria_interno == "Analisar" and status_folha == "Enviada para Auditoria"
        if st.button("Devolver Folha para Revisão", use_container_width=True, disabled=not pode_devolver, help="Status interno 'Analisar' e folha 'Enviada' necessários."):
            if db_utils.devolver_folha_para_revisao(obra_id_selecionada, mes_selecionado): st.cache_data.clear(); st.rerun()


    with col_aviso_geral:
        st.markdown("##### Situação")

        if edicao_bloqueada: st.success(f"Folha Finalizada.")
        if not folha_do_mes.empty:
            data_envio = pd.to_datetime(folha_do_mes['data_lancamento'].iloc[0]); contador = folha_do_mes['contador_envios'].iloc[0]
            st.info(f"Status: **{status_folha}** | Envios: **{contador}**")
            st.caption(f"Último envio: {data_envio.strftime('%d/%m/%Y às %H:%M')}")
        else: st.warning("Aguardando envio da folha.")
            
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

        for _, row in resumo_df.iterrows():
            with st.container(border=True):
                funcionario_nome = row['Funcionário'] 
                
                c_info, c_stat = st.columns([5, 2])
                
                with c_info:
                    st.markdown(f"### {funcionario_nome} <span style='color:#E37026; font-size:0.8em'>| {row['FUNÇÃO']}</span>", unsafe_allow_html=True)
                    
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1: st.markdown(make_audit_stat("Sal. Base", utils.format_currency(row['SALÁRIO BASE (R$)']), "#FFFFFF"), unsafe_allow_html=True)
                    with c2: st.markdown(make_audit_stat("Prod. Bruta", utils.format_currency(row['PRODUÇÃO BRUTA (R$)']), "border-orange"), unsafe_allow_html=True)
                    with c3: st.markdown(make_audit_stat("Prod. Líquida", utils.format_currency(row['PRODUÇÃO LÍQUIDA (R$)']), "border-blue"), unsafe_allow_html=True)
                    with c4: st.markdown(make_audit_stat("Gratificações", utils.format_currency(row['TOTAL GRATIFICAÇÕES (R$)']), "border-purple"), unsafe_allow_html=True)
                    with c5: st.markdown(make_audit_stat("A Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']), "border-green"), unsafe_allow_html=True)

                with c_stat:
                    st.caption("Status Auditoria")
                    status_func_row = status_df[(status_df['funcionario_id'] == row['id']) & (status_df['obra_id'] == obra_id_selecionada)]
                    status_f = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    
                    utils.display_status_box("Status", status_f)
                    
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
                        idx_func = status_options_func.index(status_f) if status_f in status_options_func else 0
                        
                        selected_status_func = st.radio("Definir Status:", options=status_options_func, index=idx_func, horizontal=True, key=f"status_{obra_selecionada}_{funcionario_nome}", disabled=edicao_bloqueada)
                        
                        if st.button("Salvar Status", key=f"btn_func_{obra_selecionada}_{funcionario_nome}", disabled=edicao_bloqueada):
                            if selected_status_func != status_f:
                                db_utils.upsert_status_auditoria(obra_id_selecionada, row['id'], mes_selecionado, status=selected_status_func)
                                st.toast(f"Status de {funcionario_nome} atualizado!", icon="✅"); st.cache_data.clear(); st.rerun()
                    
                    with col_comment:
                        st.markdown("##### Comentário de Auditoria")
                        comment_row = status_df[(status_df['funcionario_id'] == row['id']) & (status_df['obra_id'] == obra_id_selecionada)]
                        curr_comment = comment_row['Comentario'].iloc[0] if not comment_row.empty and pd.notna(comment_row['Comentario'].iloc[0]) else ""
                        new_comment = st.text_area("Observação:", value=curr_comment, key=f"comm_{row['id']}", disabled=edicao_bloqueada, height=100)
                    
                        if not edicao_bloqueada:
                            if st.button("Salvar Comentário", key=f"b_comm_{row['id']}"):
                                db_utils.upsert_status_auditoria(obra_id_selecionada, row['id'], mes_selecionado, comentario=new_comment)
                                st.toast("Comentário salvo!", icon="💬")
                                st.rerun()
                    
                    st.markdown("---")
                    st.markdown("##### Lançamentos e Observações")
                    lancs_f = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario_nome].copy()
                
                    if not lancs_f.empty:
                        cols_bloqueadas = ['id', 'Data do Serviço', 'Serviço', 'Quantidade', 'Valor Parcial']
                        disabled_config = True if edicao_bloqueada else cols_bloqueadas
                    
                        edited_df = st.data_editor(
                            lancs_f[['id', 'Data do Serviço', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação']], 
                            key=f"ed_{row['id']}", 
                            disabled=disabled_config, 
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Valor Parcial": st.column_config.NumberColumn(format="R$ %.2f"),
                                "Data do Serviço": st.column_config.DateColumn(format="DD/MM/YYYY")
                            }
                        )
                    
                        if not edicao_bloqueada:
                            if st.button("Salvar Alterações nas Observações", key=f"save_obs_{row['id']}", type="primary"):
                                try:
                                    original_obs = lancs_f.set_index('id')['Observação'].fillna('') 
                                    edited_obs = edited_df.set_index('id')['Observação'].fillna('') 
                                    alteracoes = edited_obs[original_obs != edited_obs]
                                
                                    if not alteracoes.empty:
                                        updates_list = [{'id': int(lanc_id), 'obs': str(nova_obs)} for lanc_id, nova_obs in alteracoes.items()]
                                        if db_utils.atualizar_observacoes(updates_list):
                                            st.toast("Observações salvas!", icon="✅"); st.cache_data.clear(); st.rerun()
                                    else: 
                                        st.toast("Nenhuma alteração detectada.", icon="🤷")
                                except Exception as e:
                                        st.error(f"Erro: {e}")
                    else: 
                        st.info("Sem lançamentos.")
