import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import base64
import io

@st.cache_resource(ttl=60) 
def get_db_connection():
    try:
        engine = create_engine(st.secrets["database"]["url"])
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return None

@st.cache_data
def get_funcionarios():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = """
    SELECT f.id, f.obra_id, f.funcao_id, f.nome as "NOME", o.nome_obra as "OBRA", 
           fn.funcao as "FUNÇÃO", fn.tipo as "TIPO", fn.salario_base as "SALARIO_BASE"
    FROM funcionarios f
    JOIN obras o ON f.obra_id = o.id
    JOIN funcoes fn ON f.funcao_id = fn.id
    WHERE f.ativo = TRUE;
    """
    return pd.read_sql(query, engine)

@st.cache_data
def get_lancamentos_do_mes(mes_referencia):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = text("""
    SELECT 
        l.id, 
        l.data_lancamento, 
        l.data_servico, 
        l.obra_id, 
        o.nome_obra AS "Obra",
        l.funcionario_id, 
        f.nome AS "Funcionário", 
        COALESCE(s.disciplina, 'Diverso') AS "Disciplina",
        COALESCE(s.descricao, l.servico_diverso_descricao) AS "Serviço",
        CAST(l.quantidade AS INTEGER) AS "Quantidade",
        COALESCE(s.unidade, 'UN') AS "Unidade", 
        l.valor_unitario AS "Valor Unitário",
        (l.quantidade * l.valor_unitario) AS "Valor Parcial", 
        l.observacao AS "Observação"
    FROM lancamentos l
    LEFT JOIN obras o ON l.obra_id = o.id
    LEFT JOIN funcionarios f ON l.funcionario_id = f.id
    LEFT JOIN servicos s ON l.servico_id = s.id
    WHERE l.arquivado = FALSE AND to_char(l.data_servico, 'YYYY-MM') = :mes;
    """)
    df = pd.read_sql(query, engine, params={'mes': mes_referencia})
    if not df.empty:
        df = df.rename(columns={'data_lancamento': 'Data', 'data_servico': 'Data do Serviço'})
        df['Data'] = pd.to_datetime(df['Data'])
        df['Data do Serviço'] = pd.to_datetime(df['Data do Serviço'])
    return df

@st.cache_data
def get_obras():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, nome_obra AS "NOME DA OBRA", status, aviso FROM obras WHERE status = \'Ativa\'', engine)

@st.cache_data
def get_acessos():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT obra_id, codigo_acesso FROM acessos_obras', engine)

@st.cache_data
def get_precos():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, disciplina as "DISCIPLINA", descricao as "DESCRIÇÃO DO SERVIÇO", unidade as "UNIDADE", valor_unitario as "VALOR" FROM servicos', engine)
    
@st.cache_data
def get_funcoes():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE" FROM funcoes WHERE ativo = TRUE', engine)

@st.cache_data
def get_all_funcoes():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE", ativo FROM funcoes', engine)

@st.cache_data
def get_status_do_mes(mes_referencia):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = text("""
    SELECT sa.obra_id, o.nome_obra AS "Obra", sa.funcionario_id, f.nome AS "Funcionario",
           sa.mes_referencia AS "Mes", sa.status AS "Status", sa.comentario AS "Comentario",
           sa.lancamentos_concluidos AS "Lancamentos Concluidos" 
    FROM status_auditoria sa
    LEFT JOIN obras o ON sa.obra_id = o.id
    LEFT JOIN funcionarios f ON sa.funcionario_id = f.id
    WHERE to_char(sa.mes_referencia, 'YYYY-MM') = :mes;
    """)
    df = pd.read_sql(query, engine, params={'mes': mes_referencia})
    if not df.empty and 'Mes' in df.columns:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df

# Otimização de Cache: Removido TTL.
@st.cache_data
def get_folhas_mensais(mes_referencia=None):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()

    base_query = """
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status, f.data_lancamento, f.contador_envios
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id
    """
    params = {}
    if mes_referencia:
        base_query += " WHERE to_char(f.mes_referencia, 'YYYY-MM') = :mes"
        params['mes'] = mes_referencia

    query = text(base_query)
    df = pd.read_sql(query, engine, params=params)

    if not df.empty and 'Mes' in df.columns:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df


def registrar_log(usuario, acao, detalhes="", tabela_afetada=None, id_registro_afetado=None):
    engine = get_db_connection()
    if engine is None: return
    try:
        if id_registro_afetado is not None:
            id_registro_afetado = int(id_registro_afetado)
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO log_auditoria (usuario, acao, detalhes, tabela_afetada, id_registro_afetado)
                    VALUES (:usuario, :acao, :detalhes, :tabela_afetada, :id_registro_afetado)
                """)
                connection.execute(query, {
                    'usuario': usuario, 'acao': acao, 'detalhes': detalhes,
                    'tabela_afetada': tabela_afetada, 'id_registro_afetado': id_registro_afetado
                })
                transaction.commit()
    except Exception as e:
        st.toast(f"Falha ao registrar log: {e}", icon="⚠️")

def upsert_status_auditoria(obra_id, funcionario_id, mes_referencia, status=None, comentario=None, lancamentos_concluidos=None):
    engine = get_db_connection()
    if engine is None: return False
    if status is None and comentario is None and lancamentos_concluidos is None:
        st.warning("Nenhuma atualização solicitada para upsert_status_auditoria.")
        return False

    mes_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()

    set_clauses = []
    update_params = {}
    if status is not None:
        set_clauses.append("status = EXCLUDED.status")
        update_params['status'] = status
    if comentario is not None:
        set_clauses.append("comentario = EXCLUDED.comentario")
        update_params['comentario'] = comentario
    if lancamentos_concluidos is not None:
        set_clauses.append("lancamentos_concluidos = EXCLUDED.lancamentos_concluidos")
        update_params['lancamentos_concluidos'] = lancamentos_concluidos

    set_clause_str = ", ".join(set_clauses)
    if not set_clause_str: 
         return False

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_insert = text(f"""
                    INSERT INTO status_auditoria (obra_id, funcionario_id, mes_referencia, status, comentario, lancamentos_concluidos)
                    VALUES (:obra_id, :func_id, :mes_ref, :status, :comentario, :lanc_concluidos)
                    ON CONFLICT (obra_id, funcionario_id, mes_referencia)
                    DO UPDATE SET {set_clause_str};
                """)

                current_record_query = text("""
                    SELECT status, comentario, lancamentos_concluidos 
                    FROM status_auditoria 
                    WHERE obra_id = :obra_id AND funcionario_id = :func_id AND mes_referencia = :mes_ref
                """)
                current_record = connection.execute(current_record_query, {'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt}).fetchone()

                current_status = current_record[0] if current_record else 'A Revisar'
                current_comentario = current_record[1] if current_record else ''
                current_lanc_concluidos = current_record[2] if current_record else False

                insert_params = {
                    'obra_id': obra_id, 
                    'func_id': funcionario_id, 
                    'mes_ref': mes_dt, 
                    'status': status if status is not None else current_status, 
                    'comentario': comentario if comentario is not None else current_comentario,
                    'lanc_concluidos': lancamentos_concluidos if lancamentos_concluidos is not None else current_lanc_concluidos
                }

                insert_params.update(update_params)

                connection.execute(query_insert, insert_params)
                transaction.commit()

        details = []
        if status is not None: details.append(f"Status para '{status}'")
        if comentario is not None: details.append("Comentário atualizado")
        if lancamentos_concluidos is not None: details.append(f"Lançamentos Concluídos para '{lancamentos_concluidos}'")
        log_detail_str = ". ".join(details)
        registrar_log(st.session_state.get('user_identifier', 'unknown'), 
                      "UPSERT_STATUS_AUDITORIA", 
                      f"Registro para func_id {funcionario_id} na obra_id {obra_id} ({mes_referencia}) atualizado: {log_detail_str}")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o status/comentário/conclusão: {e}")
        return False

def launch_monthly_sheet(obra_id, mes_referencia_dt, obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    mes_inicio = mes_referencia_dt.strftime('%Y-%m-01')
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_arquivar = text("UPDATE lancamentos SET arquivado = TRUE WHERE obra_id = :obra_id AND date_trunc('month', data_servico) = :mes_inicio;")
                connection.execute(query_arquivar, {'obra_id': obra_id, 'mes_inicio': mes_inicio})

                query_update_status = text("UPDATE folhas_mensais SET status = 'Finalizada' WHERE obra_id = :obra_id AND mes_referencia = :mes_inicio;")
                connection.execute(query_update_status, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "FINALIZAR_FOLHA", f"Folha para {obra_nome} ({mes_referencia_dt.strftime('%Y-%m')}) finalizada.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao finalizar a folha: {e}")
        return False

def devolver_folha_para_revisao(obra_id, mes_referencia):
    engine = get_db_connection()
    if engine is None: return False
    
    mes_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE folhas_mensais SET status = 'Devolvida para Revisão' WHERE obra_id = :obra_id AND mes_referencia = :mes_ref")
                connection.execute(query, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "DEVOLVER_FOLHA", f"Folha da obra_id {obra_id} devolvida para revisão.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao devolver a folha: {e}")
        return False

def enviar_folha_para_auditoria(obra_id, mes_referencia, obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    mes_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()
    
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_insert = text("""
                    INSERT INTO folhas_mensais (obra_id, mes_referencia, status, data_lancamento, contador_envios)
                    VALUES (:obra_id, :mes_ref, 'Enviada para Auditoria', NOW(), 1)
                    ON CONFLICT (obra_id, mes_referencia) 
                    DO UPDATE SET status = 'Enviada para Auditoria', data_lancamento = NOW(), contador_envios = folhas_mensais.contador_envios + 1;
                """)
                connection.execute(query_insert, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "ENVIAR_FOLHA_AUDITORIA", f"Folha de {obra_nome} enviada.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao enviar a folha: {e}")
        return False

def salvar_novos_lancamentos(df_para_salvar):
    engine = get_db_connection()
    if engine is None: return False

    df_para_salvar = df_para_salvar.where(pd.notna(df_para_salvar), None)
    
    obra_id = int(df_para_salvar.iloc[0]['obra_id'])
    mes_ref_dt = pd.to_datetime(df_para_salvar.iloc[0]['data_servico']).date().replace(day=1)
    
    try:
        with engine.connect() as connection:
            
            status_query = text("SELECT status FROM folhas_mensais WHERE obra_id = :obra_id AND mes_referencia = :mes_ref")
            result = connection.execute(status_query, {'obra_id': obra_id, 'mes_ref': mes_ref_dt}).fetchone()
            status_atual = result[0] if result else 'Não Enviada'
            
            if status_atual in ['Enviada para Auditoria', 'Finalizada']:
                st.error(f"Não foi possível salvar: A folha para este mês (Status: {status_atual}) já foi enviada ou finalizada. Por favor, atualize a página.")
                return False
            
            with connection.begin() as transaction:
                lancamentos_dict = df_para_salvar.to_dict(orient='records')
                query = text("""
                    INSERT INTO lancamentos (data_servico, obra_id, funcionario_id, servico_id,
                                           servico_diverso_descricao, quantidade, valor_unitario, observacao, data_lancamento)
                    VALUES (:data_servico, :obra_id, :funcionario_id, :servico_id,
                            :servico_diverso_descricao, :quantidade, :valor_unitario, :observacao, :data_lancamento)
                """)
                connection.execute(query, lancamentos_dict)
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "SALVAR_LANCAMENTOS", f"{len(lancamentos_dict)} lançamentos salvos.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar na base de dados: {e}")
        return False
        
def remover_lancamentos_por_id(ids_para_remover, razao="", obra_id=None, mes_referencia=None):
    engine = get_db_connection()
    if engine is None: return False
    if not ids_para_remover: return False
    
    try:
        with engine.connect() as connection:
            
            if obra_id is not None and mes_referencia is not None:
                mes_ref_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()
                status_query = text("SELECT status FROM folhas_mensais WHERE obra_id = :obra_id AND mes_referencia = :mes_ref")
                result = connection.execute(status_query, {'obra_id': obra_id, 'mes_ref': mes_ref_dt}).fetchone()
                status_atual = result[0] if result else 'Não Enviada'
                
                if status_atual in ['Enviada para Auditoria', 'Finalizada']:
                    st.error(f"Não foi possível remover: A folha (Status: {status_atual}) já foi enviada ou finalizada.")
                    return False

            with connection.begin() as transaction:
                query = text("DELETE FROM lancamentos WHERE id = ANY(:ids)")
                connection.execute(query, {'ids': ids_para_remover})
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "REMOVER_LANCAMENTOS", f"IDs: {ids_para_remover}. Razão: {razao}")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao remover lançamentos: {e}")
        return False
        
def save_aviso_data(obra_id, novo_aviso):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE obras SET aviso = :aviso WHERE id = :id")
                connection.execute(query, {'aviso': novo_aviso, 'id': obra_id})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "SALVAR_AVISO", f"Aviso para obra_id {obra_id} atualizado.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o aviso: {e}")
        return False
        
def atualizar_observacoes(updates_list):
    engine = get_db_connection()
    if engine is None: return False
    if not updates_list: return True
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE lancamentos SET observacao = :obs WHERE id = :id")
                connection.execute(query, updates_list)
                transaction.commit()
        ids_str = ", ".join([str(item['id']) for item in updates_list])
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "ATUALIZAR_OBSERVACOES", f"Observações atualizadas para IDs: {ids_str}")
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar as observações: {e}")
        return False

def adicionar_obra(nome_obra, codigo_acesso):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_obra = text("INSERT INTO obras (nome_obra, status) VALUES (:nome, 'Ativa') RETURNING id")
                result = connection.execute(query_obra, {'nome': nome_obra})
                new_obra_id = result.scalar_one()

                query_acesso = text("INSERT INTO acessos_obras (obra_id, codigo_acesso) VALUES (:obra_id, :codigo)")
                connection.execute(query_acesso, {'obra_id': new_obra_id, 'codigo': codigo_acesso})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "ADICIONAR_OBRA", f"Obra '{nome_obra}' adicionada.")
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar obra no banco de dados: {e}")
        return False

def remover_obra(obra_id):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE obras SET status = 'Inativa' WHERE id = :id")
                connection.execute(query, {'id': obra_id})
                connection.execute(text("DELETE FROM acessos_obras WHERE obra_id = :id"), {'id': obra_id})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "REMOVER_OBRA", f"Obra ID {obra_id} INATIVADA.")
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao inativar obra: {e}.")
        return False

def mudar_codigo_acesso_obra(obra_id, novo_codigo):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE acessos_obras SET codigo_acesso = :novo_codigo WHERE obra_id = :obra_id")
                connection.execute(query, {'novo_codigo': novo_codigo, 'obra_id': obra_id})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "MUDAR_CODIGO_ACESSO", f"Código de acesso da obra ID {obra_id} alterado.")
        
        st.cache_data.clear() # Limpa o cache
        return True
    except Exception as e:
        st.error(f"Erro ao alterar o código de acesso: {e}")
        return False

def adicionar_funcao(nome, tipo, salario_base):
    """
    Insere uma nova função ativa no banco de dados.
    """
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO funcoes (funcao, tipo, salario_base, ativo)
                    VALUES (:nome, :tipo, :salario_base, TRUE)
                """)
                connection.execute(query, {
                    'nome': nome, 
                    'tipo': tipo, 
                    'salario_base': salario_base
                })
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'admin'), 
                      "ADICIONAR_FUNCAO", 
                      f"Função '{nome}' adicionada.")
        st.cache_data.clear() 
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            st.error(f"Erro: Já existe uma função com o nome '{nome}'.")
        else:
            st.error(f"Erro ao adicionar função no banco de dados: {e}")
        return False

def inativar_funcao(funcao_id):
    """
    Marca uma função como inativa no banco de dados (ativo = FALSE).
    """
    engine = get_db_connection()
    if engine is None: return False
    
    try:
        with engine.connect() as connection:
            check_query = text("SELECT COUNT(*) FROM funcionarios WHERE funcao_id = :id AND ativo = TRUE")
            count = connection.execute(check_query, {'id': funcao_id}).scalar_one()
            
            if count > 0:
                st.error(f"Não é possível inativar: {count} funcionário(s) ativo(s) está(ão) usando esta função.")
                return False
                
            with connection.begin() as transaction:
                query = text("UPDATE funcoes SET ativo = FALSE WHERE id = :id")
                connection.execute(query, {'id': funcao_id})
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'admin'), 
                      "INATIVAR_FUNCAO", 
                      f"Função ID {funcao_id} foi inativada.")
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao inativar função no banco de dados: {e}")
        return False

def adicionar_funcionario(nome, funcao_id, obra_id):
    engine = get_db_connection()
    if engine is None: return False
    
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO funcionarios (nome, funcao_id, obra_id, ativo)
                    VALUES (:nome, :funcao_id, :obra_id, TRUE)
                """)
                connection.execute(query, {
                    'nome': nome, 
                    'funcao_id': funcao_id, 
                    'obra_id': obra_id
                })
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'admin'), 
                      "ADICIONAR_FUNCIONARIO", 
                      f"Funcionário '{nome}' adicionado.")
        st.cache_data.clear()
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            st.error(f"Erro: Já existe um funcionário ativo com o nome '{nome}'. Por favor, escolha um nome diferente.")
        else:
            st.error(f"Erro ao adicionar funcionário no banco de dados: {e}")
        return False

def inativar_funcionario(funcionario_id):
    engine = get_db_connection()
    if engine is None: return False
    
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE funcionarios SET ativo = FALSE WHERE id = :id
                """)
                connection.execute(query, {'id': funcionario_id})
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'admin'), 
                      "INATIVAR_FUNCIONARIO", 
                      f"Funcionário ID {funcionario_id} foi inativado.")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao inativar funcionário no banco de dados: {e}")
        return False

def editar_funcionario(funcionario_id, novo_nome, nova_funcao_id, nova_obra_id):
    """
    Atualiza nome, funcao_id e obra_id de um funcionário.
    """
    engine = get_db_connection()
    if engine is None: return False
    
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE funcionarios 
                    SET nome = :novo_nome, 
                        funcao_id = :nova_funcao_id, 
                        obra_id = :nova_obra_id 
                    WHERE id = :funcionario_id
                """)
                connection.execute(query, {
                    'novo_nome': novo_nome,
                    'nova_funcao_id': nova_funcao_id,
                    'nova_obra_id': nova_obra_id,
                    'funcionario_id': funcionario_id
                })
                transaction.commit()
        
        registrar_log(st.session_state.get('user_identifier', 'admin'), 
                      "EDITAR_FUNCIONARIO",
                      f"Dados do funcionário ID {funcionario_id} atualizados (Nome: {novo_nome}, Obra ID: {nova_obra_id}, Função ID: {nova_funcao_id}).")
        st.cache_data.clear() 
        return True
    except Exception as e:
        if 'unique constraint' in str(e).lower():
             st.error(f"Erro: O nome '{novo_nome}' já está em uso por outro funcionário.")
        else:
            st.error(f"Erro ao editar funcionário no banco de dados: {e}")
        return False


def limpar_concluidos_obra_mes(obra_id, mes_referencia):
    """Define lancamentos_concluidos como FALSE para todos funcionários de uma obra/mês."""
    engine = get_db_connection()
    if engine is None: return False
    mes_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE status_auditoria 
                    SET lancamentos_concluidos = FALSE 
                    WHERE obra_id = :obra_id AND mes_referencia = :mes_ref AND funcionario_id != 0
                """)
                connection.execute(query, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'unknown'), 
                      "LIMPAR_CONCLUIDOS", 
                      f"Status de conclusão limpo para obra_id {obra_id} no mês {mes_referencia}.")
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao limpar status de concluídos: {e}")
        return False

