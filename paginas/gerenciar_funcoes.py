import streamlit as st
import db_utils
import pandas as pd
import utils

def render_page():
    st.header("Gerenciar Funções")

    @st.cache_data
    def get_all_funcoes_cached():
        return db_utils.get_all_funcoes()

    @st.cache_data
    def get_funcionarios_cached():
        return db_utils.get_funcionarios()

    all_funcoes_df = get_all_funcoes_cached()
    funcionarios_df = get_funcionarios_cached()

    with st.expander("Adicionar Nova Função"):
        with st.form("gf_add_funcao_form", clear_on_submit=True):
            nome_funcao = st.text_input("Nome da Função")
            salario_base = st.number_input("Salário Base (R$)", min_value=0.0, step=100.0, format="%.2f")
            
            tipo_display = st.selectbox("Tipo de Contrato", options=["PRODUCAO", "BONUS"])
            tipo_valor = "PRODUCAO" if tipo_display == "PRODUCAO" else "BONUS"
            
            submitted = st.form_submit_button("Adicionar Função", use_container_width=True, type="primary")
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

    st.subheader("Funções Ativas")
    
    active_funcoes_df = all_funcoes_df[all_funcoes_df['ativo'] == True]
    
    if active_funcoes_df.empty:
        st.info("Nenhuma função ativa encontrada.")
    else:
        for index, row in active_funcoes_df.iterrows():
            funcao_id = int(row['id'])
            
            card_html = f"""
            <div style="
                border-left: 6px solid #E37026; 
                background-color: transparent; 
                border-top: 1px solid rgba(150, 150, 150, 0.2);
                border-right: 1px solid rgba(150, 150, 150, 0.2);
                border-bottom: 1px solid rgba(150, 150, 150, 0.2);
                padding: 16px; 
                border-radius: 4px; 
                margin-bottom: 8px; 
                margin-top: 16px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            ">
                <h4 style="margin-top: 0; margin-bottom: 8px;">{row['FUNÇÃO']}</h4>
                <p style="margin: 0; font-size: 17px;">
                    <strong>Tipo:</strong> {row['TIPO']} &nbsp;&nbsp;|&nbsp;&nbsp; 
                    <strong>Salário Base:</strong> R$ {row['SALARIO_BASE']:.2f}
                </p>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            col_btn1, col_btn2 = st.columns([3, 1])
            
            with col_btn1:
                with st.popover("Editar Função", use_container_width=True, type="primary"):
                    with st.form(key=f"edit_form_{funcao_id}", clear_on_submit=False):
                        edit_nome = st.text_input("Nome", value=row['FUNÇÃO'])
                        
                        idx_tipo = 0 if row['TIPO'] == "PRODUCAO" else 1
                        edit_tipo_display = st.selectbox(
                            "Tipo de Contrato", 
                            options=["PRODUCAO", "BONUS"], 
                            index=idx_tipo,
                            key=f"tipo_{funcao_id}"
                        )
                        
                        edit_salario = st.number_input(
                            "Salário (R$)", 
                            min_value=0.0, 
                            value=float(row['SALARIO_BASE']), 
                            step=100.0, 
                            format="%.2f",
                            key=f"salario_{funcao_id}"
                        )
                        
                        submit_edit = st.form_submit_button("Salvar Alterações"c)
                        
                        if submit_edit:
                            if not edit_nome.strip():
                                st.error("O nome não pode ficar vazio.")
                            else:
                                with st.spinner("Salvando..."):
                                    sucesso = db_utils.atualizar_funcao(
                                        funcao_id=funcao_id, 
                                        novo_nome=edit_nome, 
                                        novo_tipo=edit_tipo_display, 
                                        novo_salario=edit_salario
                                    )
                                    if sucesso:
                                        st.success("Atualizado!")
                                        st.cache_data.clear()
                                        st.rerun()

            with col_btn2:
                with st.popover("Inativar Função", use_container_width=True):
                    funcionarios_usando = funcionarios_df[funcionarios_df['funcao_id'] == funcao_id]
                    
                    if not funcionarios_usando.empty:
                        st.error("A função não pode ser inativada.")
                        st.warning(f"Utilizada por {len(funcionarios_usando)} funcionário(s):")
                        st.dataframe(funcionarios_usando[['NOME', 'OBRA']], use_container_width=True)
                    else:
                        st.warning(f"Você está prestes a inativar '{row['FUNÇÃO']}'.")
                        if st.button("Confirmar Inativação", key=f"btn_conf_inativar_{funcao_id}", type="primary", use_container_width=True):
                            with st.spinner("Inativando..."):
                                if db_utils.inativar_funcao(funcao_id):
                                    st.success("Inativada com sucesso.")
                                    st.cache_data.clear() 
                                    st.rerun()
            
            st.write("")
