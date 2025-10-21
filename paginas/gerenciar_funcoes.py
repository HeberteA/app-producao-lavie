import streamlit as st
import db_utils
import pandas as pd
import utils

def render_page():
    st.header("Gerenciar Funções 🔧")
    @st.cache_data
    def get_all_funcoes_cached():
        return db_utils.get_all_funcoes()

    @st.cache_data
    def get_funcionarios_cached():
        return db_utils.get_funcionarios()

    all_funcoes_df = get_all_funcoes_cached()
    funcionarios_df = get_funcionarios_cached()

    tab_adicionar, tab_inativar = st.tabs(["➕ Adicionar Nova Função", "🚫 Inativar Função Existente"])

    with tab_adicionar:
        st.subheader("Adicionar Nova Função")
        st.info("Uma vez criada, uma função não pode ter seu salário ou tipo alterado. Para corrigir, inative-a e crie uma nova.")

        with st.form("gf_add_funcao_form", clear_on_submit=True):
            nome_funcao = st.text_input("Nome da Função (ex: 'Pedreiro - R$2200')")
            salario_base = st.number_input("Salário Base (R$)", min_value=0.0, step=100.0, format="%.2f")
            
            tipo_display = st.selectbox("Tipo de Contrato", options=["Produção", "Bônus"])
            tipo_valor = "PRODUCAO" if tipo_display == "Produção" else "BONUS"
            
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
        
        st.dataframe(
            active_funcoes_df[['FUNÇÃO', 'TIPO', 'SALARIO_BASE']],
            use_container_width=True,
            column_config={
                "SALARIO_BASE": st.column_config.NumberColumn(
                    "Salário Base", # 
                    format="R$ %.2f"  
                )
            }
        )

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
                st.dataframe(funcionarios_usando[['NOME', 'OBRA']])
                st.info("Mova este(s) funcionário(s) para outra função na aba 'Gerenciar Funcionários' antes de inativar esta função.")
            else:
                st.warning(f"Você está prestes a inativar a função '{funcao_para_inativar_nome}'. Esta ação não pode ser desfeita.")
                if st.button(f"Confirmar Inativação de {funcao_para_inativar_nome}", type="primary"):
                    with st.spinner("Inativando..."):
                        if db_utils.inativar_funcao(funcao_id):
                            st.success(f"Função '{funcao_para_inativar_nome}' inativada.")
                            st.cache_data.clear() 
                            st.rerun()
