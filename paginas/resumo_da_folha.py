import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
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
         resumo_df = pd.DataFrame()
    else:
        if 'id' not in funcionarios_filtrados_df.columns:
            st.error("Coluna 'id' crucial não encontrada em funcionarios_df.")
            return

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
        resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = resumo_df['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0)

        resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

        status_funcionarios_df = status_filtrado_df[status_filtrado_df['funcionario_id'] != 0][['funcionario_id', 'Status', 'Lancamentos Concluidos']].drop_duplicates()

        if not status_funcionarios_df.empty:
            resumo_df = pd.merge(
                resumo_df, status_funcionarios_df,
                left_on='id', right_on='funcionario_id',
                how='left'
            )
            if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id':
                 resumo_df = resumo_df.drop(columns=['funcionario_id'])
        else: 
             resumo_df['Status'] = 'A Revisar'
             resumo_df['Lancamentos Concluidos'] = False

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
        if funcao_filtrada != "Todas":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['FUNÇÃO'] == funcao_filtrada]
        if funcionario_filtrado != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['NOME'] == funcionario_filtrado]
            
    st.markdown("---")
        st.subheader("Totais")
        col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
        total_base = df_filtrado_final['SALÁRIO BASE (R$)'].sum()
        total_bruta = df_filtrado_final['PRODUÇÃO BRUTA (R$)'].sum()
        total_liquida = df_filtrado_final['PRODUÇÃO LÍQUIDA (R$)'].sum()
        total_grat = df_filtrado_final['TOTAL GRATIFICAÇÕES (R$)'].sum()
        total_receber = df_filtrado_final['SALÁRIO A RECEBER (R$)'].sum()
        col_t1.metric("Total Salário Base", utils.format_currency(total_base))
        col_t2.metric("Total Prod. Bruta", utils.format_currency(total_bruta))
        col_t3.metric("Total Prod. Líquida", utils.format_currency(total_liquida))
        col_t4.metric("Total Gratificações", utils.format_currency(total_grat))
        col_t5.metric("Total a Receber", utils.format_currency(total_receber))

    st.markdown("---") 
    st.subheader("Detalhes da Folha")

    if df_filtrado_final.empty:
         st.info("Nenhum dado para exibir com os filtros selecionados.")
    else:
        colunas_exibicao = [
            'NOME', 'OBRA', 'FUNÇÃO', 'TIPO',
            'SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)',
            'PRODUÇÃO LÍQUIDA (R$)', 'TOTAL GRATIFICAÇÕES (R$)',
            'SALÁRIO A RECEBER (R$)',
            'Status', 
            'Situação'
        ]

        if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
            if 'OBRA' in colunas_exibicao: colunas_exibicao.remove('OBRA')

        colunas_finais_existentes = [col for col in colunas_exibicao if col in df_filtrado_final.columns]

        st.dataframe(
            df_filtrado_final[colunas_finais_existentes],
            use_container_width=True, hide_index=True, height=550,
            column_config={
                "SALÁRIO BASE (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO BRUTA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO LÍQUIDA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "TOTAL GRATIFICAÇÕES (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "SALÁRIO A RECEBER (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Status": st.column_config.TextColumn("Status Auditoria"), 
                "Situação": st.column_config.TextColumn("Situação Lançamento")
            }
        )
        
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            excel_data = utils.to_excel(df_filtrado_final[colunas_finais_existentes]) 
            st.download_button( label="📥 Baixar Resumo em Excel", data=excel_data,
                file_name=f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl2:
            lancamentos_para_pdf_final = lancamentos_filtrados_df.copy()
            if funcionario_filtrado != "Todos":
                 if not lancamentos_para_pdf_final.empty:
                      lancamentos_para_pdf_final = lancamentos_para_pdf_final[lancamentos_para_pdf_final['Funcionário'] == funcionario_filtrado]
            colunas_lancamentos_pdf = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
            if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
                 if 'Obra' in colunas_lancamentos_pdf: colunas_lancamentos_pdf.remove('Obra')
            if lancamentos_para_pdf_final.empty: lancamentos_para_pdf = pd.DataFrame(columns=colunas_lancamentos_pdf)
            else:
                cols_lanc_existentes = [col for col in colunas_lancamentos_pdf if col in lancamentos_para_pdf_final.columns]
                lancamentos_para_pdf = lancamentos_para_pdf_final[cols_lanc_existentes]

            pdf_button_placeholder = st.empty() 
            if pdf_button_placeholder.button("📄 Baixar Resumo em PDF", use_container_width=True, key="gerar_pdf_resumo"):
                 with st.spinner("Gerando PDF..."):
                    pdf_data = utils.gerar_relatorio_pdf(
                        resumo_df=df_filtrado_final[colunas_finais_existentes], 
                        lancamentos_df=lancamentos_para_pdf,
                        logo_path="Lavie.png", mes_referencia=mes_selecionado, obra_nome=obra_relatorio_nome
                    )
                    if pdf_data:
                        pdf_button_placeholder.download_button(
                            label="⬇️ Clique aqui para baixar o PDF", data=pdf_data,
                            file_name=f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.pdf",
                            mime="application/pdf", use_container_width=True,
                            key="pdf_download_resumo_final"
                        )
                        st.info("Seu download está pronto. Clique no botão acima.")


