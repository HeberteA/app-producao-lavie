import streamlit as st
import db_utils
import utils

def render_page():
    funcionarios_df = db_utils.get_funcionarios()
    obras_df = db_utils.get_obras()
    funcoes_df = db_utils.get_funcoes()

    st.header("Gerenciar Funcionários 👥")
    
    tab_adicionar, tab_gerenciar, tab_mudar_obra = st.tabs(["➕ Adicionar Novo", "📋 Gerenciar Existentes", "🔄 Mudar de Obra"])

    with tab_adicionar:
        st.subheader("Adicionar Novo Funcionário")
        with st.container(border=True):
            lista_funcoes = [""] + funcoes_df['FUNÇÃO'].dropna().unique().tolist()
            funcao_selecionada = st.selectbox(
                "1. Selecione a Função",
                options=lista_funcoes, index=0,
                help="A escolha da função preencherá o tipo e o salário automaticamente.",
                key="gf_funcao_select"
            )
            if funcao_selecionada:
                info_funcao = funcoes_df[funcoes_df['FUNÇÃO'] == funcao_selecionada].iloc[0]
                col_tipo, col_salario = st.columns(2)
                col_tipo.text_input("Tipo de Contrato", value=info_funcao['TIPO'], disabled=True, key="gf_tipo_input")
                col_salario.text_input("Salário Base", value=utils.format_currency(info_funcao['SALARIO_BASE']), disabled=True, key="gf_salario_input")
            
            with st.form("gf_add_funcionario_form", clear_on_submit=True):
                nome = st.text_input("2. Nome do Funcionário", key="gf_nome_input")
                obra = st.selectbox("3. Alocar na Obra", options=obras_df['NOME DA OBRA'].unique(), key="gf_obra_select")
                submitted = st.form_submit_button("Adicionar Funcionário")
                if submitted:
                    if nome.strip() and funcao_selecionada and obra:
                        obra_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra, 'id']
                        funcao_info = funcoes_df.loc[funcoes_df['FUNÇÃO'] == funcao_selecionada, 'id']

                        if obra_info.empty:
                            st.error(f"A obra '{obra}' não foi encontrada. Por favor, atualize a página.")
                        elif funcao_info.empty:
                            st.error(f"A função '{funcao_selecionada}' não foi encontrada. Por favor, atualize a página.")
                        else:
                            obra_id = int(obra_info.iloc[0])
                            funcao_id = int(funcao_info.iloc[0])
                            
                            with st.spinner("Adicionando funcionário..."):
                                if db_utils.adicionar_funcionario(nome, funcao_id, obra_id):
                                    st.success(f"Funcionário '{nome}' adicionado com sucesso ao banco de dados!")
                                    st.cache_data.clear()
                                    st.rerun()
                    else:
                        st.warning("Por favor, preencha nome, função e obra.")

    with tab_gerenciar:
        st.subheader("Inativar Funcionário Existente")
        obra_filtro_remover = st.selectbox(
            "Filtre por Obra", options=["Todas"] + sorted(obras_df['NOME DA OBRA'].unique()), 
            index=0, key="gf_filtro_obra_remover"
        )
        df_filtrado = funcionarios_df
        if obra_filtro_remover != "Todas":
            df_filtrado = funcionarios_df[funcionarios_df['OBRA'] == obra_filtro_remover]

        st.dataframe(df_filtrado[['NOME', 'FUNÇÃO', 'OBRA']], use_container_width=True)

        func_para_remover = st.selectbox(
            "Selecione o funcionário para inativar", 
            options=sorted(df_filtrado['NOME'].unique()), index=None, 
            placeholder="Selecione um funcionário...", key="gf_func_remover_select"
        )
        if func_para_remover:
            if st.button(f"Inativar {func_para_remover}", type="primary", key="gf_inativar_btn"):
                with st.spinner(f"Inativando {func_para_remover}..."):
                    funcionario_info = funcionarios_df.loc[funcionarios_df['NOME'] == func_para_remover, 'id']
                    if not funcionario_info.empty:
                        funcionario_id = int(funcionario_info.iloc[0])
                        if db_utils.inativar_funcionario(funcionario_id):
                            st.success(f"Funcionário '{func_para_remover}' inativado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.error(f"Erro: Funcionário '{func_para_remover}' não encontrado.")

    with tab_mudar_obra:
        st.subheader("Mudar Funcionário de Obra")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                obra_origem = st.selectbox(
                    "1. Obra de Origem", options=sorted(obras_df['NOME DA OBRA'].unique()),
                    index=None, placeholder="Selecione...", key="gf_obra_origem_select"
                )
            with col2:
                opcoes_funcionarios = []
                if obra_origem:
                    opcoes_funcionarios = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_origem]['NOME'].unique())
                func_para_mudar = st.selectbox(
                    "2. Funcionário a Mudar",
                    options=opcoes_funcionarios, index=None, placeholder="Escolha uma obra...",
                    disabled=not obra_origem, key="gf_func_mudar_select"
                )
            with col3:
                opcoes_destino = []
                if obra_origem:
                    opcoes_destino = sorted(obras_df[obras_df['NOME DA OBRA'] != obra_origem]['NOME DA OBRA'].unique())
                obra_destino = st.selectbox(
                    "3. Nova Obra de Destino",
                    options=opcoes_destino, index=None, placeholder="Escolha uma obra...",
                    disabled=not obra_origem, key="gf_obra_destino_select"
                )

            if st.button("Mudar Funcionário de Obra", use_container_width=True, key="gf_mudar_obra_btn"):
                if obra_origem and func_para_mudar and obra_destino:
                    with st.spinner(f"Movendo {func_para_mudar} para a obra {obra_destino}..."):
                        funcionario_info = funcionarios_df.loc[funcionarios_df['NOME'] == func_para_mudar, 'id']
                        obra_destino_info = obras_df.loc[obras_df['NOME DA OBRA'] == obra_destino, 'id']

                        if funcionario_info.empty:
                            st.error(f"Erro: Funcionário '{func_para_mudar}' não encontrado.")
                        elif obra_destino_info.empty:
                            st.error(f"Erro: Obra de destino '{obra_destino}' não encontrada.")
                        else:
                            funcionario_id = int(funcionario_info.iloc[0])
                            nova_obra_id = int(obra_destino_info.iloc[0])
                            
                            if db_utils.mudar_funcionario_de_obra(funcionario_id, nova_obra_id):
                                st.success(f"Funcionário '{func_para_mudar}' movido para '{obra_destino}' com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                else:
                    st.warning("Por favor, preencha todos os três campos.")
