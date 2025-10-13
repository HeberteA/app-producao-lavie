import streamlit as st
import db_utils

def render_page():
    mes_selecionado = st.session_state.selected_month
    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    
    st.header("Gerenciar Lançamentos")
    
    if lancamentos_df.empty:
        st.info("Não há lançamentos para gerenciar no mês selecionado.")
    else:
        df_filtrado = lancamentos_df.copy()

        if st.session_state['role'] == 'user':
            df_filtrado = df_filtrado[df_filtrado['Obra'] == st.session_state['obra_logada']]
            funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="rl_func_user")
            if funcionario_filtrado:
                df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
        else:
            filtro_col1, filtro_col2 = st.columns(2)
            with filtro_col1:
                obras_disponiveis = sorted(df_filtrado['Obra'].unique())
                obras_filtradas_nomes = st.multiselect("Filtrar por Obra(s):", options=obras_disponiveis, key="rl_obras_admin")
                if obras_filtradas_nomes:
                    df_filtrado = df_filtrado[df_filtrado['Obra'].isin(obras_filtradas_nomes)]
            with filtro_col2:
                funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
                funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="rl_func_admin")
                if funcionario_filtrado:
                    df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
      
        if df_filtrado.empty:
            st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        else:
            df_filtrado['Remover'] = False
            colunas_visiveis = ['id', 'Remover', 'Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação']
            
            df_modificado = st.data_editor(
                df_filtrado[colunas_visiveis],
                hide_index=True,
                key="rl_data_editor",
                column_config={"id": None, "Remover": st.column_config.CheckboxColumn(required=True)},
                disabled=df_filtrado.columns.drop(['Remover'])
            )
          
            linhas_para_remover = df_modificado[df_modificado['Remover']]
        
            if not linhas_para_remover.empty:
                st.warning("Você selecionou os seguintes lançamentos para remoção permanente:")
                st.dataframe(linhas_para_remover.drop(columns=['Remover'])) 
            
                razao_remocao = ""
                if st.session_state['role'] == 'admin':
                    razao_remocao = st.text_area("Justificativa para remoção (obrigatório):", key="rl_razao_remocao")

                confirmacao = st.checkbox("Sim, confirmo a remoção.", key="rl_confirmacao_remocao")
            
                is_disabled = (st.session_state['role'] == 'admin' and not razao_remocao.strip()) or not confirmacao

                if st.button("Remover Itens Selecionados", disabled=is_disabled, type="primary", key="rl_remover_btn"):
                    ids_a_remover = linhas_para_remover['id'].tolist()
                    if db_utils.remover_lancamentos_por_id(ids_a_remover, razao_remocao):
                        st.success("Lançamentos removidos!")
                        st.cache_data.clear()
                        st.rerun()

