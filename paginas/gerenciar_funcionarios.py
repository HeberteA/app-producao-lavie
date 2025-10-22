import streamlit as st
import db_utils
import utils
import pandas as pd

def render_page():
    st.header("Gerenciar Funcionários")

    @st.cache_data
    def get_all_data():
        funcionarios_df = db_utils.get_funcionarios()
        obras_df = db_utils.get_obras()
        funcoes_df = db_utils.get_funcoes() 
        return funcionarios_df, obras_df, funcoes_df

    funcionarios_df, obras_df, funcoes_df = get_all_data()

    if funcoes_df.empty:
        st.error("Nenhuma função cadastrada. Adicione funções na página 'Gerenciar Funções' antes de adicionar funcionários.")
        st.stop()
    if obras_df.empty:
        st.error("Nenhuma obra cadastrada. Adicione obras na página 'Gerenciar Obras' antes de adicionar funcionários.")
        st.stop()

    lista_funcoes = funcoes_df.set_index('FUNÇÃO')['id'].to_dict()
    lista_obras = obras_df.set_index('NOME DA OBRA')['id'].to_dict()
    
    tab_adicionar, tab_inativar, tab_editar = st.tabs(["Adicionar Novo", "Gerenciar/Inativar Existente", "Editar Funcionário"])

    with tab_adicionar:
        st.subheader("Adicionar Novo Funcionário")
        
        funcao_selecionada_nome = st.selectbox(
            "1. Selecione a Função",
            options=sorted(lista_funcoes.keys()),
            index=None,
            placeholder="Selecione...",
            key="gf_funcao_select_add"
        )
        
        if funcao_selecionada_nome:
            info_funcao = funcoes_df[funcoes_df['FUNÇÃO'] == funcao_selecionada_nome].iloc[0]
            col_tipo, col_salario = st.columns(2)
            col_tipo.text_input("Tipo de Contrato", value=info_funcao['TIPO'], disabled=True, key="gf_tipo_input_add")
            col_salario.text_input("Salário Base", value=utils.format_currency(info_funcao['SALARIO_BASE']), disabled=True, key="gf_salario_input_add")
        
        with st.form("gf_add_funcionario_form", clear_on_submit=True):
            nome = st.text_input("2. Nome do Funcionário", key="gf_nome_input")
            obra_selecionada_nome = st.selectbox("3. Alocar na Obra", options=sorted(lista_obras.keys()), key="gf_obra_select_add")
            
            submitted = st.form_submit_button("Adicionar Funcionário")
            if submitted:
                if not nome.strip() or not funcao_selecionada_nome or not obra_selecionada_nome:
                    st.warning("Por favor, preencha nome, função e obra.")
                else:
                    if not funcionarios_df[funcionarios_df['NOME'].str.lower() == nome.lower()].empty:
                        st.error(f"Erro: Já existe um funcionário ativo com o nome '{nome}'.")
                    else:
                        obra_id = lista_obras[obra_selecionada_nome]
                        funcao_id = lista_funcoes[funcao_selecionada_nome]
                        
                        with st.spinner("Adicionando funcionário..."):
                            if db_utils.adicionar_funcionario(nome, funcao_id, obra_id):
                                st.success(f"Funcionário '{nome}' adicionado com sucesso!")
                                st.cache_data.clear() 
                                st.rerun()

    with tab_inativar:
        st.subheader("Inativar Funcionário Existente")
    
        col_filtro1, col_filtro2 = st.columns(2)
        
        with col_filtro1:
            obra_filtro_remover = st.selectbox(
                "Filtre por Obra", options=["Todas"] + sorted(obras_df['NOME DA OBRA'].unique()), 
                index=0, key="gf_filtro_obra_remover"
            )
        
        with col_filtro2:
            funcao_filtro_remover = st.selectbox(
                "Filtre por Função", options=["Todas"] + sorted(funcoes_df['FUNÇÃO'].unique()),
                index=0, key="gf_filtro_funcao_remover"
            )
        
        df_filtrado_inativar = funcionarios_df
        if obra_filtro_remover != "Todas":
            df_filtrado_inativar = df_filtrado_inativar[df_filtrado_inativar['OBRA'] == obra_filtro_remover]
        
        if funcao_filtro_remover != "Todas":
            df_filtrado_inativar = df_filtrado_inativar[df_filtrado_inativar['FUNÇÃO'] == funcao_filtro_remover]

        st.dataframe(
            df_filtrado_inativar[['NOME', 'FUNÇÃO', 'TIPO', 'SALARIO_BASE', 'OBRA']],
            use_container_width=True,
            column_config={
                "SALARIO_BASE": st.column_config.NumberColumn(
                    "SALARIO BASE",
                    format="R$ %.2f"  
                )
            }
        )

        func_para_remover_nome = st.selectbox(
            "Selecione o funcionário para inativar", 
            options=sorted(df_filtrado_inativar['NOME'].unique()), index=None, 
            placeholder="Selecione um funcionário...", key="gf_func_remover_select"
        )
        if func_para_remover_nome:
            if st.button(f"Inativar {func_para_remover_nome}", type="primary", key="gf_inativar_btn"):
                with st.spinner(f"Inativando {func_para_remover_nome}..."):
                    funcionario_info = funcionarios_df.loc[funcionarios_df['NOME'] == func_para_remover_nome, 'id']
                    if not funcionario_info.empty:
                        funcionario_id = int(funcionario_info.iloc[0])
                        if db_utils.inativar_funcionario(funcionario_id):
                            st.success(f"Funcionário '{func_para_remover_nome}' inativado com sucesso!")
                            st.cache_data.clear() 
                            st.rerun()
                    else:
                        st.error(f"Erro: Funcionário '{func_para_remover_nome}' não encontrado.")

    with tab_editar:
        st.subheader("Editar Funcionário")
        obra_filtro_editar = st.selectbox(
            "1. Filtre por Obra (Opcional)", options=["Todas"] + sorted(obras_df['NOME DA OBRA'].unique()), 
            index=0, key="gf_filtro_obra_editar"
        )

        df_filtrado_editar = funcionarios_df
        if obra_filtro_editar != "Todas":
            df_filtrado_editar = funcionarios_df[funcionarios_df['OBRA'] == obra_filtro_editar]

        func_para_editar_nome = st.selectbox(
            "2. Selecione o Funcionário para Editar",
            options=sorted(df_filtrado_editar['NOME'].unique()), index=None,
            placeholder="Selecione um funcionário...",
            key="gf_func_editar_select"
        )

        if func_para_editar_nome:
            try:
                func_atual = funcionarios_df[funcionarios_df['NOME'] == func_para_editar_nome].iloc[0]
                func_id = int(func_atual['id'])

                with st.form("gf_edit_funcionario_form"):
                    st.markdown(f"**Editando:** {func_para_editar_nome}")
                    
                    novo_nome = st.text_input("Nome", value=func_atual['NOME'])
                    
                    list_funcoes_nomes = sorted(lista_funcoes.keys())
                    idx_funcao = list_funcoes_nomes.index(func_atual['FUNÇÃO']) if func_atual['FUNÇÃO'] in list_funcoes_nomes else 0
                    nova_funcao_nome = st.selectbox("Função", options=list_funcoes_nomes, index=idx_funcao)
                    
                    list_obras_nomes = sorted(lista_obras.keys())
                    idx_obra = list_obras_nomes.index(func_atual['OBRA']) if func_atual['OBRA'] in list_obras_nomes else 0
                    nova_obra_nome = st.selectbox("Obra", options=list_obras_nomes, index=idx_obra)
                    
                    submitted_edit = st.form_submit_button("Salvar Alterações")
                    
                    if submitted_edit:
                        if not novo_nome.strip() or not nova_funcao_nome or not nova_obra_nome:
                            st.warning("Todos os campos são obrigatórios.")
                        else:
                            nova_funcao_id = lista_funcoes[nova_funcao_nome]
                            nova_obra_id = lista_obras[nova_obra_nome]
                            nome_conflitante = funcionarios_df[
                                (funcionarios_df['NOME'].str.lower() == novo_nome.lower()) &
                                (funcionarios_df['id'] != func_id)
                            ]
                            if not nome_conflitante.empty:
                                st.error(f"Erro: O nome '{novo_nome}' já está em uso por outro funcionário.")
                            else:
                                with st.spinner("Salvando alterações..."):
                                    if db_utils.editar_funcionario(func_id, novo_nome, nova_funcao_id, nova_obra_id):
                                        st.success(f"Funcionário '{novo_nome}' atualizado com sucesso!")
                                        st.cache_data.clear()
                                        st.rerun()
            except Exception as e:
                st.error(f"Erro ao carregar dados do funcionário. A função ou obra dele pode ter sido inativada. Detalhe: {e}")




