import streamlit as st
import db_utils
import pandas as pd 
import utils
from datetime import datetime

@st.dialog("Editar Lançamento")
def abrir_modal_edicao(row, precos_df):
    id_lanc = row['id']
    data_atual = pd.to_datetime(row['Data']).date()
    servico_atual_nome = row['Serviço']
    obs_atual = row['Observação']
    qtd_atual = float(row['Quantidade'])
    valor_total_atual = float(row['Valor Parcial'])
    valor_unit_atual_calculado = valor_total_atual / qtd_atual if qtd_atual > 0 else 0

    st.write(f"Editando lançamento **#{id_lanc}** de **{row['Funcionário']}**")
    
    disciplina_atual_guess = None
    servico_row = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_atual_nome]
    
    if not servico_row.empty:
        disciplina_atual_guess = servico_row.iloc[0]['DISCIPLINA']
    
    disciplinas = sorted(precos_df['DISCIPLINA'].unique())
    
    idx_disc = disciplines.index(disciplina_atual_guess) if disciplina_atual_guess in disciplinas else None
    disciplina_sel = st.selectbox("Disciplina", options=disciplinas, index=idx_disc, key="edit_disc")
    
    opcoes_servico = []
    if disciplina_sel:
        opcoes_servico = sorted(precos_df[precos_df['DISCIPLINA'] == disciplina_sel]['DESCRIÇÃO DO SERVIÇO'].unique())
    
    idx_serv = opcoes_servico.index(servico_atual_nome) if servico_atual_nome in opcoes_servico else None
    servico_sel = st.selectbox("Serviço", options=opcoes_servico, index=idx_serv, key="edit_serv")
    
    col_q, col_v = st.columns(2)
    with col_q:
        nova_qtd = st.number_input("Quantidade", value=qtd_atual, step=0.1, min_value=0.01, format="%.2f")
    with col_v:
        novo_valor_unit = valor_unit_atual_calculado
        if servico_sel:
            preco_tab = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_sel].iloc[0]['VALOR']
            novo_valor_unit = st.number_input("Valor Unitário", value=float(preco_tab), step=0.5, format="%.2f")
    
    nova_data = st.date_input("Data do Serviço", value=data_atual)
    nova_obs = st.text_area("Observação", value=obs_atual)

    st.markdown("---")
    col_b1, col_b2 = st.columns(2)
    
    if col_b2.button("Salvar Alterações", type="primary", use_container_width=True):
        if servico_sel:
            servico_id_novo = int(precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_sel].iloc[0]['id'])
            
            if db_utils.atualizar_lancamento_completo(
                id_lanc, nova_data, servico_id_novo, None, nova_qtd, novo_valor_unit, nova_obs
            ):
                st.success("Atualizado com sucesso!")
                st.rerun()
        else:
            st.error("Selecione um serviço válido.")

def render_page():
    mes_selecionado = st.session_state.selected_month
    
    @st.cache_data
    def get_remove_page_data(mes):
        lancamentos_df = db_utils.get_lancamentos_do_mes(mes)
        obras_df = db_utils.get_obras() 
        folhas_df = db_utils.get_folhas_mensais(mes)
        precos_df = db_utils.get_precos() 
        return lancamentos_df, obras_df, folhas_df, precos_df

    lancamentos_df, obras_df, folhas_df, precos_df = get_remove_page_data(mes_selecionado)
    
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
            if not obra_info.empty: obra_id_para_verificar = int(obra_info.iloc[0]['id'])
            
            funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
            funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="rl_func_user")
            if funcionario_filtrado: df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
        else:
            filtro_col1, filtro_col2 = st.columns(2)
            with filtro_col1:
                obras_disponiveis = sorted(df_filtrado['Obra'].unique())
                obras_filtradas_nomes = st.multiselect("Filtrar por Obra(s):", options=obras_disponiveis, key="rl_obras_admin")
                if obras_filtradas_nomes:
                    df_filtrado = df_filtrado[df_filtrado['Obra'].isin(obras_filtradas_nomes)]
                    if len(obras_filtradas_nomes) == 1:
                         obra_info = obras_df[obras_df['NOME DA OBRA'] == obras_filtradas_nomes[0]]
                         if not obra_info.empty: obra_id_para_verificar = int(obra_info.iloc[0]['id'])
            with filtro_col2:
                funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
                funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="rl_func_admin")
                if funcionario_filtrado: df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
      
        if df_filtrado.empty:
            st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        else:
            edicao_bloqueada = False
            status_folha = "Não Enviada" 
            if obra_id_para_verificar:
                folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_para_verificar]
                if not folha_do_mes.empty:
                    status_folha = folha_do_mes['status'].iloc[0]
            
                admin_bloqueado = st.session_state['role'] == 'admin' and status_folha == "Finalizada"
                user_bloqueado = st.session_state['role'] == 'user' and status_folha in ['Enviada para Auditoria', 'Finalizada']

                if admin_bloqueado or user_bloqueado:
                    edicao_bloqueada = True
                    st.error(f"Mês Fechado: Status '{status_folha}'. Edição/Remoção bloqueada.")

            df_filtrado['Remover'] = False
            df_filtrado['Editar'] = False 
            
            colunas_visiveis = ['id', 'Editar', 'Remover', 'Data', 'Obra', 'Funcionário', 'Serviço', 'Quantidade', 'Valor Parcial', 'Observação']
            
            if edicao_bloqueada:
                config_disabled = True
            else:
                config_disabled = df_filtrado.columns.drop(['Remover', 'Editar']) 

            df_modificado = st.data_editor(
                df_filtrado[colunas_visiveis],
                hide_index=True,
                key="rl_data_editor",
                column_config={
                    "id": None, 
                    "Remover": st.column_config.CheckboxColumn(width="small"),
                    "Editar": st.column_config.CheckboxColumn(width="small"),
                    "Data": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                    "Quantidade": st.column_config.NumberColumn("Qtd", format="%.2f"),
                    "Valor Parcial": st.column_config.NumberColumn("Valor", format="R$ %.2f")
                },
                disabled=config_disabled
            )
            
            linhas_para_editar = df_modificado[df_modificado['Editar']]
            
            if not linhas_para_editar.empty:
                if len(linhas_para_editar) > 1:
                    st.warning("Selecione apenas um item por vez para editar.")
                else:
                    row_to_edit = linhas_para_editar.iloc[0]
                    abrir_modal_edicao(row_to_edit, precos_df)

            linhas_para_remover = df_modificado[df_modificado['Remover']]
            if not linhas_para_remover.empty:
                st.divider()
                st.warning(f"Você selecionou {len(linhas_para_remover)} item(ns) para remoção permanente:")
                
                razao_remocao = ""
                if st.session_state['role'] == 'admin':
                    razao_remocao = st.text_input("Justificativa (Admin):", key="rl_razao_remocao")

                col_confirm, col_btn_del = st.columns([3, 1])
                with col_confirm:
                    confirmacao = st.checkbox("Confirmo que esta ação é irreversível.", key="rl_confirmacao_remocao")
                
                is_disabled = edicao_bloqueada or (st.session_state['role'] == 'admin' and not razao_remocao.strip()) or not confirmacao

                with col_btn_del:
                    if st.button("Remover Selecionados", disabled=is_disabled, type="primary", key="rl_remover_btn"):
                        ids_a_remover = linhas_para_remover['id'].tolist()
                        if db_utils.remover_lancamentos_por_id(ids_a_remover, razao_remocao, obra_id_para_verificar, mes_selecionado):
                            st.success("Removido com sucesso!")
                            st.cache_data.clear() 
                            st.rerun()
