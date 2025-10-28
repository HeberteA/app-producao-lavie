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

    obra_filtrada = None
    obra_relatorio_nome = None 
    
    if st.session_state['role'] == 'admin':
        st.subheader("Filtros")
        opcoes_obras_filtro = ["Todas"] + sorted(obras_df['NOME DA OBRA'].unique())
        obra_filtrada = st.selectbox("Filtrar por Obra", options=opcoes_obras_filtro, key="resumo_obra_filter")
        if obra_filtrada != "Todas":
            obra_relatorio_nome = obra_filtrada
        st.markdown("---")
    else:
        obra_filtrada = st.session_state['obra_logada']
        obra_relatorio_nome = obra_filtrada

    funcionarios_filtrados_df = funcionarios_df.copy()
    lancamentos_filtrados_df = lancamentos_df.copy()
    
    if obra_filtrada and obra_filtrada != "Todas":
        funcionarios_filtrados_df = funcionarios_filtrados_df[funcionarios_filtrados_df['OBRA'] == obra_filtrada]
        if not lancamentos_filtrados_df.empty:
            lancamentos_filtrados_df = lancamentos_filtrados_df[lancamentos_filtrados_df['Obra'] == obra_filtrada]

    if funcionarios_filtrados_df.empty:
         st.warning(f"Nenhum funcionário encontrado para a obra '{obra_filtrada}'.")
         resumo_df = pd.DataFrame() 
    else:
        funcionarios_filtrados_df['SALARIO_BASE'] = funcionarios_filtrados_df['SALARIO_BASE'].apply(utils.safe_float)
        
        if not lancamentos_filtrados_df.empty:
            lancamentos_filtrados_df['Valor Parcial'] = lancamentos_filtrados_df['Valor Parcial'].apply(utils.safe_float)
            producao_bruta_df = lancamentos_filtrados_df.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
            producao_bruta_df.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
            resumo_df = pd.merge(
                funcionarios_filtrados_df, 
                producao_bruta_df, 
                left_on='id',        
                right_on='funcionario_id', 
                how='left'
            )
        else:
            resumo_df = funcionarios_filtrados_df.copy()
            resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0

        resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
        resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0)

        resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

        status_obra_filtrada = status_df.copy()
        if obra_filtrada and obra_filtrada != "Todas":
            obra_id_filtrada = obras_df.loc[obras_df['NOME DA OBRA'] == obra_filtrada, 'id'].iloc[0]
            status_obra_filtrada = status_df[status_df['obra_id'] == obra_id_filtrada]

        concluidos_df = status_obra_filtrada[status_obra_filtrada['Lancamentos Concluidos'] == True][['funcionario_id']].drop_duplicates()
        
        if not concluidos_df.empty:
            resumo_df = pd.merge(
                resumo_df, 
                concluidos_df, 
                left_on='id',             
                right_on='funcionario_id', 
                how='left', 
                indicator=True
            )
            resumo_df['Situação'] = resumo_df['_merge'].apply(lambda x: 'Concluído' if x == 'both' else 'Pendente')
            resumo_df.drop(columns=['_merge', 'funcionario_id_x', 'funcionario_id_y'], errors='ignore', inplace=True) 
        else:
            resumo_df['Situação'] = 'Pendente'
            resumo_df.drop(columns=['funcionario_id_x', 'funcionario_id_y'], errors='ignore', inplace=True) 

        st.markdown("---")
        st.subheader("Totais")
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        
        total_base = resumo_df['SALÁRIO BASE (R$)'].sum()
        total_liquida = resumo_df['PRODUÇÃO LÍQUIDA (R$)'].sum()
        total_bruta = resumo_df['PRODUÇÃO BRUTA (R$)'].sum()
        total_receber = resumo_df['SALÁRIO A RECEBER (R$)'].sum()
        
        col_t1.metric("Total Salário Base", utils.format_currency(total_base))
        col_t2.metric("Total Produção Líquida", utils.format_currency(total_liquida))
        col_t3.metric("Total Produção Bruta", utils.format_currency(total_bruta))
        col_t4.metric("Total a Receber", utils.format_currency(total_receber))
        
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)

    st.subheader("Detalhes da Folha")
    
    if resumo_df.empty:
         st.info("Nenhum dado para exibir com os filtros selecionados.")
    else:
        colunas_exibicao = [
            'NOME', 'OBRA', 'FUNÇÃO', 'TIPO', 
            'SALÁRIO BASE (R$)', 
            'PRODUÇÃO LÍQUIDA (R$)', 
            'PRODUÇÃO BRUTA (R$)', 
            'SALÁRIO A RECEBER (R$)',
            'Situação' 
        ]
        
        if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
            if 'OBRA' in colunas_exibicao: colunas_exibicao.remove('OBRA')

        colunas_exibicao_finais = [col for col in colunas_exibicao if col in resumo_df.columns]

        st.dataframe(
            resumo_df[colunas_exibicao_finais],
            use_container_width=True,
            hide_index=True,
            column_config={
                "SALÁRIO BASE (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO BRUTA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO LÍQUIDA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "SALÁRIO A RECEBER (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Situação": st.column_config.TextColumn() 
            }
        )
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)

        

        with col_dl1:
            excel_data = utils.to_excel(resumo_df[colunas_exibicao_finais])
            st.download_button(
                label="📥 Baixar Resumo em Excel",
                data=excel_data,
                file_name=f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col_dl2:
            colunas_lancamentos_pdf = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
            if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
                 if 'Obra' in colunas_lancamentos_pdf: colunas_lancamentos_pdf.remove('Obra')

            if lancamentos_filtrados_df.empty:
                lancamentos_para_pdf = pd.DataFrame(columns=colunas_lancamentos_pdf)
            else:
                colunas_lanc_existentes = [col for col in colunas_lancamentos_pdf if col in lancamentos_filtrados_df.columns]
                lancamentos_para_pdf = lancamentos_filtrados_df[colunas_lanc_existentes]


            if st.button("📄 Baixar Resumo em PDF", use_container_width=True):
                 with st.spinner("Gerando PDF..."):
                    pdf_data = utils.gerar_relatorio_pdf( 
                        resumo_df=resumo_df[colunas_exibicao_finais], 
                        lancamentos_df=lancamentos_para_pdf,
                        logo_path="Lavie.png",
                        mes_referencia=mes_selecionado,
                        obra_nome=obra_relatorio_nome 
                    )
                    if pdf_data: 
                        st.session_state['pdf_data_resumo'] = pdf_data 
                        st.session_state['pdf_filename_resumo'] = f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.pdf"
                    else:
                        if 'pdf_data_resumo' in st.session_state: del st.session_state['pdf_data_resumo']
                        if 'pdf_filename_resumo' in st.session_state: del st.session_state['pdf_filename_resumo']

            if 'pdf_data_resumo' in st.session_state and st.session_state['pdf_data_resumo']:
                st.download_button(
                    label="⬇️ Clique aqui para baixar o PDF",
                    data=st.session_state['pdf_data_resumo'],
                    file_name=st.session_state['pdf_filename_resumo'],
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_download_resumo_final", 
                    on_click=lambda: st.session_state.pop('pdf_data_resumo', None) 
                )




