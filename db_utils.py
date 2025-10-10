import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

@st.cache_resource(ttl=60)
def get_db_connection():
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

@st.cache_data(ttl=300)
def get_obras():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, nome_obra AS "NOME DA OBRA", status, aviso FROM obras', engine)

@st.cache_data(ttl=300)
def get_acessos():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT obra_id, codigo_acesso FROM acessos_obras', engine)

@st.cache_data(ttl=300)
def get_precos():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, disciplina as "DISCIPLINA", descricao as "DESCRIÇÃO DO SERVIÇO", unidade as "UNIDADE", valor_unitario as "VALOR" FROM servicos', engine)
    
@st.cache_data(ttl=300)
def get_funcoes():
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    return pd.read_sql('SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE" FROM funcoes', engine)

@st.cache_data(ttl=60)
def get_status_do_mes(mes_referencia):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = text("""
    SELECT sa.obra_id, o.nome_obra AS "Obra", sa.funcionario_id, f.nome AS "Funcionario",
           sa.mes_referencia AS "Mes", sa.status AS "Status", sa.comentario AS "Comentario"
    FROM status_auditoria sa
    LEFT JOIN obras o ON sa.obra_id = o.id
    LEFT JOIN funcionarios f ON sa.funcionario_id = f.id
    WHERE to_char(sa.mes_referencia, 'YYYY-MM') = :mes;
    """)
    df = pd.read_sql(query, engine, params={'mes': mes_referencia})
    if not df.empty and 'Mes' in df.columns:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df

@st.cache_data(ttl=60)
def get_folhas(mes_referencia):
    engine = get_db_connection()
    if engine is None: return pd.DataFrame()
    query = text("""
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status, f.data_lancamento, f.contador_envios
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id
    WHERE to_char(f.mes_referencia, 'YYYY-MM') = :mes;
    """)
    df = pd.read_sql(query, engine, params={'mes': mes_referencia})
    if not df.empty and 'Mes' in df.columns:
        df['Mes'] = pd.to_datetime(df['Mes']).dt.date
    return df


def upsert_status_auditoria(obra_id, funcionario_id, status, mes_referencia, comentario=None):
    engine = get_db_connection()
    if engine is None: return False
    
    mes_dt = pd.to_datetime(mes_referencia, format='%Y-%m').date()

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                if comentario is not None:
                    set_clause = "SET status = :status, comentario = :comentario"
                    params = {'status': status, 'comentario': comentario, 'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt}
                else:
                    set_clause = "SET status = :status"
                    params = {'status': status, 'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt}
                
                query_insert = text(f"""
                    INSERT INTO status_auditoria (obra_id, funcionario_id, mes_referencia, status, comentario)
                    VALUES (:obra_id, :func_id, :mes_ref, :status, :comentario)
                    ON CONFLICT (obra_id, funcionario_id, mes_referencia)
                    DO UPDATE {set_clause};
                """)
                
                # Garante que o comentário tenha um valor padrão para o INSERT
                insert_params = {'obra_id': obra_id, 'func_id': funcionario_id, 'mes_ref': mes_dt, 'status': status, 'comentario': comentario or ""}
                
                connection.execute(query_insert, insert_params)
                transaction.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o status: {e}")
        return False

def launch_monthly_sheet(obra_id, mes_referencia_dt, obra_nome):
    engine = get_db_connection()
    if engine is None: return False
    mes_inicio = mes_referencia_dt.strftime('%Y-%m-01')
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_arquivar = text("""
                    UPDATE lancamentos SET arquivado = TRUE
                    WHERE obra_id = :obra_id AND date_trunc('month', data_servico) = :mes_inicio;
                """)
                connection.execute(query_arquivar, {'obra_id': obra_id, 'mes_inicio': mes_inicio})

                query_update_status = text("""
                    UPDATE folhas_mensais SET status = 'Finalizada'
                    WHERE obra_id = :obra_id AND mes_referencia = :mes_inicio;
                """)
                connection.execute(query_update_status, {'obra_id': obra_id, 'mes_inicio': mes_inicio})
                transaction.commit()
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
                query = text("""
                    UPDATE folhas_mensais SET status = 'Devolvida para Revisão'
                    WHERE obra_id = :obra_id AND mes_referencia = :mes_ref
                """)
                connection.execute(query, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
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
                    DO UPDATE SET 
                        status = 'Enviada para Auditoria',
                        data_lancamento = NOW(),
                        contador_envios = folhas_mensais.contador_envios + 1;
                """)
                connection.execute(query_insert, {'obra_id': obra_id, 'mes_ref': mes_dt})
                transaction.commit()
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao enviar a folha: {e}")
        return False

def salvar_novos_lancamentos(df_para_salvar):
    engine = get_db_connection()
    if engine is None: return False
    lancamentos_dict = df_para_salvar.to_dict(orient='records')
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO lancamentos (data_servico, obra_id, funcionario_id, servico_id,
                                           servico_diverso_descricao, quantidade, valor_unitario, observacao, data_lancamento)
                    VALUES (:data_servico, :obra_id, :funcionario_id, :servico_id,
                            :servico_diverso_descricao, :quantidade, :valor_unitario, :observacao, :data_lancamento)
                """)
                connection.execute(query, lancamentos_dict)
                transaction.commit()
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar na base de dados: {e}")
        return False
        
def remover_lancamentos_por_id(ids_para_remover, razao=""):
    engine = get_db_connection()
    if engine is None: return False
    if not ids_para_remover: return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("DELETE FROM lancamentos WHERE id = ANY(:ids)")
                connection.execute(query, {'ids': ids_para_remover})
                transaction.commit()
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
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar as observações: {e}")
        return False

