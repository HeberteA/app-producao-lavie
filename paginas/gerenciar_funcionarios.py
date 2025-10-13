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
            
            with st.form("add_funcionario_form"):
                nome = st.text_input("2. Nome do Funcionário", key="gf_nome_input")
                obra = st.selectbox("3. Alocar na Obra", options=obras_df['NOME DA OBRA'].unique(), key="gf_obra_select")
                submitted = st.form_submit_button("Adicionar Funcionário")
                if submitted:
                    if nome and funcao_selecionada and obra:
                        st.success(f"Funcionário '{nome}' adicionado com sucesso (simulação).")
                        st.cache_data.clear()
                    else:
                        st.warning("Por favor, preencha nome, função e obra.")

    with tab_gerenciar:
        st.subheader("Inativar Funcionário Existente")
        obra_filtro_remover = st.selectbox(
            "Filtre por Obra para ver os funcionários",
            options=["Todas"] + sorted(obras_df['NOME DA OBRA'].unique()), index=0,
            key="gf_filtro_obra_remover"
        )
        df_filtrado = funcionarios_df
        if obra_filtro_remover != "Todas":
            df_filtrado = funcionarios_df[funcionarios_df['OBRA'] == obra_filtro_remover]

        st.dataframe(df_filtrado[['NOME', 'FUNÇÃO', 'OBRA']], use_container_width=True)

        func_para_remover = st.selectbox(
            "Selecione o funcionário para inativar", 
            options=sorted(df_filtrado['NOME'].unique()), index=None, 
            placeholder="Selecione um funcionário da lista acima...",
            key="gf_func_remover_select"
        )
        if func_para_remover:
            if st.button(f"Inativar {func_para_remover}", type="primary", key="gf_inativar_btn"):
                st.success(f"Funcionário '{func_para_remover}' inativado com sucesso (simulação).")
                st.cache_data.clear()

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
                    st.success(f"Funcionário '{func_para_mudar}' movido para '{obra_destino}' com sucesso (simulação).")
                    st.cache_data.clear()
                else:
                    st.warning("Por favor, preencha todos os três campos.")

