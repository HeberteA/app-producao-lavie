import streamlit as st
import pandas as pd
import db_utils
import utils

def render_page():
    mes_selecionado = st.session_state.selected_month
    funcionarios_df = db_utils.get_funcionarios()
    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    status_df = db_utils.get_status_do_mes(mes_selecionado)
    obras_df = db_utils.get_obras()

    st.header("Resumo da Folha")
    
    base_para_resumo = funcionarios_df.copy()
    
    if st.session_state['role'] == 'user':
        base_para_resumo = base_para_resumo[base_para_resumo['OBRA'] == st.session_state['obra_logada']]
        funcionarios_disponiveis = sorted(base_para_resumo['NOME'].unique())
        funcionarios_filtrados = st.multiselect(
            "Filtrar por Funcionário(s) específico(s):", 
            options=funcionarios_disponiveis, key="rf_func_user"
        )
        if funcionarios_filtrados:
            base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
    else: 
        filtro_col1, filtro_col2 = st.columns(2)
        with filtro_col1:
            obras_disponiveis = sorted(obras_df['NOME DA OBRA'].unique())
            obras_filtradas = st.multiselect(
                "Filtrar por Obra(s)", options=obras_disponiveis, key="rf_obras_admin"
            )
            if obras_filtradas:
                base_para_resumo = base_para_resumo[base_para_resumo['OBRA'].isin(obras_filtradas)]
        with filtro_col2:
            funcionarios_disponiveis = sorted(base_para_resumo['NOME'].unique())
            funcionarios_filtrados = st.multiselect(
                "Filtrar por Funcionário(s):", options=funcionarios_disponiveis, key="rf_func_admin"
            )
            if funcionarios_filtrados:
                base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]

    if base_para_resumo.empty:
        st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
    else:
        producao_por_funcionario = lancamentos_df.groupby('funcionario_id')['Valor Parcial'].sum().reset_index() 
        producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)

        base_para_resumo.rename(columns={'id': 'funcionario_id'}, inplace=True)

        resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, on='funcionario_id', how='left') 
        resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0.0)

        resumo_com_status_df = pd.merge(
            resumo_df,
            status_df[['funcionario_id', 'obra_id', 'Status', 'Lancamentos Concluidos']], 
            on=['funcionario_id', 'obra_id'],
            how='left'
        )
        resumo_com_status_df['Status'] = resumo_com_status_df['Status'].fillna('A Revisar')
        if 'Lancamentos Concluidos' not in resumo_com_status_df.columns:
            resumo_com_status_df['Lancamentos Concluidos'] = False
        resumo_com_status_df['Lancamentos Concluidos'] = resumo_com_status_df['Lancamentos Concluidos'].fillna(False)


        resumo_final_df = resumo_com_status_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})

        if 'SALÁRIO BASE (R$)' not in resumo_final_df.columns: resumo_final_df['SALÁRIO BASE (R$)'] = 0.0
        resumo_final_df['SALÁRIO BASE (R$)'] = resumo_final_df['SALÁRIO BASE (R$)'].fillna(0)
        resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(utils.calcular_salario_final, axis=1)

        resumo_final_df['Situação'] = resumo_final_df['Lancamentos Concluidos'].apply(
            lambda concluido: 'Concluído' if concluido else 'Pendente'
        )

        colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)', 'Status', 'Situação']
        if st.session_state['role'] == 'admin':
            colunas_finais.insert(1, 'OBRA')

        colunas_existentes = [col for col in colunas_finais if col in resumo_final_df.columns]
        resumo_final_df = resumo_final_df[colunas_existentes].reset_index(drop=True)

        st.dataframe(
            resumo_final_df.style.format({
                'SALÁRIO BASE (R$)': 'R$ {:,.2f}',
                'PRODUÇÃO (R$)': 'R$ {:,.2f}',
                'SALÁRIO A RECEBER (R$)': 'R$ {:,.2f}'
            }).applymap(
                utils.style_status, subset=['Status']
            ).applymap(
                utils.style_situacao, subset=['Situação'] 
            ),
            use_container_width=True,
            hide_index=True
        )
