import streamlit as st
import pandas as pd
from datetime import datetime, date, timezone, timedelta 
import db_utils
import utils

def render_page():
    if st.session_state['role'] != 'user':
        st.error("Acesso negado.")
        st.stop()
   
    st.markdown("""
    <style>
        /* Estilo geral dos cards */
        .stContainer {
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        /* Destaque para valores monetários (Subtotais) */
        .subtotal-box {
            background-color: rgba(46, 125, 50, 0.1);
            border: 1px solid rgba(46, 125, 50, 0.3);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        }
        .subtotal-label {
            font-size: 0.8rem;
            color: #a0a0a0;
            text-transform: uppercase;
            margin-bottom: 0;
        }
        .subtotal-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: #4caf50; /* Verde Material Design */
        }

        /* Melhoria nos Expanders */
        .streamlit-expanderHeader {
            font-weight: 600;
            background-color: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
        }
        
        /* Header de Seção */
        .section-header {
            font-size: 1.1rem;
            font-weight: 600;
            color: #e0e0e0;
            margin-top: 20px;
            margin-bottom: 10px;
            border-left: 4px solid #E37026;
            padding-left: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

    mes_selecionado = st.session_state.selected_month
    
    @st.cache_data
    def get_launch_page_data(mes):
        funcionarios_df = db_utils.get_funcionarios()
        precos_df = db_utils.get_precos()
        obras_df = db_utils.get_obras()
        lancamentos_do_mes_df = db_utils.get_lancamentos_do_mes(mes)
        status_df = db_utils.get_status_do_mes(mes)
        folhas_df = db_utils.get_folhas_mensais(mes) 
        return funcionarios_df, precos_df, obras_df, lancamentos_do_mes_df, status_df, folhas_df

    funcionarios_df, precos_df, obras_df, lancamentos_do_mes_df, status_df, folhas_df = get_launch_page_data(mes_selecionado)

    if 'current_month_for_concluded' not in st.session_state or st.session_state.current_month_for_concluded != mes_selecionado:
        st.session_state.current_month_for_concluded = mes_selecionado

    st.header(f"Lançamentos de Produção • {mes_selecionado}")
    
    obra_logada = st.session_state['obra_logada']
    obra_logada_id_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'id']
    if obra_logada_id_info.empty:
        st.error("Não foi possível identificar a obra logada. Por favor, faça login novamente.")
        st.stop()
    obra_logada_id = int(obra_logada_id_info.iloc[0])
    
    try:
        mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)
    except Exception:
        mes_selecionado_dt = date.today().replace(day=1) 

    folha_do_mes = folhas_df[
        (folhas_df['obra_id'] == obra_logada_id) &
        (folhas_df['Mes'] == mes_selecionado_dt)
    ]
    status_folha = folha_do_mes['status'].iloc[0] if not folha_do_mes.empty else "Não Enviada"

    edicao_bloqueada = status_folha in ['Enviada para Auditoria', 'Finalizada']

    if edicao_bloqueada:
        st.error(f"Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi enviada ({status_folha}). Não é possível adicionar novos lançamentos.")
        st.stop()
    else:
        if status_folha == 'Devolvida para Revisão':
            st.warning("Atenção: A folha foi devolvida pela auditoria. Você pode adicionar ou remover lançamentos antes de reenviar.")

        col_form, col_view = st.columns([2, 1], gap="large") 
        
        with col_form:
            st.markdown(f"<div class='section-header'>Obra Ativa: {st.session_state['obra_logada']}</div>", unsafe_allow_html=True)
            
            with st.container(border=True):
                funcionarios_da_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_logada].copy()
                
                status_conclusao_df = status_df[
                    (status_df['obra_id'] == obra_logada_id) & (status_df['funcionario_id'] != 0)
                ][['funcionario_id', 'Lancamentos Concluidos']].fillna(False)

                funcionarios_status_df = pd.merge(
                    funcionarios_da_obra_df, status_conclusao_df,
                    left_on='id', right_on='funcionario_id', how='left'
                ).fillna({'Lancamentos Concluidos': False})

                pendentes_df = funcionarios_status_df[~funcionarios_status_df['Lancamentos Concluidos']]
                concluidos_df = funcionarios_status_df[funcionarios_status_df['Lancamentos Concluidos']]
                
                pendentes = sorted(pendentes_df['NOME'].unique())
                concluidos_marcados = sorted([f"{nome}" for nome in concluidos_df['NOME'].unique()])
                
                opcoes_finais = pendentes + concluidos_marcados
                
                col_sel_func, col_cargo = st.columns([2, 1])
                with col_sel_func:
                    selected_option = st.selectbox(
                        "Selecione o Funcionário", options=opcoes_finais, index=None,
                        placeholder="Digite para buscar...", key="lf_func_select" 
                    )
                
                funcionario_selecionado = None
                funcao_selecionada = "---"
                if selected_option:
                    funcionario_selecionado = selected_option.replace("✅ ", "")
                    funcao_selecionada = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'FUNÇÃO'].iloc[0]
                
                with col_cargo:
                    st.markdown(f"**Função:**")
                    st.info(f"{funcao_selecionada}")

            st.markdown("<div class='section-header'>Detalhes do Serviço</div>", unsafe_allow_html=True)
            
            with st.container(border=True):
                disciplinas = sorted(precos_df['DISCIPLINA'].unique())
                disciplina_idx = disciplinas.index(st.session_state.get("lf_disciplina_select")) if st.session_state.get("lf_disciplina_select") in disciplinas else None
                
                c1, c2 = st.columns([1, 2])
                with c1:
                    disciplina_selecionada = st.selectbox("Disciplina", options=disciplinas, index=disciplina_idx, placeholder="Selecione...", key="lf_disciplina_select")
                
                opcoes_servico = []
                servico_idx = None
                if disciplina_selecionada:
                    opcoes_servico = sorted(precos_df[precos_df['DISCIPLINA'] == disciplina_selecionada]['DESCRIÇÃO DO SERVIÇO'].unique())
                    servico_idx = opcoes_servico.index(st.session_state.get("lf_servico_select")) if st.session_state.get("lf_servico_select") in opcoes_servico else None

                with c2:
                    servico_selecionado = st.selectbox("Descrição do Serviço", options=opcoes_servico, index=servico_idx, placeholder="Selecione disciplina primeiro...", disabled=not disciplina_selecionada, key="lf_servico_select")
                
                quantidade_principal = 0.0 
                valor_parcial_servico = 0.0
                
                if servico_selecionado:
                    st.markdown("---")
                    servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                    valor_unitario = utils.safe_float(servico_info.get('VALOR'))
                    
                    kpi1, kpi2, kpi3 = st.columns([1, 1, 2])
                    kpi1.caption("Unidade")
                    kpi1.markdown(f"**{servico_info['UNIDADE']}**")
                    
                    kpi2.caption("Valor Unit.")
                    kpi2.markdown(f"**{utils.format_currency(servico_info['VALOR'])}**")
                    
                    with kpi3:
                        quantidade_principal = st.number_input(
                            "Quantidade Executada", min_value=0.0, step=0.1, format="%.2f", 
                            key="lf_qty_principal" 
                        )
                    
                    valor_parcial_servico = quantidade_principal * valor_unitario
                    
                    st.markdown(f"""
                    <div class="subtotal-box">
                        <p class="subtotal-label">Subtotal do Serviço</p>
                        <p class="subtotal-value">{utils.format_currency(valor_parcial_servico)}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    col_data_princ, col_obs_princ = st.columns([1, 2])
                    with col_data_princ:
                        data_servico_principal = st.date_input("Data Realização", value=datetime.now().date(), key="lf_data_principal", format="DD/MM/YYYY")
                    with col_obs_princ:
                        obs_principal = st.text_input("Observação (Opcional)", key="lf_obs_principal", placeholder="Detalhes do local ou especificidade...")
            
            with st.expander("Lançar Item Diverso", expanded=False):
                descricao_diverso = st.text_input("Descrição do Item", key="lf_desc_diverso", placeholder="Ex: Transporte de material extra...")
                
                col_valor_div, col_qtd_div, col_total_div = st.columns([1, 1, 1])
                with col_valor_div:
                    valor_diverso = st.number_input("Valor Unit. (R$)", min_value=0.0, step=1.00, format="%.2f", key="lf_valor_diverso")
                with col_qtd_div:
                    quantidade_diverso = st.number_input(
                        "Qtd.", min_value=0.0, step=0.1, format="%.2f", 
                        key="lf_qty_diverso"
                    )
                
                valor_parcial_diverso = quantidade_diverso * valor_diverso
                with col_total_div:
                     st.markdown(f"<div style='text-align:right; padding-top: 30px;'><b>Total: {utils.format_currency(valor_parcial_diverso)}</b></div>", unsafe_allow_html=True)

                col_data_div, col_obs_div = st.columns([1, 2])
                with col_data_div:
                    data_servico_diverso = st.date_input("Data", value=datetime.now().date(), key="lf_data_diverso", format="DD/MM/YYYY")
                with col_obs_div:
                    obs_diverso = st.text_input("Obs.", key="lf_obs_diverso")

            with st.expander("Adicionar Gratificação (Complementar)", expanded=False):
                st.info("Use apenas para complementar o salário base de funcionários de PRODUÇÃO que não atingiram a meta.")
                desc_grat = st.text_input("Motivo da Gratificação", key="lf_desc_grat")
                
                col_val_grat, col_data_grat = st.columns(2) 
                with col_val_grat:
                    val_grat = st.number_input("Valor (R$)", min_value=0.0, step=50.00, format="%.2f", key="lf_val_grat")
                with col_data_grat:
                    data_grat = st.date_input("Data Ref.", value=datetime.now().date(), key="lf_data_grat", format="DD/MM/YYYY")
                
                obs_grat = st.text_area("Justificativa Detalhada", key="lf_obs_grat", height=68)
                if val_grat > 0:
                    st.markdown(f"**Total a lançar: {utils.format_currency(val_grat)}**")

            st.markdown("---")
            
            if st.button("Adicionar Lançamento(s)", use_container_width=True, type="primary", key="lf_add_btn"):

                if not funcionario_selecionado:
                    st.warning("Por favor, selecione um funcionário.")
                else:
                    current_servico_selecionado = st.session_state.get("lf_servico_select")
                    current_quantidade_principal = st.session_state.get("lf_qty_principal", 0.0)
                    current_obs_principal = st.session_state.get("lf_obs_principal", "")
                    current_data_servico_principal = st.session_state.get("lf_data_principal", datetime.now().date())
                    
                    current_descricao_diverso = st.session_state.get("lf_desc_diverso", "")
                    current_quantidade_diverso = st.session_state.get("lf_qty_diverso", 0.0)
                    current_valor_diverso = st.session_state.get("lf_valor_diverso", 0.0)
                    current_obs_diverso = st.session_state.get("lf_obs_diverso", "")
                    current_data_servico_diverso = st.session_state.get("lf_data_diverso", datetime.now().date())

                    current_desc_grat = st.session_state.get("lf_desc_grat", "")
                    current_val_grat = st.session_state.get("lf_val_grat", 0.0)
                    current_obs_grat = st.session_state.get("lf_obs_grat", "")
                    current_data_grat = st.session_state.get("lf_data_grat", datetime.now().date())

                    erros = []
                    if current_servico_selecionado and current_quantidade_principal > 0.0 and not current_obs_principal.strip():

                        erros.append("Serviço Principal: Observação obrigatória.")
                    if current_descricao_diverso.strip() and current_quantidade_diverso > 0.0 and not current_obs_diverso.strip():
                        erros.append("Item Diverso: Observação obrigatória.")
                    if current_val_grat > 0.0 and not current_desc_grat.strip():
                         erros.append("Gratificação: Descrição obrigatória.")
                    if current_val_grat > 0.0 and not current_obs_grat.strip():
                         erros.append("Gratificação: Observação obrigatória.")

                    add_serv = current_servico_selecionado and current_quantidade_principal > 0.0
                    add_div = current_descricao_diverso.strip() and current_quantidade_diverso > 0.0 and current_valor_diverso > 0.0 
                    add_grat = current_desc_grat.strip() and current_val_grat > 0.0

                    if not any([add_serv, add_div, add_grat]):
                         st.info("Nenhum item válido foi preenchido (verifique Quantidade e Valor).")
                    elif erros:
                        for erro in erros: st.warning(erro)
                    else:
                        novos_lancamentos = []
                        fuso_horario = timezone(timedelta(hours=-3)) 
                        agora = datetime.now(fuso_horario) 
                        
                        func_id_info = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id']
                        if func_id_info.empty: st.error("Funcionário não encontrado.")
                        else:
                            func_id = int(func_id_info.iloc[0])
                            
                            if add_serv:
                                servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == current_servico_selecionado].iloc[0]
                                novos_lancamentos.append({'data_servico': current_data_servico_principal, 'obra_id': obra_logada_id, 'funcionario_id': func_id, 'servico_id': int(servico_info['id']), 'servico_diverso_descricao': None, 'quantidade': current_quantidade_principal, 'valor_unitario': utils.safe_float(servico_info['VALOR']), 'observacao': current_obs_principal, 'data_lancamento': agora})
                            if add_div:
                                novos_lancamentos.append({'data_servico': current_data_servico_diverso, 'obra_id': obra_logada_id, 'funcionario_id': func_id, 'servico_id': None, 'servico_diverso_descricao': current_descricao_diverso, 'quantidade': current_quantidade_diverso, 'valor_unitario': current_valor_diverso, 'observacao': current_obs_diverso, 'data_lancamento': agora})
                            if add_grat:
                                novos_lancamentos.append({'data_servico': current_data_grat, 'obra_id': obra_logada_id, 'funcionario_id': func_id, 'servico_id': None, 'servico_diverso_descricao': f"[GRATIFICACAO] {current_desc_grat}", 'quantidade': 1, 'valor_unitario': current_val_grat, 'observacao': current_obs_grat, 'data_lancamento': agora})
                            
                            if novos_lancamentos:
                                df_para_salvar = pd.DataFrame(novos_lancamentos)
                                
                                if db_utils.salvar_novos_lancamentos(df_para_salvar): 
                                    st.success(f"{len(novos_lancamentos)} lançamento(s) adicionado(s)!")
                                    st.cache_data.clear() 

                                    keys_to_delete = [
                                        "lf_disciplina_select", "lf_servico_select", 
                                        "lf_qty_principal", "lf_obs_principal",
                                        "lf_desc_diverso", "lf_valor_diverso",
                                        "lf_qty_diverso", "lf_obs_diverso",
                                        "lf_desc_grat", "lf_val_grat", "lf_obs_grat"
                                    ]
                                    for key in keys_to_delete:
                                        if key in st.session_state:
                                            del st.session_state[key]
                                    
                                    st.rerun()
                                
        with col_view:
            if funcionario_selecionado:
                func_id_info = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id']
                if not func_id_info.empty:
                    func_id = int(func_id_info.iloc[0])
                    status_row = status_df[(status_df['obra_id'] == obra_logada_id) & (status_df['funcionario_id'] == func_id)]
                    status_atual = status_row['Status'].iloc[0] if not status_row.empty else 'A Revisar'
                    comentario = status_row['Comentario'].iloc[0] if not status_row.empty and pd.notna(status_row['Comentario'].iloc[0]) else ""
                    
                    with st.container(border=True):
                        st.markdown("**Status de Auditoria**")
                        utils.display_status_box(f"{funcionario_selecionado}", status_atual)
                        
                        if comentario:
                            st.caption("Nota do Auditor:")
                            st.warning(f"{comentario}")
                        else:
                             st.caption("Sem pendências de auditoria.")
            
            st.write("") 
            st.markdown("**Histórico Recente**")
            lancamentos_da_obra = lancamentos_do_mes_df[lancamentos_do_mes_df['Obra'] == st.session_state['obra_logada']]
            if funcionario_selecionado: 
                 lancamentos_da_obra = lancamentos_da_obra[lancamentos_da_obra['Funcionário'] == funcionario_selecionado]

            if not lancamentos_da_obra.empty:
                cols_display = ['Data', 'Funcionário','Disciplina', 'Serviço','Quantidade','Valor Parcial', 'Observação']
                cols_existentes = [col for col in cols_display if col in lancamentos_da_obra.columns]
                
                st.dataframe(
                    lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[cols_existentes], 
                    column_config={
                        'Data': st.column_config.DatetimeColumn("Data", format="DD/MM", width='small'), 
                        'Valor Parcial': st.column_config.NumberColumn("R$", format="%.2f", width='small'),
                        'Quantidade': st.column_config.NumberColumn("Qtd", format="%.1f", width='small'),
                        'Disciplina': st.column_config.TextColumn(width='small'),
                        'Funcionário': None, 
                        'Serviço': st.column_config.TextColumn(width='medium'),
                        'Observação': st.column_config.TextColumn(width='large'),
                    },
                    use_container_width=True, 
                    hide_index=True,
                    height=400 
                 )
            else:
                st.info("Nenhum lançamento recente.")

            st.markdown("---")
            
            if funcionario_selecionado:
                func_id_info = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id']
                if not func_id_info.empty:
                    func_id = int(func_id_info.iloc[0])
                    
                    status_row = status_df[(status_df['obra_id'] == obra_logada_id) & (status_df['funcionario_id'] == func_id)]
                    is_concluded = status_row['Lancamentos Concluidos'].iloc[0] if not status_row.empty and 'Lancamentos Concluidos' in status_row.columns and pd.notna(status_row['Lancamentos Concluidos'].iloc[0]) else False

                    if st.button("Marcar como Concluído", use_container_width=True, disabled=is_concluded, help="Finaliza os lançamentos deste funcionário no mês."):
                        if db_utils.upsert_status_auditoria(obra_logada_id, func_id, mes_selecionado, lancamentos_concluidos=True):
                            st.toast(f"'{funcionario_selecionado}' marcado como concluído.")
                            st.cache_data.clear() 
                            st.rerun()
        
            funcionarios_concluidos_db = status_df[
                (status_df['obra_id'] == obra_logada_id) & 
                (status_df['Lancamentos Concluidos'] == True) &
                (status_df['funcionario_id'] != 0) 
            ]
            if not funcionarios_concluidos_db.empty:
                 if st.button("Resetar Todos Concluídos", use_container_width=True, help="Reabre edição para todos da obra."):
                    if db_utils.limpar_concluidos_obra_mes(obra_logada_id, mes_selecionado):
                        st.toast("Status reiniciado.")
                        st.cache_data.clear()
                        st.rerun()

