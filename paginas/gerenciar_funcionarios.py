import streamlit as st
import db_utils
import utils

def render_page():
    if st.session_state['role'] != 'admin':
        st.error("Você não tem permissão para acessar esta página.")
        st.stop()

    engine = db_utils.get_db_connection()
    if engine is None:
        st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
        st.stop()

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
                options=lista_funcoes,
                index=0,
                help="A escolha da função preencherá o tipo e o salário automaticamente."
            )
            tipo = ""
            salario = 0.0
            if funcao_selecionada:
                info_funcao = funcoes_df[funcoes_df['FUNÇÃO'] == funcao_selecionada].iloc[0]
                tipo = info_funcao['TIPO']
                salario = info_funcao['SALARIO_BASE']
                col_tipo, col_salario = st.columns(2)
                col_tipo.text_input("Tipo de Contrato", value=tipo, disabled=True)
                col_salario.text_input("Salário Base", value=utils.format_currency(salario), disabled=True)
            with st.form("add_funcionario_form", clear_on_submit=True):
                nome = st.text_input("2. Nome do Funcionário")
                obra = st.selectbox("3. Alocar na Obra", options=obras_df['NOME DA OBRA'].unique())
                submitted = st.form_submit_button("Adicionar Funcionário")
                if submitted:
                    if nome and funcao_selecionada and obra:
                        obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra, 'id'].iloc[0])
                        funcao_id = int(funcoes_df.loc[funcoes_df['FUNÇÃO'] == funcao_selecionada, 'id'].iloc[0])
                        if db_utils.adicionar_funcionario(nome, funcao_id, obra_id):
                            st.success(f"Funcionário '{nome}' adicionado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.warning("Por favor, preencha nome, função e obra.")

    with tab_gerenciar:
        st.subheader("Inativar Funcionário Existente")
        if funcionarios_df.empty:
            st.info("Nenhum funcionário cadastrado.")
        else:
            obra_filtro_remover = st.selectbox(
                "Filtre por Obra para ver os funcionários",
                options=["Todas"] + sorted(obras_df['NOME DA OBRA'].unique()),
                index=0,
                key="filtro_obra_remover"
            )

            df_filtrado = funcionarios_df
            if obra_filtro_remover and obra_filtro_remover != "Todas":
                df_filtrado = funcionarios_df[funcionarios_df['OBRA'] == obra_filtro_remover]

            df_para_remover = df_filtrado[df_filtrado['id'] != 0]

            st.dataframe(df_para_remover[['NOME', 'FUNÇÃO', 'OBRA']], use_container_width=True)

            func_para_remover = st.selectbox(
                "Selecione o funcionário para inativar", 
                options=sorted(df_para_remover['NOME'].unique()), 
                index=None, 
                placeholder="Selecione um funcionário da lista acima..."
            )
            if func_para_remover:
                if st.button(f"Inativar {func_para_remover}", type="primary"):
                    funcionario_id = int(funcionarios_df.loc[funcionarios_df['NOME'] == func_para_remover, 'id'].iloc[0])
                    if db_utils.remover_funcionario(funcionario_id, func_para_remover):
                        st.success(f"Funcionário '{func_para_remover}' inativado com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                        
    with tab_mudar_obra:
        st.subheader("Mudar Funcionário de Obra")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                obra_origem = st.selectbox(
                    "1. Obra de Origem",
                    options=sorted(obras_df['NOME DA OBRA'].unique()),
                    index=None,
                    placeholder="Selecione..."
                )
            with col2:
                opcoes_funcionarios = []
                if obra_origem:
                    opcoes_funcionarios = sorted(
                        funcionarios_df[(funcionarios_df['OBRA'] == obra_origem) & (funcionarios_df['id'] != 0)]['NOME'].unique()
                    )
        
                func_para_mudar = st.selectbox(
                    "2. Funcionário a Mudar",
                    options=opcoes_funcionarios,
                    index=None,
                    placeholder="Escolha uma obra...",
                    disabled=not obra_origem
                )
            with col3:
                opcoes_destino = []
                if obra_origem:
                    opcoes_destino = sorted(
                        obras_df[obras_df['NOME DA OBRA'] != obra_origem]['NOME DA OBRA'].unique()
                    )

                obra_destino = st.selectbox(
                    "3. Nova Obra de Destino",
                    options=opcoes_destino,
                    index=None,
                    placeholder="Escolha uma obra...",
                    disabled=not obra_origem
                )

            if st.button("Mudar Funcionário de Obra", use_container_width=True):
                if obra_origem and func_para_mudar and obra_destino:
                    funcionario_id = int(funcionarios_df.loc[funcionarios_df['NOME'] == func_para_mudar, 'id'].iloc[0])
                    nova_obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_destino, 'id'].iloc[0])

                    if db_utils.mudar_funcionario_de_obra(funcionario_id, nova_obra_id, func_para_mudar, obra_destino):
                        st.toast(f"Funcionário '{func_para_mudar}' movido para a obra '{obra_destino}'!", icon="✅")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.warning("Por favor, preencha todos os três campos: obra de origem, funcionário e obra de destino.")

