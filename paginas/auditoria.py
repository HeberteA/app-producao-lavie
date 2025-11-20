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
        lancamentos_obra_df['Valor Parcial'] = lancamentos_obra_df['Valor Parcial'].apply(utils.safe_float)
        
        prod_bruta = lancamentos_obra_df[lancamentos_obra_df['Disciplina']!='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'})
        gratif = lancamentos_obra_df[lancamentos_obra_df['Disciplina']=='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'})
        
        resumo_df = funcionarios_obra_df.merge(prod_bruta, left_on='id', right_on='funcionario_id', how='left').merge(gratif, left_on='id', right_on='funcionario_id', how='left', suffixes=('', '_grat'))
        resumo_df[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']] = resumo_df[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']].fillna(0.0)
        resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

        st.subheader("Análise Individual")
        for _, row in resumo_df.iterrows():
            with st.container(border=True):
                c_info, c_stat = st.columns([5, 2])
                with c_info:
                    st.markdown(f"### {row['NOME']} <span style='color:#E37026; font-size:0.8em'>| {row['FUNÇÃO']}</span>", unsafe_allow_html=True)
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1: st.markdown(make_audit_stat("Base", utils.format_currency(row['SALARIO_BASE'])), unsafe_allow_html=True)
                    with c2: st.markdown(make_audit_stat("Bruta", utils.format_currency(row['PRODUÇÃO BRUTA (R$)']), "border-orange"), unsafe_allow_html=True)
                    with c3: st.markdown(make_audit_stat("Líquida", utils.format_currency(row['PRODUÇÃO LÍQUIDA (R$)']), "border-blue"), unsafe_allow_html=True)
                    with c4: st.markdown(make_audit_stat("Gratif.", utils.format_currency(row['TOTAL GRATIFICAÇÕES (R$)']), "border-purple"), unsafe_allow_html=True)
                    with c5: st.markdown(make_audit_stat("A Receber", utils.format_currency(row['SALÁRIO A RECEBER (R$)']), "border-green"), unsafe_allow_html=True)
                
                with c_stat:
                    st.caption("Auditoria")
                    status_f = status_df[(status_df['funcionario_id']==row['id']) & (status_df['obra_id']==obra_id_selecionada)]['Status'].iloc[0] if not status_df[(status_df['funcionario_id']==row['id']) & (status_df['obra_id']==obra_id_selecionada)].empty else "A Revisar"
                    utils.display_status_box("", status_f)

                with st.expander("Detalhes e Edição"):
                    col_act, col_obs = st.columns(2)
                    with col_act:
                         st.markdown("##### Status")
                         new_st = st.radio("Status:", ['A Revisar', 'Aprovado', 'Analisar'], index=['A Revisar', 'Aprovado', 'Analisar'].index(status_f) if status_f in ['A Revisar', 'Aprovado', 'Analisar'] else 0, key=f"s_{row['id']}", horizontal=True, disabled=edicao_bloqueada)
                         if st.button("Salvar Status", key=f"b_s_{row['id']}", disabled=edicao_bloqueada):
                             db_utils.upsert_status_auditoria(obra_id_selecionada, row['id'], mes_selecionado, status=new_st); st.toast("Ok!"); st.rerun()
                    
                    lancs_f = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == row['NOME']].copy()
                    if not lancs_f.empty:
                        st.data_editor(lancs_f[['id', 'Data do Serviço', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação']], key=f"ed_{row['id']}", disabled=['id', 'Data do Serviço', 'Serviço', 'Quantidade', 'Valor Parcial'], hide_index=True)
                    else: st.info("Sem lançamentos.")
    else: st.warning("Sem funcionários.")
