import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date

@st.cache_resource(ttl=60)
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados. Cacheada como um recurso."""
    try:
        engine = create_engine(st.secrets["database"]["url"])
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return None
        
@st.cache_data(ttl=300)
def get_funcionarios():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = """
    SELECT f.id, f.obra_id, f.nome as "NOME", o.nome_obra as "OBRA", 
           fn.funcao as "FUNÇÃO", fn.tipo as "TIPO", fn.salario_base as "SALARIO_BASE"
    FROM funcionarios f
    JOIN obras o ON f.obra_id = o.id
    JOIN funcoes fn ON f.funcao_id = fn.id
    WHERE f.ativo = TRUE;
    """
    return pd.read_sql(query, engine)

@st.cache_data
def get_precos():
    """Busca a tabela de preços de serviços."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    
    query = 'SELECT id, disciplina as "DISCIPLINA", descricao as "DESCRIÇÃO DO SERVIÇO", unidade as "UNIDADE", valor_unitario as "VALOR" FROM servicos'
    return pd.read_sql(query, engine)

@st.cache_data
def get_obras():
    """Busca todas as obras."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    
    query = 'SELECT id, nome_obra AS "NOME DA OBRA", status, aviso FROM obras'
    return pd.read_sql(query, engine)

@st.cache_data(ttl=60)
def get_lancamentos_do_mes(mes_referencia):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = text("""
    SELECT l.id, l.data_lancamento, l.data_servico, l.obra_id, o.nome_obra AS "Obra", 
           f.nome AS "Funcionário", s.disciplina AS "Disciplina",
           COALESCE(s.descricao, l.servico_diverso_descricao) AS "Serviço",
           CAST(l.quantidade AS INTEGER) AS "Quantidade",
           COALESCE(s.unidade, 'UN') AS "Unidade", l.valor_unitario AS "Valor Unitário",
           (l.quantidade * l.valor_unitario) AS "Valor Parcial", l.observacao AS "Observação"
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
def get_status_do_mes(mes_referencia_str):
    """Busca os status de auditoria para um mês de referência."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    
    mes_dt = pd.to_datetime(mes_referencia_str).date().replace(day=1)
    
    query = text("""
    SELECT
        sa.obra_id, o.nome_obra AS "Obra", sa.funcionario_id, f.nome AS "Funcionario",
        sa.mes_referencia AS "Mes", sa.status AS "Status", sa.comentario AS "Comentario"
    FROM status_auditoria sa
    LEFT JOIN obras o ON sa.obra_id = o.id
    LEFT JOIN funcionarios f ON sa.funcionario_id = f.id
    WHERE sa.mes_referencia = :mes_ref;
    """)
    status_df = pd.read_sql(query, engine, params={'mes_ref': mes_dt})
    if not status_df.empty:
        status_df['Mes'] = pd.to_datetime(status_df['Mes']).dt.date
    return status_df

@st.cache_data
def get_funcoes():
    """Busca todas as funções e seus detalhes."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    
    query = 'SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE" FROM funcoes'
    return pd.read_sql(query, engine)

@st.cache_data
def get_folhas(mes_referencia_str):
    """Busca as folhas mensais para o mês de referência."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()

    mes_dt = pd.to_datetime(mes_referencia_str).date().replace(day=1)
    
    query = text("""
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status, f.data_lancamento, f.contador_envios
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id
    WHERE f.mes_referencia = :mes_ref;
    """)
    return pd.read_sql(query, engine, params={'mes_ref': mes_dt})

@st.cache_data
def get_folhas_todas():
    """Busca TODAS as folhas mensais para análises históricas."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()

    query = """
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status, f.data_lancamento, f.contador_envios
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id;
    """
    return pd.read_sql(query, engine)

@st.cache_data
def get_acessos():
    """Busca os códigos de acesso de todas as obras."""
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    
    query = 'SELECT obra_id, codigo_acesso FROM acessos_obras'
    return pd.read_sql(query, engine)



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

def enviar_folha_para_auditoria(obra_id, mes_referencia, obra_nome):
    """Envia folha para auditoria, incrementando o contador se já existir."""
    engine = get_db_connection()
    if engine is None: return False
    
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO folhas_mensais (obra_id, mes_referencia, status, data_lancamento, contador_envios)
                    VALUES (:obra_id, :mes_ref, 'Enviada para Auditoria', NOW(), 1)
                    ON CONFLICT (obra_id, mes_referencia) DO UPDATE 
                    SET status = 'Enviada para Auditoria',
                        data_lancamento = NOW(),
                        contador_envios = folhas_mensais.contador_envios + 1;
                """)
                connection.execute(query, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        detalhes = f"Folha da obra '{obra_nome}' para {mes_referencia} enviada/reenviada para auditoria."
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "ENVIO_PARA_AUDITORIA", detalhes)
        st.toast("Folha enviada para auditoria!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao enviar a folha: {e}")
        return False

def devolver_folha_para_revisao(obra_id, mes_referencia, obra_nome):
    """Auditor devolve a folha para a obra corrigir."""
    engine = get_db_connection()
    if engine is None: return False
    
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE folhas_mensais
                    SET status = 'Devolvida para Revisão'
                    WHERE obra_id = :obra_id AND mes_referencia = :mes_ref;
                """)
                connection.execute(query, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        detalhes = f"Folha da obra '{obra_nome}' para {mes_referencia} DEVOLVIDA para revisão."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "DEVOLUCAO_FOLHA", detalhes)
        st.toast("Folha devolvida para a obra!", icon="↩️")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao devolver a folha: {e}")
        return False

def adicionar_funcionario(nome, funcao_id, obra_id):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("INSERT INTO funcionarios (nome, funcao_id, obra_id) VALUES (:nome, :funcao_id, :obra_id)")
                connection.execute(query, {'nome': nome, 'funcao_id': funcao_id, 'obra_id': obra_id})
                transaction.commit()
        registrar_log(st.session_state.get('user_identifier', 'admin'), "ADICAO_FUNCIONARIO", f"Funcionário '{nome}' adicionado.")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar funcionário: {e}")
        return False

def remover_funcionario(funcionario_id, nome_funcionario):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE funcionarios SET ativo = FALSE WHERE id = :id")
                connection.execute(query, {'id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{nome_funcionario}' (ID: {funcionario_id}) inativado."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "REMOCAO_FUNCIONARIO", detalhes, 'funcionarios', funcionario_id)
        return True
    except Exception as e:
        st.error(f"Erro ao inativar funcionário: {e}")
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
        registrar_log(st.session_state.get('user_identifier', 'admin'), "ADICAO_OBRA", f"Obra '{nome_obra}' adicionada.")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar obra: {e}")
        return False

def remover_obra(obra_id, nome_obra):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                connection.execute(text("DELETE FROM acessos_obras WHERE obra_id = :id"), {'id': obra_id})
                connection.execute(text("DELETE FROM obras WHERE id = :id"), {'id': obra_id})
                transaction.commit()
        detalhes = f"Obra '{nome_obra}' (ID: {obra_id}) removida."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "REMOCAO_OBRA", detalhes, 'obras', obra_id)
        return True
    except Exception as e:
        st.error(f"Erro ao remover obra: {e}")
        return False

def salvar_novos_lancamentos(df_para_salvar):
    engine = get_db_connection()
    if engine is None: return False
    
    lancamentos_dict = df_para_salvar.to_dict(orient='records')
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO lancamentos (data_servico, obra_id, funcionario_id, servico_id, servico_diverso_descricao, quantidade, valor_unitario, observacao, data_lancamento)
                    VALUES (:data_servico, :obra_id, :funcionario_id, :servico_id, :servico_diverso_descricao, :quantidade, :valor_unitario, :observacao, :data_lancamento)
                """)
                connection.execute(query, lancamentos_dict)
                transaction.commit()
        detalhes = f"{len(lancamentos_dict)} novo(s) lançamento(s) salvo(s)."
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "SALVAR_LANCAMENTO", detalhes)
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar na base de dados: {e}")
        return False

def remover_lancamentos_por_id(ids_para_remover, razao=""):
    engine = get_db_connection()
    if not ids_para_remover or engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("DELETE FROM lancamentos WHERE id = ANY(:ids)")
                connection.execute(query, {'ids': ids_para_remover})
                transaction.commit()
        st.toast("Lançamentos removidos com sucesso!", icon="🗑️")
        detalhes = f"IDs removidos: {ids_para_remover}. Justificativa: {razao}"
        registrar_log(st.session_state.get('user_identifier', 'unknown'), "REMOCAO_LANCAMENTO", detalhes, 'lancamentos')
        return True
    except Exception as e:
        st.error(f"Erro ao remover lançamentos: {e}")
        return False

def launch_monthly_sheet(obra_id, mes_dt, obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    
    mes_inicio = mes_dt.strftime('%Y-%m-01')
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_arquivar = text("UPDATE lancamentos SET arquivado = TRUE WHERE obra_id = :obra_id AND date_trunc('month', data_servico) = :mes_inicio;")
                connection.execute(query_arquivar, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                query_update_status = text("UPDATE folhas_mensais SET status = 'Finalizada' WHERE obra_id = :obra_id AND mes_referencia = :mes_inicio;")
                connection.execute(query_update_status, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                transaction.commit()
        detalhes = f"Folha da obra '{obra_nome}' para {mes_dt.strftime('%Y-%m')} foi finalizada e arquivada."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "FINALIZACAO_FOLHA", detalhes, 'folhas_mensais')
        st.toast(f"Folha de {mes_dt.strftime('%Y-%m')} finalizada e arquivada!", icon="🚀") 
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao finalizar a folha: {e}")
        return False

def upsert_status_auditoria(obra_id, funcionario_id, mes_referencia, status=None, comentario=None):
    """Insere ou atualiza um registro em status_auditoria. Mais eficiente que update/insert."""
    engine = get_db_connection()
    if engine is None: return False

    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)

    update_clauses = []
    params = {'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt}
    
    if status is not None:
        update_clauses.append("status = :status")
        params['status'] = status
    if comentario is not None:
        update_clauses.append("comentario = :comentario")
        params['comentario'] = comentario
    
    if not update_clauses: 
        return True

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text(f"""
                    INSERT INTO status_auditoria (obra_id, funcionario_id, mes_referencia, status, comentario)
                    VALUES (:obra_id, :func_id, :mes_ref, :status, :comentario)
                    ON CONFLICT (obra_id, funcionario_id, mes_referencia)
                    DO UPDATE SET {', '.join(update_clauses)};
                """)
                params.setdefault('status', 'A Revisar')
                params.setdefault('comentario', '')

                connection.execute(query, params)
                transaction.commit()
        
        detalhes = f"Status/Comentário atualizado para func_id {funcionario_id} na obra_id {obra_id} para {mes_referencia}."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "UPSERT_STATUS", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar status/comentário: {e}")
        return False

def mudar_funcionario_de_obra(funcionario_id, nova_obra_id, func_nome, nova_obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE funcionarios SET obra_id = :nova_obra_id WHERE id = :funcionario_id")
                connection.execute(query, {'nova_obra_id': nova_obra_id, 'funcionario_id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{func_nome}' (ID: {funcionario_id}) movido para a obra '{nova_obra_nome}'."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "MUDANCA_OBRA_FUNCIONARIO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao mudar funcionário de obra: {e}")
        return False

def mudar_codigo_acesso_obra(obra_id, novo_codigo, obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE acessos_obras SET codigo_acesso = :novo_codigo WHERE obra_id = :obra_id")
                connection.execute(query, {'novo_codigo': novo_codigo, 'obra_id': obra_id})
                transaction.commit()
        detalhes = f"Código de acesso da obra '{obra_nome}' (ID: {obra_id}) foi alterado."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "MUDANCA_CODIGO_ACESSO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao alterar o código de acesso: {e}")
        return False

def save_aviso_data(obra_nome, novo_aviso):
    engine = get_db_connection()
    if engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE obras SET aviso = :aviso WHERE nome_obra = :nome")
                connection.execute(query, {'aviso': novo_aviso, 'nome': obra_nome})
                transaction.commit()
        detalhes = f"Aviso para a obra '{obra_nome}' foi atualizado."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "SALVAR_AVISO_OBRA", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o aviso: {e}")
        return False

def atualizar_observacoes(updates_list):
    engine = get_db_connection()
    if not updates_list or engine is None: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE lancamentos SET observacao = :obs WHERE id = :id")
                connection.execute(query, updates_list)
                transaction.commit()
        ids_atualizados = [item['id'] for item in updates_list]
        detalhes = f"Observações dos lançamentos IDs {ids_atualizados} foram atualizadas."
        registrar_log(st.session_state.get('user_identifier', 'admin'), "ATUALIZACAO_OBSERVACAO_MASSA", detalhes)
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar as observações: {e}")
        return False


