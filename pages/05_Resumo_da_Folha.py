import streamlit as st
import pandas as pd
import db_utils
import utils

if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.error("Por favor, faça o login primeiro na página principal.")
    st.stop()

engine = db_utils.get_db_connection()
if engine is None:
    st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
    st.stop()

mes_selecionado = st.session_state.selected_month
funcionarios_df = db_utils.get_funcionarios(engine)
lancamentos_df = db_utils.get_lancamentos_do_mes(engine, mes_selecionado)
status_df = db_utils.get_status_do_mes(engine, mes_selecionado)
obras_df = db_utils.get_obras(engine)

st.header("Resumo da Folha")

base_para_resumo = funcionarios_df.copy()

if st.session_state['role'] == 'user':
    base_para_resumo = base_para_resumo[base_para_resumo['OBRA'] == st.session_state['obra_logada']]
    funcionarios_disponiveis = base_para_resumo['NOME'].unique()
    funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s) específico(s):", options=funcionarios_disponiveis, key="resumo_func_user")
    if funcionarios_filtrados:
        base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
else: 
    filtro_col1, filtro_col2 = st.columns(2)
    with filtro_col1:
        obras_disponiveis = obras_df['NOME DA OBRA'].unique()
        obras_filtradas = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis, key="resumo_obras_admin")
        if obras_filtradas:
            base_para_resumo = base_para_resumo[base_para_resumo['OBRA'].isin(obras_filtradas)]
    
    with filtro_col2:
        funcionarios_disponiveis = base_para_resumo['NOME'].unique()
        funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s):", options=funcionarios_disponiveis, key="resumo_func_admin")
        if funcionarios_filtrados:
            base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]

if base_para_resumo.empty:
    st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
else:
    producao_por_funcionario = lancamentos_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
    producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
    
    resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
    resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
    
    if 'Funcionário' in resumo_df.columns:
        resumo_df = resumo_df.drop(columns=['Funcionário'])

    resumo_df.rename(columns={'id': 'funcionario_id'}, inplace=True)
    
    resumo_com_status_df = pd.merge(
        resumo_df,
        status_df,
        on=['funcionario_id', 'obra_id'],
        how='left'
    )

    resumo_com_status_df['Status'] = resumo_com_status_df['Status'].fillna('A Revisar')
    resumo_final_df = resumo_com_status_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
    resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(utils.calcular_salario_final, axis=1)

    colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)', 'Status']
    if st.session_state['role'] == 'admin':
        colunas_finais.insert(1, 'OBRA')

    resumo_final_df = resumo_final_df[colunas_finais].reset_index(drop=True)
    
    st.dataframe(
        resumo_final_df.style.format({
            'SALÁRIO BASE (R$)': 'R$ {:,.2f}',
            'PRODUÇÃO (R$)': 'R$ {:,.2f}',
            'SALÁRIO A RECEBER (R$)': 'R$ {:,.2f}'
        }).applymap(
            utils.style_status, subset=['Status']
        ),
        use_container_width=True
    )

