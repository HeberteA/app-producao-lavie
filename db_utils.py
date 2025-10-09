import streamlit as st
import pandas as pd
from sqlalchemy import Engine, create_engine, text

@st.cache_resource(ttl=60)
def get_db_connection():
    try:
        engine = create_engine(st.secrets["database"]["url"])
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return None

def registrar_log(engine, usuario, acao, detalhes="", tabela_afetada=None, id_registro_afetado=None):
    try:
        if id_registro_afetado is not None:
            id_registro_afetado = int(id_registro_afetado)
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO log_auditoria (usuario, acao, detalhes, tabela_afetada, id_registro_afetado)
                    VALUES (:usuario, :acao, :detalhes, :tabela_afetada, :id_registro_afetado)
                """)
                connection.execute(query, {'usuario': usuario, 'acao': acao, 'detalhes': detalhes, 'tabela_afetada': tabela_afetada, 'id_registro_afetado': id_registro_afetado})
                transaction.commit()
    except Exception as e:
        st.toast(f"Falha ao registrar log: {e}", icon="⚠️")

def enviar_folha_para_auditoria(engine, obra_id, mes_referencia, obra_nome):
    """Insere ou atualiza um registro em folhas_mensais para marcar a submissão."""
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_upsert = text("""
                    INSERT INTO folhas_mensais (obra_id, mes_referencia, status, data_lancamento, contador_envios)
                    VALUES (:obra_id, :mes_ref, 'Enviada para Auditoria', NOW(), 1)
                    ON CONFLICT (obra_id, mes_referencia) 
                    DO UPDATE SET 
                        status = 'Enviada para Auditoria',
                        data_lancamento = NOW(),
                        contador_envios = folhas_mensais.contador_envios + 1;
                """)
                connection.execute(query_upsert, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        detalhes = f"A folha da obra '{obra_nome}' para o mês {mes_referencia} foi (re)enviada para auditoria."
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "ENVIO_PARA_AUDITORIA", detalhes, tabela_afetada='folhas_mensais')
        st.toast("Folha enviada para auditoria com sucesso!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao enviar a folha: {e}")
        return False

def devolver_folha_para_revisao(engine, obra_id, mes_referencia, obra_nome):
    """Muda o status de uma folha para 'Devolvida para Revisão'."""
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_update = text("""
                    UPDATE folhas_mensais
                    SET status = 'Devolvida para Revisão'
                    WHERE obra_id = :obra_id AND mes_referencia = :mes_ref
                    AND status != 'Finalizada';
                """)
                connection.execute(query_update, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        detalhes = f"Folha da obra '{obra_nome}' para {mes_referencia} devolvida para revisão."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "DEVOLUCAO_FOLHA", detalhes, tabela_afetada='folhas_mensais')
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao devolver a folha: {e}")
        return False

@st.cache_data
def get_funcionarios(engine):
    query = """
    SELECT f.id, f.obra_id, f.nome as "NOME", o.nome_obra as "OBRA", fn.funcao as "FUNÇÃO", fn.tipo as "TIPO", fn.salario_base as "SALARIO_BASE"
    FROM funcionarios f
    JOIN obras o ON f.obra_id = o.id
    JOIN funcoes fn ON f.funcao_id = fn.id
    WHERE f.ativo = TRUE;
    """
    return pd.read_sql(query, engine)

@st.cache_data
def get_lancamentos_do_mes(engine, mes_selecionado):
    query = text("""
    SELECT l.id, l.data_lancamento as "Data", l.data_servico as "Data do Serviço", l.obra_id,
           o.nome_obra AS "Obra", f.nome AS "Funcionário", s.disciplina AS "Disciplina",
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
    WHERE l.arquivado = FALSE AND date_trunc('month', l.data_servico) = date_trunc('month', CAST(:mes AS date));
    """)
    df = pd.read_sql(query, engine, params={'mes': f'{mes_selecionado}-01'})
    if not df.empty:
        df['Data'] = df['Data'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['Data do Serviço'] = pd.to_datetime(df['Data do Serviço'])
    return df

@st.cache_data
def get_status_do_mes(engine, mes_selecionado):
    query = text("""
    SELECT sa.obra_id, o.nome_obra AS "Obra", sa.funcionario_id, f.nome AS "Funcionario",
           sa.mes_referencia AS "Mes", sa.status AS "Status", sa.comentario AS "Comentario"
    FROM status_auditoria sa
    LEFT JOIN obras o ON sa.obra_id = o.id
    LEFT JOIN funcionarios f ON sa.funcionario_id = f.id
    WHERE date_trunc('month', sa.mes_referencia) = date_trunc('month', CAST(:mes AS date));
    """)
    df = pd.read_sql(query, engine, params={'mes': f'{mes_selecionado}-01'})
    if not df.empty and 'Mes' in df.columns:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df

@st.cache_data
def get_folhas(engine):
    query = """
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status, f.data_lancamento, f.contador_envios
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id;
    """
    df = pd.read_sql(query, engine)
    if not df.empty:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df

@st.cache_data
def get_precos(engine):
    return pd.read_sql('SELECT id, disciplina as "DISCIPLINA", descricao as "DESCRIÇÃO DO SERVIÇO", unidade as "UNIDADE", valor_unitario as "VALOR" FROM servicos', engine)

@st.cache_data
def get_obras(engine):
    return pd.read_sql('SELECT id, nome_obra AS "NOME DA OBRA", status, aviso AS "Aviso" FROM obras', engine)

@st.cache_data
def get_funcoes(engine):
    return pd.read_sql('SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE" FROM funcoes', engine)

@st.cache_data
def get_acessos(engine):
    return pd.read_sql('SELECT obra_id, codigo_acesso FROM acessos_obras', engine)

@st.cache_data
def get_lancamentos(engine):
    query = """
    SELECT l.id, l.data_lancamento as "Data", l.data_servico as "Data do Serviço", l.obra_id,
           o.nome_obra AS "Obra", f.nome AS "Funcionário", s.disciplina AS "Disciplina",
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
    WHERE l.arquivado = FALSE;
    """
    df = pd.read_sql(query, engine)
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'])
        df['Data do Serviço'] = pd.to_datetime(df['Data do Serviço'])
    return df

def adicionar_funcionario(engine, nome, funcao_id, obra_id):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("INSERT INTO funcionarios (nome, funcao_id, obra_id) VALUES (:nome, :funcao_id, :obra_id)")
                connection.execute(query, {'nome': nome, 'funcao_id': funcao_id, 'obra_id': obra_id})
                transaction.commit()
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "ADICAO_FUNCIONARIO", f"Funcionário '{nome}' adicionado.")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar funcionário: {e}")
        return False

def remover_funcionario(engine, funcionario_id, nome_funcionario):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE funcionarios SET ativo = FALSE WHERE id = :id")
                connection.execute(query, {'id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{nome_funcionario}' (ID: {funcionario_id}) inativado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "REMOCAO_FUNCIONARIO", detalhes, 'funcionarios', funcionario_id)
        return True
    except Exception as e:
        st.error(f"Erro ao inativar funcionário: {e}")
        return False

def adicionar_obra(engine, nome_obra, codigo_acesso):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_obra = text("INSERT INTO obras (nome_obra, status) VALUES (:nome, 'Ativa') RETURNING id")
                result = connection.execute(query_obra, {'nome': nome_obra})
                new_obra_id = result.scalar_one()
                query_acesso = text("INSERT INTO acessos_obras (obra_id, codigo_acesso) VALUES (:obra_id, :codigo)")
                connection.execute(query_acesso, {'obra_id': new_obra_id, 'codigo': codigo_acesso})
                transaction.commit()
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "ADICAO_OBRA", f"Obra '{nome_obra}' adicionada.")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar obra: {e}")
        return False

def remover_obra(engine, obra_id, nome_obra):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                connection.execute(text("DELETE FROM acessos_obras WHERE obra_id = :id"), {'id': obra_id})
                connection.execute(text("DELETE FROM obras WHERE id = :id"), {'id': obra_id})
                transaction.commit()
        detalhes = f"Obra '{nome_obra}' (ID: {obra_id}) removida."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "REMOCAO_OBRA", detalhes, 'obras', obra_id)
        return True
    except Exception as e:
        st.error(f"Erro ao remover obra: {e}")
        return False

def garantir_funcionario_geral(engine):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                obra_id = connection.execute(text("SELECT id FROM obras LIMIT 1")).scalar_one_or_none()
                funcao_id = connection.execute(text("SELECT id FROM funcoes LIMIT 1")).scalar_one_or_none()
                if obra_id is None or funcao_id is None: return
                query = text("""
                    INSERT INTO funcionarios (id, nome, obra_id, funcao_id, ativo)
                    VALUES (0, 'Status Geral da Obra', :obra_id, :funcao_id, FALSE)
                    ON CONFLICT (id) DO UPDATE SET ativo = FALSE;
                """)
                connection.execute(query, {'obra_id': obra_id, 'funcao_id': funcao_id})
                transaction.commit()
    except Exception as e:
        st.error(f"Erro ao garantir funcionário geral: {e}")

def atualizar_observacoes(engine, updates_list):
    if not updates_list: return True
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE lancamentos SET observacao = :obs WHERE id = :id")
                connection.execute(query, updates_list)
                transaction.commit()
        ids = [item['id'] for item in updates_list]
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "ATUALIZACAO_OBSERVACAO_MASSA", f"Observações dos IDs {ids} atualizadas.")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar as observações: {e}")
        return False

def salvar_novos_lancamentos(df_para_salvar, engine):
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
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "SALVAR_LANCAMENTO", f"{len(lancamentos_dict)} novo(s) lançamento(s) salvo(s).")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar na base de dados: {e}")
        return False

def remover_lancamentos_por_id(ids_para_remover, engine, razao=""):
    if not ids_para_remover: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE lancamentos SET arquivado = TRUE WHERE id = ANY(:ids)")
                connection.execute(query, {'ids': ids_para_remover})
                transaction.commit()
        st.toast("Lançamentos arquivados com sucesso!", icon="🗑️")
        detalhes = f"IDs arquivados: {ids_para_remover}. Justificativa: {razao}"
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "REMOCAO_LANCAMENTO", detalhes, tabela_afetada='lancamentos')
        return True
    except Exception as e:
        st.error(f"Erro ao remover lançamentos: {e}")
        return False

def launch_monthly_sheet(obra_id, mes_dt, obra_nome):
    mes_inicio = mes_dt.strftime('%Y-%m-01')
    try:
        with Engine.connect() as connection:
            with connection.begin() as transaction:
                query_arquivar = text("UPDATE lancamentos SET arquivado = TRUE WHERE obra_id = :obra_id AND date_trunc('month', data_servico) = :mes_inicio;")
                connection.execute(query_arquivar, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                query_update_status = text("UPDATE folhas_mensais SET status = 'Finalizada' WHERE obra_id = :obra_id AND mes_referencia = :mes_inicio;")
                connection.execute(query_update_status, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                transaction.commit()
        detalhes = f"Folha da obra '{obra_nome}' (ID: {obra_id}) para {mes_dt.strftime('%Y-%m')} foi finalizada e arquivada."
        registrar_log(Engine, st.session_state.get('user_identifier', 'admin'), "FINALIZACAO_FOLHA", detalhes, tabela_afetada='folhas_mensais')
        st.toast(f"Folha de {mes_dt.strftime('%Y-%m')} finalizada e arquivada!", icon="🚀")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao finalizar a folha: {e}")
        return False

def upsert_status_auditoria(engine, obra_id, funcionario_id, status, mes_referencia, func_nome, obra_nome, comentario=None):
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                if comentario is not None:
                    query = text("""
                        INSERT INTO status_auditoria (obra_id, funcionario_id, mes_referencia, status, comentario)
                        VALUES (:obra_id, :func_id, :mes_ref, :status, :comentario)
                        ON CONFLICT (obra_id, funcionario_id, mes_referencia)
                        DO UPDATE SET status = EXCLUDED.status, comentario = EXCLUDED.comentario;
                    """)
                    params = {'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt, 'status': status, 'comentario': comentario}
                else:
                    query = text("""
                        INSERT INTO status_auditoria (obra_id, funcionario_id, mes_referencia, status)
                        VALUES (:obra_id, :func_id, :mes_ref, :status)
                        ON CONFLICT (obra_id, funcionario_id, mes_referencia)
                        DO UPDATE SET status = EXCLUDED.status;
                    """)
                    params = {'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt, 'status': status}
                connection.execute(query, params)
                transaction.commit()
        detalhes = f"Status/Comentário para '{func_nome}' na obra '{obra_nome}' para {mes_referencia} foi salvo."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "UPSERT_STATUS", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar status/comentário: {e}")
        return False

def mudar_funcionario_de_obra(engine, funcionario_id, nova_obra_id, func_nome, nova_obra_nome):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE funcionarios SET obra_id = :nova_obra_id WHERE id = :funcionario_id")
                connection.execute(query, {'nova_obra_id': nova_obra_id, 'funcionario_id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{func_nome}' movido para a obra '{nova_obra_nome}'."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_OBRA_FUNCIONARIO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao mudar funcionário de obra: {e}")
        return False

def mudar_codigo_acesso_obra(engine, obra_id, novo_codigo, obra_nome):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE acessos_obras SET codigo_acesso = :novo_codigo WHERE obra_id = :obra_id")
                connection.execute(query, {'novo_codigo': novo_codigo, 'obra_id': obra_id})
                transaction.commit()
        detalhes = f"Código de acesso da obra '{obra_nome}' foi alterado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_CODIGO_ACESSO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao alterar o código de acesso: {e}")
        return False

def save_aviso_data(engine, obra_nome, novo_aviso):
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE obras SET aviso = :aviso WHERE nome_obra = :nome")
                connection.execute(query, {'aviso': novo_aviso, 'nome': obra_nome})
                transaction.commit()
        detalhes = f"Aviso para a obra '{obra_nome}' foi atualizado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "SALVAR_AVISO_OBRA", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o aviso: {e}")
        return False

