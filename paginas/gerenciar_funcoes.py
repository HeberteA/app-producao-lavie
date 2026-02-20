import streamlit as st
import db_utils
import pandas as pd
import utils

def render_page():
    st.header("Gerenciar Funções")
    
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
            background-color: #ffffff;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
        }
        @media (prefers-color-scheme: dark) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                background-color: #1e1e1e;
                box-shadow: 0 4px 6px rgba(255, 255, 255, 0.05);
            }
        }
        </style>
    """, unsafe_allow_html=True)

    @st.cache_data
    def get_all_funcoes_cached():
        return db_utils.get_all_funcoes()

    @st.cache_data
    def get_funcionarios_cached():
        return db_utils.get_funcionarios()

    all_funcoes_df = get_all_funcoes_cached()
    funcionarios_df = get_funcionarios_cached()

    tab_visualizar, tab_adicionar, tab_inativar = st.tabs([
        "Visualizar e Editar", 
        "Adicionar Nova Função", 
        "Inativar Função"
    ])

    with tab_visualizar:
        st.subheader("Funções Ativas")
        
        active_funcoes_df = all_funcoes_df[all_funcoes_df['ativo'] == True]
        
        if active_funcoes_df.empty:
            st.info("Nenhuma função ativa encontrada.")
        else:
            cols = st.columns(3)
            
            for index, row in active_funcoes_df.iterrows():
                with cols[index % 3]:
                    with st.container(border=True):
                        st.markdown(f"### {row['FUNÇÃO']}")
                        st.write(f"**Tipo:** {row['TIPO']}")
                        st.write(f"**Salário Base:** R$ {row['SALARIO_BASE']:.2f}")
                        
                        with st.expander("Editar Função"):
                            with st.form(key=f"edit_form_{row['id']}", clear_on_submit=False):
                                edit_nome = st.text_input("Nome", value=row['FUNÇÃO'])
                                
                                idx_tipo = 0 if row['TIPO'] == "PRODUCAO" else 1
                                edit_tipo_display = st.selectbox(
                                    "Tipo de Contrato", 
                                    options=["PRODUCAO", "BONUS"], 
                                    index=idx_tipo,
                                    key=f"tipo_{row['id']}"
                                )
                                
                                edit_salario = st.number_input(
                                    "Salário (R$)", 
                                    min_value=0.0, 
                                    value=float(row['SALARIO_BASE']), 
                                    step=100.0, 
                                    format="%.2f",
                                    key=f"salario_{row['id']}"
                                )
                                
                                submit_edit = st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True)
                                
                                if submit_edit:
                                    if not edit_nome.strip():
                                        st.error("O nome não pode ficar vazio.")
                                    else:
                                        with st.spinner("Salvando..."):
                                            sucesso = db_utils.atualizar_funcao(
                                                funcao_id=row['id'], 
                                                novo_nome=edit_nome, 
                                                novo_tipo=edit_tipo_display, 
                                                novo_salario=edit_salario
                                            )
                                            if sucesso:
                                                st.success("Atualizado!")
                                                st.cache_data.clear()
                                                st.rerun()

    with tab_adicionar:
        st.subheader("Adicionar Nova Função")

        with st.form("gf_add_funcao_form", clear_on_submit=True):
            nome_funcao = st.text_input("Nome da Função")
            salario_base = st.number_input("Salário Base (R$)", min_value=0.0, step=100.0, format="%.2f")
            
            tipo_display = st.selectbox("Tipo de Contrato", options=["PRODUCAO", "BONUS"])
            tipo_valor = "PRODUCAO" if tipo_display == "PRODUCAO" else "BONUS"
            
            submitted = st.form_submit_button("Adicionar Função")
            if submitted:
                if not nome_funcao.strip():
                    st.warning("O nome da função é obrigatório.")
                elif salario_base <= 0:
                    st.warning("O salário base deve ser maior que zero.")
                else:
                    if not all_funcoes_df[all_funcoes_df['FUNÇÃO'].str.lower() == nome_funcao.lower()].empty:
                        st.error(f"Já existe uma função com o nome '{nome_funcao}'.")
                    else:
                        with st.spinner("Adicionando função..."):
                            if db_utils.adicionar_funcao(nome_funcao, tipo_valor, salario_base):
                                st.success(f"Função '{nome_funcao}' adicionada com sucesso!")
                                st.cache_data.clear() 
                                st.rerun()

    with tab_inativar:
        st.subheader("Inativar Função Existente")
        
        active_funcoes_df = all_funcoes_df[all_funcoes_df['ativo'] == True]
        
        funcao_para_inativar_nome = st.selectbox(
            "Selecione a função para inativar",
            options=sorted(active_funcoes_df['FUNÇÃO'].unique()),
            index=None,
            placeholder="Selecione uma função..."
        )
        
        if funcao_para_inativar_nome:
            funcao_info = active_funcoes_df[active_funcoes_df['FUNÇÃO'] == funcao_para_inativar_nome].iloc[0]
            funcao_id = int(funcao_info['id'])

            funcionarios_usando = funcionarios_df[funcionarios_df['funcao_id'] == funcao_id]
            
            if not funcionarios_usando.empty:
                st.error(f"A função '{funcao_para_inativar_nome}' não pode ser inativada.")
                st.warning(f"Ela está sendo utilizada por {len(funcionarios_usando)} funcionário(s):")
                st.dataframe(funcionarios_usando[['NOME', 'OBRA']], use_container_width=True)
                st.info("Mova este(s) funcionário(s) para outra função na aba 'Gerenciar Funcionários' antes de inativar esta função.")
            else:
                st.warning(f"Você está prestes a inativar a função '{funcao_para_inativar_nome}'. Esta ação não pode ser desfeita.")
                if st.button(f"Confirmar Inativação de {funcao_para_inativar_nome}", type="primary"):
                    with st.spinner("Inativando..."):
                        if db_utils.inativar_funcao(funcao_id):
                            st.success(f"Função '{funcao_para_inativar_nome}' inativada.")
                            st.cache_data.clear() 
                            st.rerun()
