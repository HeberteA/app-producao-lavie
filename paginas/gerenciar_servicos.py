import streamlit as st
import db_utils
import pandas as pd

def render_page():
    if st.session_state['role'] != 'admin':
        st.error("Acesso negado.")
        st.stop()

    st.header("Gerenciar Serviços e Disciplinas 🛠️")

    @st.cache_data
    def get_servicos_e_disciplinas_data():
        all_servicos_df = db_utils.get_all_servicos()
        all_disciplinas_df = db_utils.get_all_disciplinas()
        active_disciplinas_df = db_utils.get_disciplinas()
        return all_servicos_df, all_disciplinas_df, active_disciplinas_df

    all_servicos_df, all_disciplinas_df, active_disciplinas_df = get_servicos_e_disciplinas_data()

    tab_disciplinas, tab_add_servico, tab_manage_servico = st.tabs([
        "Gerenciar Disciplinas", 
        "Adicionar Serviço", 
        "Gerenciar Serviços"
    ])

    with tab_disciplinas:
        st.subheader("Gerenciar Disciplinas")
        st.info("Disciplinas são as categorias principais (ex: ESTRUTURA, HIDRÁULICA).")

        col_add_disc, col_manage_disc = st.columns(2)

        with col_add_disc:
            st.markdown("##### Adicionar Nova Disciplina")
            with st.form("gs_add_disciplina_form", clear_on_submit=True):
                nome_disciplina = st.text_input("Nome da Nova Disciplina")
                submitted_disc = st.form_submit_button("Adicionar Disciplina", type="primary")
                if submitted_disc:
                    if not nome_disciplina.strip():
                        st.warning("O nome da disciplina não pode estar em branco.")
                    else:
                        with st.spinner("Adicionando..."):
                            if db_utils.adicionar_disciplina(nome_disciplina.upper()):
                                st.success(f"Disciplina '{nome_disciplina.upper()}' adicionada!")
                                st.cache_data.clear()
                                st.rerun()

        with col_manage_disc:
            st.markdown("##### Ativar / Inativar Disciplina")
            if all_disciplinas_df.empty:
                st.info("Nenhuma disciplina cadastrada.")
            else:
                disciplina_selecionada_nome = st.selectbox(
                    "Selecione uma disciplina para gerenciar",
                    options=sorted(all_disciplinas_df['nome'].unique()),
                    index=None,
                    placeholder="Selecione uma disciplina..."
                )
                
                if disciplina_selecionada_nome:
                    disciplina_atual = all_disciplinas_df[all_disciplinas_df['nome'] == disciplina_selecionada_nome].iloc[0]
                    disciplina_id = int(disciplina_atual['id'])
                    disciplina_ativa = bool(disciplina_atual['ativo'])

                    if disciplina_ativa:
                        st.warning(f"A disciplina '{disciplina_selecionada_nome}' está **Ativa**.")
                        if st.button("🚫 Inativar Disciplina", key=f"inativar_disc_{disciplina_id}"):
                            # Robustez: Verifica se a disciplina está em uso
                            servicos_usando = all_servicos_df[
                                (all_servicos_df['DISCIPLINA'] == disciplina_selecionada_nome) & 
                                (all_servicos_df['ativo'] == True)
                            ]
                            if not servicos_usando.empty:
                                st.error(f"Não é possível inativar. Esta disciplina é usada por {len(servicos_usando)} serviço(s) ativo(s). Inative os serviços primeiro.")
                            else:
                                with st.spinner("Inativando..."):
                                    if db_utils.inativar_disciplina(disciplina_id):
                                        st.success("Disciplina inativada!")
                                        st.cache_data.clear()
                                        st.rerun()
                    else:
                        st.success(f"A disciplina '{disciplina_selecionada_nome}' está **Inativa**.")
                        if st.button("✅ Reativar Disciplina", key=f"reativar_disc_{disciplina_id}"):
                            with st.spinner("Reativando..."):
                                if db_utils.reativar_disciplina(disciplina_id):
                                    st.success("Disciplina reativada!")
                                    st.cache_data.clear()
                                    st.rerun()

    with tab_add_servico:
        st.subheader("Adicionar Novo Serviço (Descrição)")
        
        if active_disciplinas_df.empty:
            st.error("Nenhuma disciplina ativa cadastrada. Vá para a aba 'Gerenciar Disciplinas' para adicionar uma.")
        else:
            with st.form("gs_add_servico_form", clear_on_submit=True):
                
                mapa_disciplinas = active_disciplinas_df.set_index('nome')['id'].to_dict()
                disciplina_nome = st.selectbox(
                    "1. Selecione a Disciplina",
                    options=sorted(mapa_disciplinas.keys())
                )
                
                st.markdown("---")
                descricao = st.text_input("2. Descrição do Serviço")
                col_unid, col_val = st.columns(2)
                with col_unid:
                    unidade = st.text_input("3. Unidade")
                with col_val:
                    valor_unitario = st.number_input("4. Valor Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")
                
                submitted = st.form_submit_button("Adicionar Serviço", type="primary")
                if submitted:
                    if not all([disciplina_nome, descricao, unidade, valor_unitario > 0]):
                        st.warning("Por favor, preencha todos os campos. O valor unitário deve ser maior que zero.")
                    else:
                        disciplina_id = int(mapa_disciplinas[disciplina_nome])
                        with st.spinner("Adicionando serviço..."):
                            if db_utils.adicionar_servico(disciplina_id, descricao, unidade.upper(), valor_unitario):
                                st.success(f"Serviço '{descricao}' adicionado com sucesso!")
                                st.cache_data.clear()
                                st.rerun()

    with tab_manage_servico:
        st.subheader("Gerenciar Serviços Existentes")
        
        if all_servicos_df.empty:
            st.info("Nenhum serviço cadastrado.")
        else:
            col_filtro1, col_filtro2 = st.columns(2)
            with col_filtro1:
                disciplinas_filtro_nomes = ["Todas"] + sorted(all_disciplinas_df['DISCIPLINA'].unique())
                disciplina_filtro = st.selectbox("Filtrar por Disciplina", options=disciplinas_filtro_nomes, key="gs_disciplina_filtro")
            with col_filtro2:
                status_filtro = st.selectbox("Filtrar por Status", options=["Todos", "Ativos", "Inativos"], key="gs_status_filtro")
            
            df_filtrado = all_servicos_df.copy()
            if disciplina_filtro != "Todas":
                df_filtrado = df_filtrado[df_filtrado['DISCIPLINA'] == disciplina_filtro]
            if status_filtro == "Ativos":
                df_filtrado = df_filtrado[df_filtrado['ativo'] == True]
            if status_filtro == "Inativos":
                df_filtrado = df_filtrado[df_filtrado['ativo'] == False]
            st.dataframe(
                df_filtrado[['DISCIPLINA', 'DESCRIÇÃO DO SERVIÇO', 'UNIDADE', 'VALOR', 'ativo']],
                use_container_width=True,
                column_config={
                    "VALOR": st.column_config.NumberColumn("Valor Unitário", format="R$ %.2f"),
                    "ativo": st.column_config.CheckboxColumn("Ativo?", disabled=True)
                }
            )

            servico_selecionado_desc = st.selectbox(
                "Selecione um serviço para gerenciar",
                options=sorted(df_filtrado['DESCRIÇÃO DO SERVIÇO'].unique()),
                index=None,
                placeholder="Selecione um serviço da lista acima..."
            )

            if servico_selecionado_desc:
                try:
                    servico_atual = df_filtrado[df_filtrado['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado_desc].iloc[0]
                    servico_id = int(servico_atual['id'])
                    servico_ativo = bool(servico_atual['ativo'])
                    with st.expander("Editar Serviço", expanded=False):
                        with st.form("gs_edit_servico_form"):
                            st.info(f"Editando: {servico_atual['DESCRIÇÃO DO SERVIÇO']}")
                            
                            mapa_disciplinas_edicao = active_disciplinas_df.set_index('nome')['id'].to_dict()
                            disciplinas_nomes_edicao = sorted(mapa_disciplinas_edicao.keys())
                            
                            try:
                                index_disciplina = disciplinas_nomes_edicao.index(servico_atual['DISCIPLINA'])
                            except ValueError:
                                st.warning("A disciplina deste serviço está inativa. Reative-a se quiser usá-la em novos serviços.")
                                disc_inativa_id = int(all_disciplinas_df[all_disciplinas_df['nome'] == servico_atual['DISCIPLINA']].iloc[0]['id'])
                                mapa_disciplinas_edicao[servico_atual['DISCIPLINA']] = disc_inativa_id
                                disciplinas_nomes_edicao = sorted(mapa_disciplinas_edicao.keys())
                                index_disciplina = disciplinas_nomes_edicao.index(servico_atual['DISCIPLINA'])

                            novo_disciplina_nome = st.selectbox(
                                "Disciplina", 
                                options=disciplinas_nomes_edicao, 
                                index=index_disciplina
                            )
                            novo_descricao = st.text_input("Descrição", value=servico_atual['DESCRIÇÃO DO SERVIÇO'])
                            novo_unidade = st.text_input("Unidade", value=servico_atual['UNIDADE'])
                            novo_valor = st.number_input("Valor Unitário (R$)", min_value=0.0, value=float(servico_atual['VALOR']), step=0.01, format="%.2f")
                            
                            submitted_edit = st.form_submit_button("Salvar Alterações", type="primary")
                            if submitted_edit:
                                if not all([novo_disciplina_nome, novo_descricao, novo_unidade, novo_valor > 0]):
                                    st.warning("Todos os campos são obrigatórios.")
                                else:
                                    novo_disciplina_id = int(mapa_disciplinas_edicao[novo_disciplina_nome])
                                    with st.spinner("Salvando alterações..."):
                                        if db_utils.editar_servico(servico_id, novo_disciplina_id, novo_descricao, novo_unidade.upper(), novo_valor):
                                            st.success("Serviço atualizado com sucesso!")
                                            st.cache_data.clear()
                                            st.rerun()

                    with st.expander("Gerenciar/Inativar Serviço Selecionado", expanded=False):
                        if servico_ativo:
                            st.warning(f"Este serviço está **Ativo**. Novos lançamentos podem usá-lo.")
                            if st.button("Inativar Serviço", type="primary"):
                                with st.spinner("Inativando..."):
                                    if db_utils.inativar_servico(servico_id):
                                        st.success("Serviço inativado com sucesso! Ele não aparecerá mais para novos lançamentos.")
                                        st.cache_data.clear()
                                        st.rerun()
                        else:
                            st.success(f"Este serviço está **Inativo**. Ele não é mostrado para novos lançamentos.")
                            if st.button("Reativar Serviço"):
                                with st.spinner("Reativando..."):
                                    if db_utils.reativar_servico(servico_id):
                                        st.success("Serviço reativado com sucesso!")
                                        st.cache_data.clear()
                                        st.rerun()

                except Exception as e:
                    st.error(f"Erro ao carregar o serviço: {e}")
