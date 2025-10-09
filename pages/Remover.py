import streamlit as st
import pandas as pd
import db_utils

if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.error("Por favor, faça o login primeiro na página principal.")
    st.stop()

engine = db_utils.get_db_connection()
if engine is None:
    st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
    st.stop()

mes_selecionado = st.session_state.selected_month
lancamentos_df = db_utils.get_lancamentos_do_mes(engine, mes_selecionado)
obras_df = db_utils.get_obras(engine)

st.header("Gerenciar Lançamentos 🗑️")

if lancamentos_df.empty:
    st.info("Não há lançamentos para gerenciar no mês selecionado.")
else:
    df_filtrado = lancamentos_df.copy()

    if st.session_state['role'] == 'user':
        df_filtrado = df_filtrado[df_filtrado['Obra'] == st.session_state['obra_logada']]
        funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
        funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_user")
        if funcionario_filtrado:
            df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
    else: 
        filtro_col1, filtro_col2 = st.columns(2)
        with filtro_col1:
            obras_disponiveis = sorted(df_filtrado['Obra'].unique())
            obras_filtradas_nomes = st.multiselect("Filtrar por Obra(s):", options=obras_disponiveis, key="editar_obras_admin")
            if obras_filtradas_nomes:
                df_filtrado = df_filtrado[df_filtrado['Obra'].isin(obras_filtradas_nomes)]
            
        with filtro_col2:
            funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_admin")
            if funcionario_filtrado:
                df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
  
    if df_filtrado.empty:
        st.info("Nenhum lançamento encontrado para os filtros selecionados.")
    else:
        df_filtrado['Remover'] = False
    
        colunas_visiveis = [
            'id', 'Remover', 'Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 
            'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação', 'Data do Serviço'
        ]
        
        st.write("Marque as caixas dos lançamentos que deseja apagar e clique no botão de remoção.")
      
        df_modificado = st.data_editor(
            df_filtrado[colunas_visiveis],
            hide_index=True,
            column_config={
                "id": None, 
                "Remover": st.column_config.CheckboxColumn(required=True),
                "Valor Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor Parcial": st.column_config.NumberColumn(format="R$ %.2f")
            },
            disabled=df_filtrado.columns.drop(['Remover'], errors='ignore') 
        )
      
        linhas_para_remover = df_modificado[df_modificado['Remover']]
    
        if not linhas_para_remover.empty:
            st.warning("Atenção! Você selecionou os seguintes lançamentos para remoção permanente:")
            st.dataframe(linhas_para_remover.drop(columns=['Remover'], errors='ignore')) 
        
            razao_remocao = ""
            if st.session_state['role'] == 'admin':
                razao_remocao = st.text_area("Justificativa para a remoção (obrigatório):", key="razao_remocao_admin")

            confirmacao_remocao = st.checkbox("Sim, confirmo que desejo remover os itens selecionados.")
        
            is_disabled = not confirmacao_remocao
            if st.session_state['role'] == 'admin':
               is_disabled = not confirmacao_remocao or not razao_remocao.strip()

            if st.button("Remover Itens Selecionados", disabled=is_disabled, type="primary"):
                ids_a_remover = linhas_para_remover['id'].tolist()
                if db_utils.remover_lancamentos_por_id(ids_a_remover, engine, razao_remocao):
                    st.cache_data.clear()
                    st.rerun()

