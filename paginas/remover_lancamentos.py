import streamlit as st
import db_utils
import pandas as pd 

def render_page():
    mes_selecionado = st.session_state.selected_month
    
    @st.cache_data
    def get_remove_page_data(mes):
        lancamentos_df = db_utils.get_lancamentos_do_mes(mes)
        obras_df = db_utils.get_obras() 
        folhas_df = db_utils.get_folhas_mensais(mes)
        return lancamentos_df, obras_df, folhas_df

    lancamentos_df, obras_df, folhas_df = get_remove_page_data(mes_selecionado)
    
    st.header("Gerenciar Lançamentos")
    
    if lancamentos_df.empty:
        st.info("Não há lançamentos para gerenciar no mês selecionado.")
    else:
        df_filtrado = lancamentos_df.copy()
        obra_id_para_verificar = None
        
        if st.session_state['role'] == 'user':
            obra_logada_nome = st.session_state['obra_logada']
            df_filtrado = df_filtrado[df_filtrado['Obra'] == obra_logada_nome]
            
            obra_info = obras_df[obras_df['NOME DA OBRA'] == obra_logada_nome]
            if not obra_info.empty:
                obra_id_para_verificar = int(obra_info.iloc[0]['id'])

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
                    if len(obras_filtradas_nomes) == 1:
                         obra_info = obras_df[obras_df['NOME DA OBRA'] == obras_filtradas_nomes[0]]
                         if not obra_info.empty:
                             obra_id_para_verificar = int(obra_info.iloc[0]['id'])

            with filtro_col2:
                funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
                funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="rl_func_admin")
                if funcionario_filtrado:
                    df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
      
        if df_filtrado.empty:
            st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        else:
            edicao_bloqueada = False
            status_folha = "Não Enviada" 
            if obra_id_para_verificar:
                folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_para_verificar]
                if not folha_do_mes.empty:
                    status_folha = folha_do_mes['status'].iloc[0]
                
                if status_folha in ['Enviada para Auditoria', 'Finalizada']:
                    edicao_bloqueada = True
                    st.error(f"Mês Fechado: A folha da obra selecionada está com status '{status_folha}'. A remoção de lançamentos está bloqueada.")

            df_filtrado['Remover'] = False
            colunas_visiveis = ['id', 'Remover', 'Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação']
            
            df_modificado = st.data_editor(
                df_filtrado[colunas_visiveis],
                hide_index=True,
                key="rl_data_editor",
                column_config={
                    "id": None, 
                    "Remover": st.column_config.CheckboxColumn(required=True),
                    "Data": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                    "Quantidade": st.column_config.NumberColumn(
                        "Quantidade",
                        format="%.2f" 
                    ),
                    "Valor Parcial": st.column_config.NumberColumn(
                        "Valor Parcial",
                        format="R$ %.2f" 
                    )
                },
                disabled=df_filtrado.columns.drop(['Remover']) 
            )
          
            linhas_para_remover = df_modificado[df_modificado['Remover']]
        
            if not linhas_para_remover.empty:
                st.warning("Você selecionou os seguintes lançamentos para remoção permanente:")
                st.dataframe(
                     linhas_para_remover.drop(columns=['Remover']),
                     column_config={
                         "Data": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                         "Quantidade": st.column_config.NumberColumn("Quantidade", format="%.2f"),
                         "Valor Parcial": st.column_config.NumberColumn("Valor Parcial", format="R$ %.2f")
                     }
                )
            
                razao_remocao = ""
                if st.session_state['role'] == 'admin':
                    razao_remocao = st.text_area("Justificativa para remoção (obrigatório):", key="rl_razao_remocao")

                confirmacao = st.checkbox("Sim, confirmo a remoção.", key="rl_confirmacao_remocao")
            
                is_disabled = edicao_bloqueada or (st.session_state['role'] == 'admin' and not razao_remocao.strip()) or not confirmacao

                if st.button("Remover Itens Selecionados", disabled=is_disabled, type="primary", key="rl_remover_btn"):
                    ids_a_remover = linhas_para_remover['id'].tolist()
                    
                    if db_utils.remover_lancamentos_por_id(ids_a_remover, razao_remocao, obra_id_para_verificar, mes_selecionado):
                        st.success("Lançamentos removidos!")
                        st.cache_data.clear() # Limpa o cache
                        st.rerun()
