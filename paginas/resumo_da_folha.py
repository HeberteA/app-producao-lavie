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
        if 'id' not in funcionarios_filtrados_df.columns and funcionarios_filtrados_df.index.name == 'id':
             funcionarios_filtrados_df.reset_index(inplace=True)
        elif 'id' not in funcionarios_filtrados_df.columns:
             st.error("Coluna 'id' não encontrada em funcionarios_df após filtro.")
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
            resumo_df = pd.merge(
                resumo_df, 
                producao_bruta_df, 
                left_on='id',             
                right_on='funcionario_id',
                how='left'
            )
            if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id':
                 resumo_df = resumo_df.drop(columns=['funcionario_id'])
        else:
            resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0
            
        if not total_gratificacoes_df.empty:
             resumo_df = pd.merge(
                 resumo_df, 
                 total_gratificacoes_df, 
                 left_on='id',             
                 right_on='funcionario_id',
                 how='left'
             )
             if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id':
                  resumo_df = resumo_df.drop(columns=['funcionario_id'])
        else:
             resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = 0.0

        resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
        resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = resumo_df['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
        resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0) 

        resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
        resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)

        status_obra_filtrada = status_df.copy()
        if obra_filtrada and obra_filtrada != "Todas":
            obra_id_filtrada_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_filtrada, 'id']
            if not obra_id_filtrada_info.empty:
                obra_id_filtrada = obra_id_filtrada_info.iloc[0]
                status_obra_filtrada = status_df[status_df['obra_id'] == obra_id_filtrada]
            else: 
                status_obra_filtrada = pd.DataFrame(columns=status_df.columns) 

        concluidos_df = status_obra_filtrada[status_obra_filtrada['Lancamentos Concluidos'] == True][['funcionario_id']]
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
            resumo_df.drop(columns=['_merge'], inplace=True)
            if 'funcionario_id' in resumo_df.columns and 'funcionario_id' != 'id':
                 resumo_df = resumo_df.drop(columns=['funcionario_id'])
        else:
            resumo_df['Situação'] = 'Pendente'
    df_filtrado_final = resumo_df.copy() 
    if not resumo_df.empty:
        if st.session_state['role'] == 'admin': 
            col_f2, col_f3 = st.columns(2)
        else: 
             container_filtros = st.container()
             col_f2 = container_filtros
             col_f3 = container_filtros
             
        with col_f2:
            opcoes_funcoes = ["Todas"] + sorted(resumo_df['FUNÇÃO'].unique())
            funcao_filtrada = st.selectbox("Filtrar por Função", options=opcoes_funcoes, key="resumo_funcao_filter")
        
        with col_f3:
            opcoes_funcionarios = ["Todos"] + sorted(resumo_df['NOME'].unique())
            funcionario_filtrado = st.selectbox("Filtrar por Funcionário", options=opcoes_funcionarios, key="resumo_func_filter")
        if funcao_filtrada != "Todas":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['FUNÇÃO'] == funcao_filtrada]
        if funcionario_filtrado != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['NOME'] == funcionario_filtrado]
        
        if st.session_state['role'] == 'admin': 
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
        if st.session_state['role'] == 'admin': 
             st.markdown("---")
    st.subheader("Detalhes da Folha")
    
    if df_filtrado_final.empty:
         st.info("Nenhum dado para exibir com os filtros selecionados.")
    else:
        colunas_exibicao = [
            'NOME', 'OBRA', 'FUNÇÃO', 'TIPO', 
            'SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)', 
            'PRODUÇÃO LÍQUIDA (R$)', 'TOTAL GRATIFICAÇÕES (R$)',
            'SALÁRIO A RECEBER (R$)', 'Situação' 
        ]
        if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
            if 'OBRA' in colunas_exibicao: colunas_exibicao.remove('OBRA')

        st.dataframe(
            df_filtrado_final[colunas_exibicao],
            use_container_width=True, hide_index=True,
            column_config={ 
                "SALÁRIO BASE (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO BRUTA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "PRODUÇÃO LÍQUIDA (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "TOTAL GRATIFICAÇÕES (R$)": st.column_config.NumberColumn(format="R$ %.2f"), 
                "SALÁRIO A RECEBER (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Situação": st.column_config.TextColumn() 
            }
        )

        
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            excel_data = utils.to_excel(df_filtrado_final[colunas_exibicao])
            st.download_button(
                label="📥 Baixar Resumo em Excel", data=excel_data,
                file_name=f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col_dl2:
            lancamentos_para_pdf_final = lancamentos_filtrados_df.copy()
            if funcionario_filtrado != "Todos":
                 if not lancamentos_para_pdf_final.empty:
                      lancamentos_para_pdf_final = lancamentos_para_pdf_final[lancamentos_para_pdf_final['Funcionário'] == funcionario_filtrado]
            
            colunas_lancamentos_pdf = ['Data', 'Data do Serviço', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Unidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
            if st.session_state['role'] != 'admin' or (obra_filtrada and obra_filtrada != "Todas"):
                 if 'Obra' in colunas_lancamentos_pdf: colunas_lancamentos_pdf.remove('Obra')

            if lancamentos_para_pdf_final.empty:
                lancamentos_para_pdf = pd.DataFrame(columns=colunas_lancamentos_pdf)
            else:
                cols_lanc_existentes = [col for col in colunas_lancamentos_pdf if col in lancamentos_para_pdf_final.columns]
                lancamentos_para_pdf = lancamentos_para_pdf_final[cols_lanc_existentes]


            if st.button("📄 Baixar Resumo em PDF", use_container_width=True):
                 with st.spinner("Gerando PDF..."):
                    pdf_data = utils.gerar_relatorio_pdf( 
                        resumo_df=df_filtrado_final[colunas_exibicao], 
                        lancamentos_df=lancamentos_para_pdf, 
                        logo_path="Lavie.png",
                        mes_referencia=mes_selecionado,
                        obra_nome=obra_relatorio_nome 
                    )
                    if pdf_data: 
                        st.download_button(
                            label="⬇️ Clique aqui para baixar o PDF", data=pdf_data,
                            file_name=f"resumo_folha_{mes_selecionado}_{obra_relatorio_nome or 'Geral'}.pdf",
                            mime="application/pdf", use_container_width=True,
                            key="pdf_download_resumo_final" 
                        )
                        st.info("Seu download está pronto. Clique no botão acima.")




