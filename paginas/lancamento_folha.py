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
    .info-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s;
    }
    .info-card:hover {
        border-color: #E37026;
        background-color: rgba(255, 255, 255, 0.08);
    }
    .info-label {
        color: #A0A0A0;
        font-size: 0.75rem;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .info-value {
        color: #FFFFFF;
        font-size: 1.1rem;
        font-weight: 700;
    }
    .info-indicator {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

    def display_info_card(label, value, color="#E37026", icon=""):
        return f"""
        <div class="info-card">
            <div class="info-indicator" style="background-color: {color};"></div>
            <div class="info-label">{icon} {label}</div>
            <div class="info-value" style="color: {color};">{value}</div>
        </div>
        """

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
    snapshots_df = db_utils.get_snapshot_salarios(mes_selecionado)
    
    if not funcionarios_df.empty and 'data_admissao' in funcionarios_df.columns:
        funcionarios_df['data_admissao'] = pd.to_datetime(funcionarios_df['data_admissao']).dt.date
        
        ano, mes = map(int, mes_selecionado.split('-'))
        import calendar
        ultimo_dia_do_mes = date(ano, mes, calendar.monthrange(ano, mes)[1])
        
        funcionarios_df = funcionarios_df[funcionarios_df['data_admissao'] <= ultimo_dia_do_mes]

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
    hoje = date.today()
    if hoje.year == mes_selecionado_dt.year and hoje.month == mes_selecionado_dt.month:
        data_padrao_input = hoje
    else:
        data_padrao_input = mes_selecionado_dt

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

        col_form, col_view = st.columns([2, 1], gap="medium") 

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
                concluidos_marcados = sorted([f"✅ {nome}" for nome in concluidos_df['NOME'].unique()])

                opcoes_finais = pendentes + concluidos_marcados

                selected_option = st.selectbox(
                    "Selecione o Funcionário", options=opcoes_finais, index=None,
                    placeholder="Selecione um funcionário...", key="lf_func_select" 
                )

                funcionario_selecionado = None
                if selected_option:
                    funcionario_selecionado = selected_option.replace("✅ ", "")

                if funcionario_selecionado:
                    func_row = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado].iloc[0]
                    func_id = func_row['id']
                    snapshot_row = snapshots_df[snapshots_df['funcionario_id'] == func_id] if not snapshots_df.empty else pd.DataFrame()
                    
                    if not snapshot_row.empty and status_folha != "Aberta":
                        funcao_selecionada = snapshot_row.iloc[0]['funcao_na_epoca']
                        salario_base = utils.safe_float(snapshot_row.iloc[0]['salario_base_na_epoca'])
                    else:
                        funcao_selecionada = func_row['FUNÇÃO']
                        salario_base = utils.safe_float(func_row['SALARIO_BASE'])
                    
                    producao_atual = 0.0
                    if not lancamentos_do_mes_df.empty:
                        lancs_func = lancamentos_do_mes_df[lancamentos_do_mes_df['Funcionário'] == funcionario_selecionado]
                        producao_atual = lancs_func['Valor Parcial'].sum()

                    c1, c2, c3 = st.columns(3)
                    
                    if salario_base > 0 and producao_atual >= salario_base:
                        cor_prod = "#328c11" 
                    else:
                        cor_prod = "#ff9800" 
                    
                    with c1:
                        st.markdown(display_info_card("Função", funcao_selecionada, color="#FFFFFF"), unsafe_allow_html=True)
                    with c2:
                        st.markdown(display_info_card("Salário Base", utils.format_currency(salario_base), color="#FFFFFF"), unsafe_allow_html=True)
                    with c3:
                        st.markdown(display_info_card("Produção Mês", utils.format_currency(producao_atual), color=cor_prod), unsafe_allow_html=True)
                    st.markdown("")

            st.markdown("<div class='section-header'>Detalhes do Serviço</div>", unsafe_allow_html=True)
            with st.container(border=True):
                disciplinas = sorted(precos_df['DISCIPLINA'].unique())
                disciplina_idx = disciplinas.index(st.session_state.get("lf_disciplina_select")) if st.session_state.get("lf_disciplina_select") in disciplinas else None

                c1, c2 = st.columns([1, 2])
                with c1:
                    disciplina_selecionada = st.selectbox("Disciplina", options=disciplinas, index=None, placeholder="Selecione...", key="lf_disciplina_select")

                opcoes_servico = []
                servico_idx = None
                if disciplina_selecionada:
                    opcoes_servico = sorted(precos_df[precos_df['DISCIPLINA'] == disciplina_selecionada]['DESCRIÇÃO DO SERVIÇO'].unique())
                    servico_idx = opcoes_servico.index(st.session_state.get("lf_servico_select")) if st.session_state.get("lf_servico_select") in opcoes_servico else None

                with c2:
                    servico_selecionado = st.selectbox("Descrição do Serviço", options=opcoes_servico, index=None, placeholder="Selecione disciplina primeiro...", disabled=not disciplina_selecionada, key="lf_servico_select")

                quantidade_principal = 0.0 
                valor_parcial_servico = 0.0
                if servico_selecionado:
                    servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]

                    kpi1, kpi2 = st.columns(2)
                    kpi1.metric(label="Unidade", value=servico_info['UNIDADE'])
                    kpi2.metric(label="Valor Unitário", value=utils.format_currency(servico_info['VALOR']))

                    col_qtd, col_parcial = st.columns(2)
                    with col_qtd:
                        quantidade_principal = st.number_input(
                            "Quantidade", min_value=0.0, step=0.1, format="%.2f", 
                            key="lf_qty_principal" 
                        )
                    with col_parcial:
                        valor_unitario = utils.safe_float(servico_info.get('VALOR'))
                        valor_parcial_servico = quantidade_principal * valor_unitario
                        st.metric(label="Subtotal do Serviço", value=utils.format_currency(valor_parcial_servico))

                    col_data_princ, col_obs_princ = st.columns(2)
                    with col_data_princ:
                        data_servico_principal = st.date_input("Data do Serviço", value=data_padrao_input, key="lf_data_principal", format="DD/MM/YYYY")
                    with col_obs_princ:
                        obs_principal = st.text_area("Observação", key="lf_obs_principal")

            with st.expander("Lançar Item Diverso"):
                descricao_diverso = st.text_input("Descrição do Item Diverso", key="lf_desc_diverso")
                col_valor_div, col_qtd_div = st.columns(2)
                with col_valor_div:
                    valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="lf_valor_diverso")
                with col_qtd_div:
                    quantidade_diverso = st.number_input(
                        "Quantidade", min_value=0.0, step=0.1, format="%.2f", 
                        key="lf_qty_diverso"
                    )
                valor_parcial_diverso = quantidade_diverso * valor_diverso
                st.metric(label="Subtotal Item Diverso", value=utils.format_currency(valor_parcial_diverso))
                col_data_div, col_obs_div = st.columns(2)
                with col_data_div:
                    data_servico_diverso = st.date_input("Data Item Diverso", value=data_padrao_input, key="lf_data_diverso", format="DD/MM/YYYY")
                with col_obs_div:
                    obs_diverso = st.text_area("Observação", key="lf_obs_diverso")

            with st.expander("Adicionar Gratificação"):
                st.warning("Observação: Este lançamento aplica-se somente a funcionários enquadrados na modalidade de PRODUÇÃO, que neste mês não atingiram produção suficiente para alcançar o salário base. Por esse motivo, o gestor autoriza o pagamento de um valor complementar, registrado a título de GRATIFICAÇÃO.")
                desc_grat = st.text_input("Descrição da Gratificação", key="lf_desc_grat")
                col_val_grat, col_st = st.columns(2) 
                with col_val_grat:
                    val_grat = st.number_input("Valor da Gratificação (R$)", min_value=0.0, step=50.00, format="%.2f", key="lf_val_grat")
                with col_st:
                    st.metric(label="Subtotal Gratificação", value=utils.format_currency(val_grat)) 
                col_data_grat, col_obs_grat = st.columns(2)
                with col_data_grat:
                    data_grat = st.date_input("Data da Gratificação", value=data_padrao_input, key="lf_data_grat", format="DD/MM/YYYY")
                with col_obs_grat:
                    obs_grat = st.text_area("Observação", key="lf_obs_grat")

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
                        st.markdown("##### Status de Auditoria")
                        utils.display_status_box(f"{funcionario_selecionado}", status_atual)
                        if comentario:
                            st.caption("Comentário:")
                            st.warning(f"{comentario}")
                        else:
                             st.caption("Nenhum comentário da auditoria.")
                    st.markdown("---")

            st.markdown("##### Lançamentos Recentes")
            lancamentos_da_obra = lancamentos_do_mes_df[lancamentos_do_mes_df['Obra'] == st.session_state['obra_logada']]
            if funcionario_selecionado: 
                 lancamentos_da_obra = lancamentos_da_obra[lancamentos_da_obra['Funcionário'] == funcionario_selecionado]

            if not lancamentos_da_obra.empty:
                cols_display = ['Data', 'Funcionário','Disciplina', 'Serviço','Quantidade','Valor Parcial', 'Observação']
                cols_existentes = [col for col in cols_display if col in lancamentos_da_obra.columns]

                st.dataframe(
                    lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[cols_existentes], 
                    column_config={
                        'Data': st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm", width='small'), 
                        'Valor Parcial': st.column_config.NumberColumn("Vlr Parcial", format="R$ %.2f", width='small'),
                        'Quantidade': st.column_config.NumberColumn("Qtd", format="%.2f", width='small'),
                        'Disciplina': st.column_config.TextColumn(width='small'),
                        'Funcionário': st.column_config.TextColumn(width='medium'),
                        'Serviço': st.column_config.TextColumn(width='medium'),
                        'Observação': st.column_config.TextColumn(width='large'),
                    },
                    use_container_width=True, 
                    hide_index=True,
                    height=350 
                 )
            else:
                st.info("Nenhum lançamento para exibir.")

            st.markdown("---")
            if funcionario_selecionado:
                func_id_info = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'id']
                if not func_id_info.empty:
                    func_id = int(func_id_info.iloc[0])

                    status_row = status_df[(status_df['obra_id'] == obra_logada_id) & (status_df['funcionario_id'] == func_id)]
                    is_concluded = status_row['Lancamentos Concluidos'].iloc[0] if not status_row.empty and 'Lancamentos Concluidos' in status_row.columns and pd.notna(status_row['Lancamentos Concluidos'].iloc[0]) else False

                    if st.button("Concluir Lançamentos", use_container_width=True, disabled=is_concluded, help="Marca este funcionário como concluído para este mês."):
                        if db_utils.upsert_status_auditoria(obra_logada_id, func_id, mes_selecionado, lancamentos_concluidos=True):
                            st.toast(f"'{funcionario_selecionado}' marcado como concluído.", icon="👍")
                            st.cache_data.clear() 
                            st.rerun()

            funcionarios_concluidos_db = status_df[
                (status_df['obra_id'] == obra_logada_id) & 
                (status_df['Lancamentos Concluidos'] == True) &
                (status_df['funcionario_id'] != 0) 
            ]
            if not funcionarios_concluidos_db.empty:
                 if st.button("Limpar Concluídos", use_container_width=True, help="Remove a marcação de 'Concluído' de TODOS os funcionários desta obra para este mês."):
                    if db_utils.limpar_concluidos_obra_mes(obra_logada_id, mes_selecionado):
                        st.toast("Marcação de concluídos reiniciada.", icon="🧹")
                        st.cache_data.clear()
                        st.rerun()







