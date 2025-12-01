import streamlit as st
import db_utils
import pandas as pd 
import utils
from datetime import datetime

@st.dialog("Editar Lançamento")
def abrir_modal_edicao(row, precos_df):
    id_lanc = int(row['id']) 
    
    data_atual = pd.to_datetime(row['Data']).date()
    obs_atual = row['Observação'] if row['Observação'] else ""
    qtd_atual = float(row['Quantidade'])
    
    valor_unit_atual = float(row['Valor Unitário']) if pd.notna(row['Valor Unitário']) else 0.0
    valor_total_atual = float(row['Valor Parcial'])
    
    tipo_lancamento = row['Disciplina'] 
    nome_servico_atual = row['Serviço']

    st.markdown(f"**Tipo:** `{tipo_lancamento}` | **Original:** {nome_servico_atual}")
    st.markdown("---")

  
    if tipo_lancamento == 'GRATIFICAÇÃO':
        nova_descricao = st.text_input("Descrição da Gratificação", value=nome_servico_atual)
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            nova_qtd = st.number_input("Quantidade", value=1.0, disabled=True)
        with col_g2:
            novo_valor_unit = st.number_input("Valor Total (R$)", value=valor_total_atual, step=50.0, format="%.2f")
        
        novo_servico_id = None
        novo_servico_diverso_desc = f"[GRATIFICACAO] {nova_descricao}"

    elif tipo_lancamento == 'Diverso':
        nova_descricao = st.text_input("Descrição do Item", value=nome_servico_atual)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            nova_qtd = st.number_input("Quantidade", value=qtd_atual, step=0.1, min_value=0.01, format="%.2f")
        with col_d2:
            novo_valor_unit = st.number_input("Valor Unitário (R$)", value=valor_unit_atual, step=1.0, format="%.2f")
            
        novo_servico_id = None
        novo_servico_diverso_desc = nova_descricao

    else:
        disciplinas = sorted(precos_df['DISCIPLINA'].unique())
        idx_disc = disciplinas.index(tipo_lancamento) if tipo_lancamento in disciplinas else 0
        disciplina_sel = st.selectbox("Disciplina", options=disciplinas, index=idx_disc, key="edit_disc")
        
        opcoes_servico = []
        if disciplina_sel:
            opcoes_servico = sorted(precos_df[precos_df['DISCIPLINA'] == disciplina_sel]['DESCRIÇÃO DO SERVIÇO'].unique())
        
        idx_serv = 0
        if nome_servico_atual in opcoes_servico:
            idx_serv = opcoes_servico.index(nome_servico_atual)
            
        servico_sel = st.selectbox("Serviço", options=opcoes_servico, index=idx_serv, key="edit_serv")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            nova_qtd = st.number_input("Quantidade", value=qtd_atual, step=0.1, min_value=0.01, format="%.2f")
        with col_s2:
            preco_sugerido = valor_unit_atual
            if servico_sel != nome_servico_atual and servico_sel:
                 try:
                     preco_tab = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_sel].iloc[0]['VALOR']
                     preco_sugerido = float(preco_tab)
                 except: pass
            
            novo_valor_unit = st.number_input("Valor Unitário (R$)", value=preco_sugerido, step=0.5, format="%.2f")

        novo_servico_diverso_desc = None
        novo_servico_id = None
        if servico_sel:
             try:
                novo_servico_id = int(precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_sel].iloc[0]['id'])
             except: pass
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        nova_data = st.date_input("Data do Serviço", value=data_atual)
    with col_c2:
        st.metric("Novo Total", utils.format_currency(nova_qtd * novo_valor_unit))

    nova_obs = st.text_area("Observação Original", value=obs_atual)
    
    justificativa_admin = ""
    if st.session_state['role'] == 'admin':
        st.warning("Edição de Auditoria: Justificativa Obrigatória")
        justificativa_admin = st.text_area("Motivo da Alteração (Aparecerá no comentário)", placeholder="Ex: Quantidade corrigida conforme medição in loco...")

    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        erro_validacao = False
        if tipo_lancamento not in ['GRATIFICAÇÃO', 'Diverso'] and not novo_servico_id:
            st.error("Selecione um serviço válido.")
            erro_validacao = True
        
        if st.session_state['role'] == 'admin' and not justificativa_admin.strip():
            st.error("É obrigatório justificar a alteração.")
            erro_validacao = True
            
        if not erro_validacao:
            obs_final = nova_obs
            if st.session_state['role'] == 'admin':
                tag_auditoria = f" | [AUDITORIA]: {justificativa_admin}"
                obs_final = f"{nova_obs}{tag_auditoria}".strip()
                if nova_obs == "": obs_final = f"[AUDITORIA]: {justificativa_admin}"

            sucesso = db_utils.atualizar_lancamento_completo(
                id_lanc, nova_data, novo_servico_id, novo_servico_diverso_desc, 
                nova_qtd, novo_valor_unit, obs_final
            )
            if sucesso:
                st.success("Lançamento atualizado com sucesso!")
                st.rerun()

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
            msg_bloqueio = ""
            status_folha = "Não Enviada" 
            
            if obra_id_para_verificar:
                folha_do_mes = folhas_df[folhas_df['obra_id'] == obra_id_para_verificar]
                if not folha_do_mes.empty:
                    status_folha = folha_do_mes['status'].iloc[0]
                
                if st.session_state['role'] == 'user':
                    if status_folha in ['Enviada para Auditoria', 'Finalizada']:
                        edicao_bloqueada = True
                        msg_bloqueio = f"Mês Fechado: Status '{status_folha}'. Edição bloqueada para usuários."
                
                elif st.session_state['role'] == 'admin':
                    if status_folha != 'Enviada para Auditoria':
                        edicao_bloqueada = True
                        if status_folha == 'Finalizada':
                            msg_bloqueio = f"Folha Finalizada: Edição bloqueada permanentemente."
                        else:
                            msg_bloqueio = f"Modo Leitura: Admin só pode editar quando for 'Enviada para Auditoria'. (Status atual: {status_folha})"

            if edicao_bloqueada:
                st.error(msg_bloqueio)

            df_filtrado['Remover'] = False
            df_filtrado['Editar'] = False
            
            colunas_visiveis = ['id', 'Editar', 'Remover', 'Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação']
            
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
                    "Remover": st.column_config.CheckboxColumn(width="medium"),
                    "Editar": st.column_config.CheckboxColumn(width="small"),
                    "Data": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                    "Quantidade": st.column_config.NumberColumn("Qtd", format="%.2f"),
                    "Valor Unitário": st.column_config.NumberColumn("Unit.", format="R$ %.2f"), 
                    "Valor Parcial": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    "Disciplina": st.column_config.TextColumn(width="medium"),
                    "Serviço": st.column_config.TextColumn(width="large"),
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
                    st.markdown("**Justificativa de Auditoria (Remoção)**")
                    razao_remocao = st.text_input("Motivo da remoção (Obrigatório):", key="rl_razao_remocao")
                
                col_confirm, col_btn_del = st.columns([3, 1])
                with col_confirm:
                    confirmacao = st.checkbox("Confirmo que esta ação é irreversível.", key="rl_confirmacao_remocao")
                
                bloqueio_justificativa = (st.session_state['role'] == 'admin' and not razao_remocao.strip())
                is_disabled = edicao_bloqueada or bloqueio_justificativa or not confirmacao

                with col_btn_del:
                    if st.button("Remover Selecionados", disabled=is_disabled, type="primary", key="rl_remover_btn"):
                        ids_a_remover = linhas_para_remover['id'].tolist()
                        if db_utils.remover_lancamentos_por_id(ids_a_remover, razao_remocao, obra_id_para_verificar, mes_selecionado):
                            st.success("Removido com sucesso!")
                            st.cache_data.clear() 
                            st.rerun()



