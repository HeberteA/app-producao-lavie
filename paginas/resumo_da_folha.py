import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    st.markdown("""
    <style>
    /* Card Estilo Glassmorphism Escuro */
    .custom-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 10px;
        transition: transform 0.2s, border-color 0.2s;
    }
    .custom-card:hover {
        transform: translateY(-2px);
        border-color: #E37026; /* Laranja da marca no hover */
        background-color: rgba(255, 255, 255, 0.08);
    }
    .card-label {
        color: #A0A0A0; /* Cinza claro para rótulos */
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .card-value {
        color: #FFFFFF; /* Branco para valores */
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    /* Indicador lateral colorido */
    .card-indicator {
        width: 4px;
        height: 24px;
        border-radius: 2px;
        position: absolute;
        left: 10px;
        top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    def display_card(label, value, color="#E37026", icon=""):
        return f"""
        <div class="custom-card">
            <div class="card-indicator" style="background-color: {color};"></div>
            <div class="card-label">{icon} {label}</div>
            <div class="card-value">{value}</div>
        </div>
        """

    mes_selecionado = st.session_state.selected_month
    st.header(f"Resumo da Folha - {mes_selecionado}")

    @st.cache_data
    def get_resumo_data(mes):
        funcionarios_df = db_utils.get_funcionarios()
        lancamentos_df = db_utils.get_lancamentos_do_mes(mes)
        obras_df = db_utils.get_obras()
        status_df = db_utils.get_status_do_mes(mes)
        return funcionarios_df, lancamentos_df, obras_df, status_df

    funcionarios_df, lancamentos_df, obras_df, status_df = get_resumo_data(mes_selecionado)

    if funcionarios_df.empty:
        st.info("Nenhum funcionário ativo encontrado.")
        return

    st.subheader("Filtros")
    obra_filtrada = None
    obra_relatorio_nome = None
    if st.session_state['role'] == 'admin':
        col_f_obra, col_f_func, col_f_funci = st.columns(3)
    else: 
        col_f_func, col_f_funci = st.columns(2)
        col_f_obra = None 

    if st.session_state['role'] == 'admin' and col_f_obra:
        with col_f_obra:
            opcoes_obras_filtro = ["Todas"] + sorted(obras_df['NOME DA OBRA'].unique())
            obra_filtrada = st.selectbox("Obra", options=opcoes_obras_filtro, key="resumo_obra_filter")
            if obra_filtrada != "Todas": obra_relatorio_nome = obra_filtrada
    else: 
        obra_filtrada = st.session_state['obra_logada']
        obra_relatorio_nome = obra_filtrada
    funcionarios_filtrados_df = funcionarios_df.copy()
    lancamentos_filtrados_df = lancamentos_df.copy()
    status_filtrado_df = status_df.copy() 

    obra_id_filtrada = None 
    if obra_filtrada and obra_filtrada != "Todas":
        obra_id_filtrada_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_filtrada, 'id']
        if not obra_id_filtrada_info.empty:
            obra_id_filtrada = obra_id_filtrada_info.iloc[0]
            funcionarios_filtrados_df = funcionarios_filtrados_df[funcionarios_filtrados_df['OBRA'] == obra_filtrada]
            if not lancamentos_filtrados_df.empty:
                lancamentos_filtrados_df = lancamentos_filtrados_df[lancamentos_filtrados_df['Obra'] == obra_filtrada]
            if not status_filtrado_df.empty:
                 status_filtrado_df = status_filtrado_df[status_filtrado_df['obra_id'] == obra_id_filtrada]
        else: 
             funcionarios_filtrados_df = pd.DataFrame(columns=funcionarios_df.columns) 
             lancamentos_filtrados_df = pd.DataFrame(columns=lancamentos_df.columns)
             status_filtrado_df = pd.DataFrame(columns=status_df.columns)

    if funcionarios_filtrados_df.empty:
         st.warning(f"Nenhum funcionário encontrado para a obra '{obra_filtrada}'.")
         return

    if 'id' not in funcionarios_filtrados_df.columns: st.error("Erro: ID não encontrado."); return
    funcionarios_filtrados_df['SALARIO_BASE'] = funcionarios_filtrados_df['SALARIO_BASE'].apply(utils.safe_float)

    producao_bruta_df = pd.DataFrame()
    total_gratificacoes_df = pd.DataFrame()

    if not lancamentos_filtrados_df.empty:
        lancamentos_filtrados_df['Valor Parcial'] = lancamentos_filtrados_df['Valor Parcial'].apply(utils.safe_float)
        lanc_producao = lancamentos_filtrados_df[lancamentos_filtrados_df['Disciplina'] != 'GRATIFICAÇÃO']
        if not lanc_producao.empty:
            producao_bruta_df = lanc_producao.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
            producao_bruta_df.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
        lanc_gratificacoes = lancamentos_filtrados_df[lancamentos_filtrados_df['Disciplina'] == 'GRATIFICAÇÃO']
        if not lanc_gratificacoes.empty:
            total_gratificacoes_df = lanc_gratificacoes.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
            total_gratificacoes_df.rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'}, inplace=True)

    resumo_df = funcionarios_filtrados_df.copy()
    if not producao_bruta_df.empty:
        resumo_df = pd.merge(resumo_df, producao_bruta_df, left_on='id', right_on='funcionario_id', how='left')
        if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id': resumo_df = resumo_df.drop(columns=['funcionario_id'])
    else: resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0

    if not total_gratificacoes_df.empty:
            resumo_df = pd.merge(resumo_df, total_gratificacoes_df, left_on='id', right_on='funcionario_id', how='left')
            if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id': resumo_df = resumo_df.drop(columns=['funcionario_id'])
    else: resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = 0.0

    resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
    cols_to_fix = ['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)', 'SALÁRIO BASE (R$)']
    for col in cols_to_fix: resumo_df[col] = resumo_df[col].fillna(0.0).apply(utils.safe_float)

    resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
    resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

    status_funcionarios_df = status_filtrado_df[status_filtrado_df['funcionario_id'] != 0][['funcionario_id', 'Status', 'Lancamentos Concluidos']].drop_duplicates()
    if not status_funcionarios_df.empty:
        resumo_df = pd.merge(resumo_df, status_funcionarios_df, left_on='id', right_on='funcionario_id', how='left')
        if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id': resumo_df = resumo_df.drop(columns=['funcionario_id'])
    else: 
            resumo_df['Status'] = 'A Revisar'; resumo_df['Lancamentos Concluidos'] = False

    resumo_df['Status'] = resumo_df['Status'].fillna('A Revisar')
    resumo_df['Lancamentos Concluidos'] = resumo_df['Lancamentos Concluidos'].fillna(False)
    resumo_df['Situação'] = resumo_df['Lancamentos Concluidos'].apply(lambda x: 'Concluído' if x else 'Pendente')

    df_filtrado_final = resumo_df.copy() 
    with col_f_func:
        opcoes_funcoes = ["Todas"] + sorted(resumo_df['FUNÇÃO'].unique()) if not resumo_df.empty else ["Todas"]
        funcao_filtrada = st.selectbox("Função", options=opcoes_funcoes, key="resumo_funcao_filter")
    with col_f_funci:
        resumo_opts_func = resumo_df.copy()
        if not resumo_opts_func.empty and funcao_filtrada != "Todas":
             resumo_opts_func = resumo_opts_func[resumo_opts_func['FUNÇÃO'] == funcao_filtrada]
        opcoes_funcionarios = ["Todos"] + sorted(resumo_opts_func['NOME'].unique()) if not resumo_opts_func.empty else ["Todos"]
        funcionario_filtrado = st.selectbox("Funcionário", options=opcoes_funcionarios, key="resumo_func_filter")

    if not df_filtrado_final.empty:
        if funcao_filtrada != "Todas": df_filtrado_final = df_filtrado_final[df_filtrado_final['FUNÇÃO'] == funcao_filtrada]
        if funcionario_filtrado != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['NOME'] == funcionario_filtrado]
            
        st.markdown("---")
        
        total_base = df_filtrado_final['SALÁRIO BASE (R$)'].sum()
        total_bruta = df_filtrado_final['PRODUÇÃO BRUTA (R$)'].sum()
        total_liquida = df_filtrado_final['PRODUÇÃO LÍQUIDA (R$)'].sum()
        total_grat = df_filtrado_final['TOTAL GRATIFICAÇÕES (R$)'].sum()
        total_receber = df_filtrado_final['SALÁRIO A RECEBER (R$)'].sum()

        col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
        
        with col_t1: st.markdown(display_card("Salário Base", utils.format_currency(total_base), color="#6c757d"), unsafe_allow_html=True)
        with col_t2: st.markdown(display_card("Prod. Bruta", utils.format_currency(total_bruta), color="#E37026"), unsafe_allow_html=True)
        with col_t3: st.markdown(display_card("Prod. Líquida", utils.format_currency(total_liquida), color="#1E88E5"), unsafe_allow_html=True)
        with col_t4: st.markdown(display_card("Gratificações", utils.format_currency(total_grat), color="#8b5cf6"), unsafe_allow_html=True)
        with col_t5: st.markdown(display_card("A Receber", utils.format_currency(total_receber), color="#328c11"), unsafe_allow_html=True)


    st.subheader("Detalhes da Folha")

    if df_filtrado_final.empty:
         st.info("Nenhum dado para exibir.")
    else:
        colunas_exibicao = ['NOME', 'OBRA', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)', 'PRODUÇÃO LÍQUIDA (R$)', 'TOTAL GRATIFICAÇÕES (R$)', 'SALÁRIO A RECEBER (R$)', 'Status', 'Situação']
        if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
            if 'OBRA' in colunas_exibicao: colunas_exibicao.remove('OBRA')

        colunas_finais_existentes = [col for col in colunas_exibicao if col in df_filtrado_final.columns]
        
        df_para_exibir = df_filtrado_final[colunas_finais_existentes].style \
            .apply(lambda x: x.map(utils.style_status), subset=['STATUS']) \
            .apply(lambda x: x.map(utils.style_situacao), subset=['SITUAÇÃO'])

        st.dataframe(
            df_para_exibir,
            use_container_width=True, hide_index=True,
            column_config={
                "SALÁRIO BASE (R$)": st.column_config.NumberColumn("SALÁRIO BASE", format="R$ %.2f"),
                "PRODUÇÃO BRUTA (R$)":st.column_config.NumberColumn("PRODUÇÃO BRUTA",format="R$ %.2f"),
                "PRODUÇÃO LÍQUIDA (R$)":st.column_config.NumberColumn("PRODUÇÃO LÍQUIDA",format="R$ %.2f"),
                "TOTAL GRATIFICAÇÕES (R$)": st.column_config.NumberColumn("GRATIFICAÇÕES",format="R$ %.2f"),
                "SALÁRIO A RECEBER (R$)": st.column_config.NumberColumn("SALÁRIO A RECEBER",format="R$ %.2f"),
            }
        )
        
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            excel_data = utils.to_excel(df_filtrado_final[colunas_finais_existentes]) 
            st.download_button(label="Baixar Excel", data=excel_data, file_name=f"resumo_{mes_selecionado}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl2:
            lancamentos_para_pdf_final = lancamentos_filtrados_df.copy()
            if funcionario_filtrado != "Todos" and not lancamentos_para_pdf_final.empty:
                  lancamentos_para_pdf_final = lancamentos_para_pdf_final[lancamentos_para_pdf_final['Funcionário'] == funcionario_filtrado]
            
            colunas_lanc = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
            if not lancamentos_para_pdf_final.empty:
                cols_ex = [c for c in colunas_lanc if c in lancamentos_para_pdf_final.columns]
                lancamentos_para_pdf = lancamentos_para_pdf_final[cols_ex]
            else: lancamentos_para_pdf = pd.DataFrame(columns=colunas_lanc)

            pdf_ph = st.empty() 
            if pdf_ph.button("Baixar PDF", use_container_width=True):
                 with st.spinner("Gerando PDF..."):
                    pdf_data = utils.gerar_relatorio_pdf(df_filtrado_final[colunas_finais_existentes], lancamentos_para_pdf, "Lavie.png", mes_selecionado, obra_relatorio_nome)
                    if pdf_data:
                        pdf_ph.download_button(label="⬇️ Download PDF", data=pdf_data, file_name=f"resumo_{mes_selecionado}.pdf", mime="application/pdf", use_container_width=True)










