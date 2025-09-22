import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
from datetime import date
from sqlalchemy import create_engine, text
import numpy as np
import re
import plotly.express as px
import io

st.set_page_config(
    page_title="Cadastro de Produção",
    page_icon="Lavie1.png",
    layout="wide"
)

st.markdown("""
<style>
    /* ... (seu CSS continua o mesmo) ... */
</style>
""", unsafe_allow_html=True)

@st.cache_resource(ttl=60)
def get_db_connection():
    try:
        engine = create_engine(st.secrets["database"]["url"])
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return None

def registrar_log(engine, usuario, acao, detalhes="", tabela_afetada=None, id_registro_afetado=None):
    """Registra uma ação no log de auditoria, com detalhes de tabela e registro."""
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
                    'usuario': usuario,
                    'acao': acao,
                    'detalhes': detalhes,
                    'tabela_afetada': tabela_afetada,
                    'id_registro_afetado': id_registro_afetado
                })
                transaction.commit()
    except Exception as e:
        st.toast(f"Falha ao registrar log: {e}", icon="⚠️")


@st.cache_data
def load_data(_engine):
    if _engine is None:
        st.stop()

    query_funcionarios = """
    SELECT
        f.id,
        f.obra_id,
        f.nome as "NOME",
        o.nome_obra as "OBRA",
        fn.funcao as "FUNÇÃO",
        fn.tipo as "TIPO",
        fn.salario_base as "SALARIO_BASE"
    FROM funcionarios f
    JOIN obras o ON f.obra_id = o.id
    JOIN funcoes fn ON f.funcao_id = fn.id
    WHERE f.ativo = TRUE; -- Adicione esta linha
    """
    funcionarios_df = pd.read_sql(query_funcionarios, _engine)


    query_lancamentos = """
    SELECT
        l.id, l.data_lancamento, l.data_servico, l.obra_id,
        o.nome_obra AS "Obra", f.nome AS "Funcionário", s.disciplina AS "Disciplina",
        COALESCE(s.descricao, ve.descricao, l.servico_diverso_descricao) AS "Serviço",
        CAST(l.quantidade AS INTEGER) AS "Quantidade",
        COALESCE(s.unidade, ve.unidade, 'UN') AS "Unidade",
        l.valor_unitario AS "Valor Unitário",
        (l.quantidade * l.valor_unitario) AS "Valor Parcial",
        l.observacao AS "Observação"
    FROM lancamentos l
    LEFT JOIN obras o ON l.obra_id = o.id
    LEFT JOIN funcionarios f ON l.funcionario_id = f.id
    LEFT JOIN servicos s ON l.servico_id = s.id
    LEFT JOIN valores_extras ve ON l.valor_extra_id = ve.id
    WHERE l.arquivado = FALSE;
    """
    lancamentos_df = pd.read_sql(query_lancamentos, _engine)

    if not lancamentos_df.empty:
        lancamentos_df = lancamentos_df.rename(columns={
            'data_lancamento': 'Data',
            'data_servico': 'Data do Serviço'
        })
        lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'])
        lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'])

    query_status = """
    SELECT
        sa.obra_id,
        o.nome_obra AS "Obra",
        sa.funcionario_id, -- ADD THIS LINE
        f.nome AS "Funcionario",
        sa.mes_referencia AS "Mes",
        sa.status AS "Status",
        sa.comentario AS "Comentario"
    FROM status_auditoria sa
    LEFT JOIN obras o ON sa.obra_id = o.id
    LEFT JOIN funcionarios f ON sa.funcionario_id = f.id;
    """
    status_df = pd.read_sql(query_status, _engine)
    if not status_df.empty and 'Mes' in status_df.columns:
        status_df['Mes'] = pd.to_datetime(status_df['Mes']).dt.date

    query_folhas = """
    SELECT f.obra_id, o.nome_obra AS "Obra", f.mes_referencia AS "Mes", f.status
    FROM folhas_mensais f
    LEFT JOIN obras o ON f.obra_id = o.id;
    """
    folhas_df = pd.read_sql(query_folhas, _engine)

    precos_df = pd.read_sql('SELECT id, disciplina as "DISCIPLINA", descricao as "DESCRIÇÃO DO SERVIÇO", unidade as "UNIDADE", valor_unitario as "VALOR" FROM servicos', _engine)
    obras_df = pd.read_sql('SELECT id, nome_obra AS "NOME DA OBRA", status, aviso FROM obras', _engine)
    valores_extras_df = pd.read_sql('SELECT id, descricao as "VALORES EXTRAS", unidade as "UNIDADE", valor as "VALOR" FROM valores_extras', _engine)
    funcoes_df = pd.read_sql('SELECT id, funcao as "FUNÇÃO", tipo as "TIPO", salario_base as "SALARIO_BASE" FROM funcoes', _engine)
    acessos_df = pd.read_sql('SELECT obra_id, codigo_acesso FROM acessos_obras', _engine)

    return funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_df, status_df, funcoes_df, folhas_df, acessos_df


def salvar_dados(df_para_salvar, nome_tabela, _engine):
    try:
        df_para_salvar.to_sql(nome_tabela, _engine, if_exists='append', index=False)
        st.cache_data.clear()
        st.toast("Dados salvos com sucesso!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar em '{nome_tabela}': {e}")
        return False

def adicionar_funcionario(engine, nome, funcao_id, obra_id):
    """Insere um novo funcionário no banco de dados."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO funcionarios (nome, funcao_id, obra_id)
                    VALUES (:nome, :funcao_id, :obra_id)
                """)
                connection.execute(query, {'nome': nome, 'funcao_id': funcao_id, 'obra_id': obra_id})
                transaction.commit()
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "ADICAO_FUNCIONARIO", f"Funcionário '{nome}' adicionado.")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar funcionário no banco de dados: {e}")
        return False

def remover_funcionario(engine, funcionario_id, nome_funcionario):
    """'Remove' um funcionário marcando-o como inativo."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE funcionarios SET ativo = FALSE WHERE id = :id")
                connection.execute(query, {'id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{nome_funcionario}' (ID: {funcionario_id}) inativado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "REMOCAO_FUNCIONARIO", detalhes, tabela_afetada='funcionarios', id_registro_afetado=funcionario_id)
        return True
    except Exception as e:
        st.error(f"Erro ao inativar funcionário no banco de dados: {e}")
        return False

def adicionar_obra(engine, nome_obra, codigo_acesso):
    """Insere uma nova obra e seu código de acesso em uma única transação."""
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
        st.error(f"Erro ao adicionar obra no banco de dados: {e}")
        return False

def remover_obra(engine, obra_id, nome_obra):
    """Remove uma obra do banco de dados pelo seu ID."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_acesso = text("DELETE FROM acessos_obras WHERE obra_id = :id")
                connection.execute(query_acesso, {'id': obra_id})

                query_obra = text("DELETE FROM obras WHERE id = :id")
                connection.execute(query_obra, {'id': obra_id})
                transaction.commit()
        detalhes = f"Obra '{nome_obra}' (ID: {obra_id}) removida."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "REMOCAO_OBRA", detalhes, tabela_afetada='obras', id_registro_afetado=obra_id)
        return True
    except Exception as e:
        st.error(f"Erro ao remover obra do banco de dados: {e}")
        return False

def atualizar_observacao_lancamento(engine, lancamento_id, nova_observacao):
    """Atualiza a observação de um lançamento específico."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE lancamentos
                    SET observacao = :obs
                    WHERE id = :id
                """)
                connection.execute(query, {'obs': nova_observacao, 'id': lancamento_id})
                transaction.commit()
        detalhes = f"Observação do lançamento ID {lancamento_id} atualizada."
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "ATUALIZACAO_OBSERVACAO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar observação: {e}")
        return False

def garantir_funcionario_geral(engine):
    try:
        with engine.connect() as connection:
            obra_id = connection.execute(text("SELECT id FROM obras LIMIT 1")).scalar_one_or_none()
            funcao_id = connection.execute(text("SELECT id FROM funcoes LIMIT 1")).scalar_one_or_none()

            if obra_id is None or funcao_id is None:
                st.warning("Não foi possível criar o funcionário geral. Cadastre pelo menos uma obra e uma função.")
                return

            query = text("""
                INSERT INTO funcionarios (id, nome, obra_id, funcao_id)
                VALUES (0, 'Status Geral da Obra', :obra_id, :funcao_id)
                ON CONFLICT (id) DO NOTHING;
            """)
            connection.execute(query, {'obra_id': obra_id, 'funcao_id': funcao_id})
            connection.commit()

            print(">>> Funcionário geral com ID 0 garantido no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao tentar garantir o funcionário geral: {e}")

def atualizar_observacoes(engine, updates_list):
    """
    Atualiza a observação de múltiplos lançamentos em uma única transação.
    'updates_list' deve ser uma lista de dicionários, ex: [{'id': 1, 'obs': 'texto'}, ...]
    """
    if not updates_list:
        return True

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("UPDATE lancamentos SET observacao = :obs WHERE id = :id")
                connection.execute(query, updates_list)
                transaction.commit()
        ids_atualizados = [item['id'] for item in updates_list]
        detalhes = f"Observações dos lançamentos IDs {ids_atualizados} foram atualizadas."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "ATUALIZACAO_OBSERVACAO_MASSA", detalhes)
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar as observações: {e}")
        return False

def salvar_novos_lancamentos(df_para_salvar, engine):
    """
    Salva um DataFrame de novos lançamentos no banco de dados
    dentro de uma única transação.
    """
    lancamentos_dict = df_para_salvar.to_dict(orient='records')

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    INSERT INTO lancamentos (
                        data_servico, obra_id, funcionario_id, servico_id,
                        valor_extra_id, servico_diverso_descricao, quantidade,
                        valor_unitario, observacao, data_lancamento
                    ) VALUES (
                        :data_servico, :obra_id, :funcionario_id, :servico_id,
                        :valor_extra_id, :servico_diverso_descricao, :quantidade,
                        :valor_unitario, :observacao, :data_lancamento
                    )
                """)
                connection.execute(query, lancamentos_dict)
                transaction.commit()
        num_lancamentos = len(lancamentos_dict)
        detalhes = f"{num_lancamentos} novo(s) lançamento(s) salvo(s)."
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "SALVAR_LANCAMENTO", detalhes)
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro ao salvar na base de dados: {e}")
        return False

def remover_lancamentos_por_id(ids_para_remover, engine, razao=""):
    if not ids_para_remover:
        return False
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("DELETE FROM lancamentos WHERE id = ANY(:ids)")
                connection.execute(query, {'ids': ids_para_remover})
                transaction.commit()
        st.toast("Lançamentos removidos com sucesso!", icon="🗑️")
        detalhes = f"IDs removidos: {ids_para_remover}. Justificativa: {razao}"
        registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "REMOCAO_LANCAMENTO", detalhes, tabela_afetada='lancamentos')
        return True
    except Exception as e:
        st.error(f"Erro ao remover lançamentos: {e}")
        return False

def launch_monthly_sheet(obra_id, mes_dt, obra_nome):
        mes_inicio = mes_dt.strftime('%Y-%m-01')
        try:
            with engine.connect() as connection:
                with connection.begin() as transaction:
                    query_update = text("""
                        UPDATE "Lancamentos"
                        SET arquivado = TRUE
                        WHERE obra_id = :obra_id
                        AND date_trunc('month', data_servico) = :mes_inicio;
                    """)
                    connection.execute(query_update, {'obra_id': obra_id, 'mes_inicio': mes_inicio})

                    query_insert = text("""
                        INSERT INTO "Folhas_Mensais" (obra_id, mes_referencia, status)
                        VALUES (:obra_id, :mes_inicio, 'Lançada')
                        ON CONFLICT (obra_id, mes_referencia) DO NOTHING;
                    """)
                    connection.execute(query_insert, {'obra_id': obra_id, 'mes_inicio': mes_inicio})

                    transaction.commit()
            detalhes = f"Folha da obra '{obra_nome}' (ID: {obra_id}) para o mês {mes_dt.strftime('%Y-%m')} foi lançada."
            registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "LANCAMENTO_FOLHA", detalhes)
            st.toast(f"Folha de {mes_dt.strftime('%Y-%m')} lançada e arquivada!", icon="🚀")
            return True

        except Exception as e:
            st.error(f"Ocorreu um erro ao lançar a folha: {e}")
            return False

def save_geral_status_obra(engine, obra_id, status, mes_referencia, obra_nome):
    """Insere ou atualiza o status GERAL de uma obra para um mês específico."""
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)
    ID_FUNCIONARIO_GERAL = 0

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_update = text("""
                    UPDATE status_auditoria
                    SET status = :status
                    WHERE obra_id = :obra_id
                    AND funcionario_id = :id_geral
                    AND mes_referencia = :mes_ref
                """)
                result = connection.execute(query_update, {
                    'status': status, 'obra_id': obra_id,
                    'id_geral': ID_FUNCIONARIO_GERAL, 'mes_ref': mes_dt
                })

                if result.rowcount == 0:
                    query_insert = text("""
                        INSERT INTO status_auditoria
                        (obra_id, funcionario_id, mes_referencia, status, comentario)
                        VALUES (:obra_id, :id_geral, :mes_ref, :status, 'Status Geral da Obra')
                    """)
                    connection.execute(query_insert, {
                        'obra_id': obra_id, 'id_geral': ID_FUNCIONARIO_GERAL,
                        'mes_ref': mes_dt, 'status': status
                    })

                transaction.commit()
        detalhes = f"Status de '{func_nome}' na obra '{obra_nome}' para {mes_referencia} alterado para '{status}'."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_STATUS_FUNCIONARIO", detalhes, tabela_afetada='status_auditoria', id_registro_afetado=funcionario_id)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o status geral da obra: {e}")
        return False

def save_status_data(engine, obra_id, funcionario_id, status, mes_referencia, func_nome, obra_nome):
    """Insere ou atualiza o status de um funcionário para um mês/obra específico."""
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_update = text("""
                    UPDATE status_auditoria
                    SET status = :status
                    WHERE obra_id = :obra_id
                    AND funcionario_id = :funcionario_id
                    AND mes_referencia = :mes_ref
                """)
                result = connection.execute(query_update, {
                    'status': status,
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
                    'mes_ref': mes_dt
                })
                if result.rowcount == 0:
                    query_insert = text("""
                        INSERT INTO status_auditoria
                        (obra_id, funcionario_id, mes_referencia, status, comentario)
                        VALUES (:obra_id, :funcionario_id, :mes_ref, :status, '')
                    """)
                    connection.execute(query_insert, {
                        'obra_id': obra_id,
                        'funcionario_id': funcionario_id,
                        'mes_ref': mes_dt,
                        'status': status
                    })

                transaction.commit()
        detalhes = f"Status do funcionário '{func_nome}' (ID: {funcionario_id}) na obra '{obra_nome}' para o mês {mes_referencia} alterado para '{status}'."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_STATUS_FUNCIONARIO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o status: {e}")
        return False

def save_comment_data(engine, obra_id, funcionario_id, comentario, mes_referencia, func_nome, obra_nome):
    """Insere ou atualiza o comentário de um funcionário para um mês/obra específico."""
    mes_dt = pd.to_datetime(mes_referencia).date().replace(day=1)

    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query_update = text("""
                    UPDATE status_auditoria
                    SET comentario = :comentario
                    WHERE obra_id = :obra_id
                    AND funcionario_id = :funcionario_id
                    AND mes_referencia = :mes_ref
                """)
                result = connection.execute(query_update, {
                    'comentario': comentario,
                    'obra_id': obra_id,
                    'funcionario_id': funcionario_id,
                    'mes_ref': mes_dt
                })

                if result.rowcount == 0:
                    query_insert = text("""
                        INSERT INTO status_auditoria
                        (obra_id, funcionario_id, mes_referencia, status, comentario)
                        VALUES (:obra_id, :funcionario_id, :mes_ref, 'A Revisar', :comentario)
                    """)
                    connection.execute(query_insert, {
                        'obra_id': obra_id,
                        'funcionario_id': funcionario_id,
                        'mes_ref': mes_dt,
                        'comentario': comentario
                    })

                transaction.commit()
        detalhes = f"Comentário para '{func_nome}' (ID: {funcionario_id}) na obra '{obra_nome}' para o mês {mes_referencia} foi salvo."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "SALVAR_COMENTARIO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o comentário: {e}")
        return False

def mudar_funcionario_de_obra(engine, funcionario_id, nova_obra_id, func_nome, nova_obra_nome):
    """Muda um funcionário para uma nova obra no banco de dados."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE funcionarios
                    SET obra_id = :nova_obra_id
                    WHERE id = :funcionario_id
                """)
                connection.execute(query, {'nova_obra_id': nova_obra_id, 'funcionario_id': funcionario_id})
                transaction.commit()
        detalhes = f"Funcionário '{func_nome}' (ID: {funcionario_id}) movido para a obra '{nova_obra_nome}'."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_OBRA_FUNCIONARIO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao mudar funcionário de obra: {e}")
        return False

def mudar_codigo_acesso_obra(engine, obra_id, novo_codigo, obra_nome):
    """Altera o código de acesso de uma obra específica."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE acessos_obras
                    SET codigo_acesso = :novo_codigo
                    WHERE obra_id = :obra_id
                """)
                connection.execute(query, {'novo_codigo': novo_codigo, 'obra_id': obra_id})
                transaction.commit()
        detalhes = f"Código de acesso da obra '{obra_nome}' (ID: {obra_id}) foi alterado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "MUDANCA_CODIGO_ACESSO", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao alterar o código de acesso: {e}")
        return False

def save_aviso_data(engine, obra_nome, novo_aviso):
    """Atualiza o aviso de uma obra específica no banco de dados."""
    try:
        with engine.connect() as connection:
            with connection.begin() as transaction:
                query = text("""
                    UPDATE obras
                    SET aviso = :aviso
                    WHERE nome_obra = :nome
                """)
                connection.execute(query, {'aviso': novo_aviso, 'nome': obra_nome})
                transaction.commit()
        detalhes = f"Aviso para a obra '{obra_nome}' foi atualizado."
        registrar_log(engine, st.session_state.get('user_identifier', 'admin'), "SALVAR_AVISO_OBRA", detalhes)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o aviso: {e}")
        return False

def calcular_salario_final(row):
    if str(row['TIPO']).upper() == 'PRODUCAO':
        return max(row['SALÁRIO BASE (R$)'], row['PRODUÇÃO (R$)'])
    else:
        return row['SALÁRIO BASE (R$)'] + row['PRODUÇÃO (R$)']


def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DadosFiltrados')
    processed_data = output.getvalue()
    return processed_data

def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

def safe_float(value):
    try:
        s = str(value).replace('R$', '').strip()
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def display_status_box(label, status):
    if status == 'Aprovado':
        st.success(f"{label}: {status}")
    elif status == 'Analisar':
        st.error(f"{label}: {status}")
    else:
        st.info(f"{label}: {status}")


def style_status(status):
    color = 'gray'
    if status == 'Aprovado':
        color = 'green'
    elif status == 'Analisar':
        color = 'red'
    return f'color: {color}; font-weight: bold;'

def login_page(obras_df, acessos_df):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Lavie.png", width=1000)

    st.header("Login")

    admin_login = st.checkbox("Entrar como Administrador")

    if admin_login:
        admin_password = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar como Admin", use_container_width=True, type="primary"):
            if 'admin' in st.secrets and st.secrets.admin.password == admin_password:
                st.session_state['logged_in'] = True
                st.session_state['role'] = 'admin'
                st.session_state['obra_logada'] = 'Todas'
                st.session_state['user_identifier'] = 'admin'
                registrar_log(engine, 'admin', "LOGIN_SUCCESS")
                st.rerun()
            else:
                registrar_log(engine, 'admin', "LOGIN_FAIL", "Senha incorreta.")
                st.error("Senha de administrador incorreta.")
    else:
        obras_com_acesso = pd.merge(obras_df, acessos_df, left_on='id', right_on='obra_id')

        obra_login = st.selectbox("Selecione a Obra", options=obras_com_acesso['NOME DA OBRA'].unique(), index=None, placeholder="Escolha a obra...")
        codigo_login = st.text_input("Código de Acesso", type="password")

        if st.button("Entrar", use_container_width=True, type="primary"):
            if obra_login and codigo_login:
                try:
                    codigo_correto = obras_com_acesso.loc[obras_com_acesso['NOME DA OBRA'] == obra_login, 'codigo_acesso'].iloc[0]
                    if codigo_correto == codigo_login:
                        st.session_state['logged_in'] = True
                        st.session_state['role'] = 'user'
                        st.session_state['obra_logada'] = obra_login
                        st.session_state['user_identifier'] = f"user:{obra_login}"
                        registrar_log(engine, f"user:{obra_login}", "LOGIN_SUCCESS")
                        st.rerun()
                    else:
                        registrar_log(engine, f"user:{obra_login}", "LOGIN_FAIL", "Código incorreto.")
                        st.error("Obra ou código de acesso incorreto.")
                except IndexError:
                    st.error("Obra ou código de acesso incorreto.")
            else:
                st.warning("Por favor, selecione a obra e insira o código.")

engine = get_db_connection()

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    try:
        obras_df_login = pd.read_sql('SELECT id, nome_obra AS "NOME DA OBRA" FROM obras', engine)
        acessos_df_login = pd.read_sql('SELECT obra_id, codigo_acesso FROM acessos_obras', engine)
        login_page(obras_df_login, acessos_df_login)
    except Exception as e:
        st.error(f"Não foi possível conectar à base de dados para o login. Verifique os segredos e a conexão. Erro: {e}")
else:
    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = datetime.now().strftime('%Y-%m')
    garantir_funcionario_geral(engine)
    funcionarios_df, precos_df, obras_df, valores_extras_df, lancamentos_df, status_df, funcoes_df, folhas_df, acessos_df = load_data(engine)

    if st.session_state.get('new_launch_received', False):
        st.toast("Novo lançamento recebido! Atualizando a lista...")
        st.session_state['new_launch_received'] = False 
        st.cache_data.clear()
        st.rerun()
    
    
    if 'page' not in st.session_state:
        st.session_state.page = "Auditoria ✏️" if st.session_state['role'] == 'admin' else "Lançamento Folha 📝"

    with st.sidebar:
        st.image("Lavie.png", use_container_width=True)
        if st.session_state['role'] == 'admin':
            st.warning("Visão de Administrador")
        else:
            st.metric(label="Obra Ativa", value=st.session_state['obra_logada'])
            obra_logada = st.session_state['obra_logada']
            obra_logada_nome = st.session_state['obra_logada']
            obra_logada_id = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada_nome, 'id'].iloc[0]
            status_geral_obra_row = status_df[status_df['obra_id'] == obra_logada_id] 
            status_atual = 'A Revisar'
            display_status_box("Status da Obra", status_atual)
            aviso_obra = ""
            obra_logada_nome = st.session_state['obra_logada']

            if 'aviso' in obras_df.columns and not obras_df[obras_df['NOME DA OBRA'] == obra_logada_nome].empty:
                aviso_obra = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada_nome, 'aviso'].iloc[0]

            if aviso_obra and str(aviso_obra).strip():
                st.error(f"📢 Aviso da Auditoria: {aviso_obra}")
        
        st.markdown("---")
        
        st.subheader("Mês de Referência")
        todos_lancamentos_df = lancamentos_df.copy()
        lancamentos_do_mes_df = pd.DataFrame()
        
        available_months = []
        if not todos_lancamentos_df.empty:
            todos_lancamentos_df['Data'] = pd.to_datetime(todos_lancamentos_df['Data'])
            mes_selecionado_periodo = pd.Period(st.session_state.selected_month, 'M')
            lancamentos_do_mes_df = todos_lancamentos_df[
                todos_lancamentos_df['Data'].dt.to_period('M') == mes_selecionado_periodo
            ].copy()

        current_month_str = datetime.now().strftime('%Y-%m')
        if current_month_str not in available_months:
            available_months.append(current_month_str)

        if 'selected_month' not in st.session_state:
            st.session_state.selected_month = current_month_str

        selected_month = st.selectbox(
            "Selecione o Mês", 
            options=available_months, 
            index=available_months.index(st.session_state.selected_month if st.session_state.selected_month in available_months else current_month_str),
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
        
        st.markdown("---")
        st.subheader("Menu")
        if 'page' not in st.session_state:
            st.session_state.page = "Auditoria ✏️" if st.session_state['role'] == 'admin' else "Lançamento Folha 📝"
        
        if st.session_state['role'] == 'user':
            if st.button("Lançamento Folha 📝", use_container_width=True):
                st.session_state.page = "Lançamento Folha 📝"
        else:
            if st.button("Auditoria ✏️", use_container_width=True):
                st.session_state.page = "Auditoria ✏️"
            if st.button("Gerenciar Funcionários 👥", use_container_width=True):
                st.session_state.page = "Gerenciar Funcionários"
            if st.button("Gerenciar Obras 🏗️", use_container_width=True):
                st.session_state.page = "Gerenciar Obras"

        if st.button("Resumo da Folha 📊", use_container_width=True):
            st.session_state.page = "Resumo da Folha 📊"
        if st.button("Remover Lançamentos 🗑️", use_container_width=True):
            st.session_state.page = "Remover Lançamentos 🗑️"
        if st.button("Dashboard de Análise 📈", use_container_width=True):
            st.session_state.page = "Dashboard de Análise 📈"
        
        st.markdown("---")
        st.header("Ferramentas")
        st.subheader("Backup dos Dados")
        if st.button("📥 Baixar Backup em Excel", use_container_width=True):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(st.session_state.lancamentos).drop(columns=['id_lancamento'], errors='ignore').to_excel(writer, sheet_name='Lançamentos', index=False)
                funcionarios_df.to_excel(writer, sheet_name='Funcionários', index=False)
                precos_df.to_excel(writer, sheet_name='Tabela de Preços', index=False)
                valores_extras_df.to_excel(writer, sheet_name='Valores Extras', index=False)
                obras_df.to_excel(writer, sheet_name='Obras', index=False)
            st.download_button(
                label="Clique para baixar o backup",
                data=output.getvalue(),
                file_name=f"backup_producao_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        st.markdown("---")
        if st.button("Sair 🚪", use_container_width=True):
            registrar_log(engine, st.session_state.get('user_identifier', 'unknown'), "LOGOUT")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if not lancamentos_df.empty:
            mes_selecionado_dt = pd.to_datetime(st.session_state.selected_month)
            lancamentos_df['Data'] = pd.to_datetime(lancamentos_df['Data'])
            lancamentos_df = lancamentos_df[
                (lancamentos_df['Data'].dt.month == mes_selecionado_dt.month) &
                (lancamentos_df['Data'].dt.year == mes_selecionado_dt.year)
            ]
   
    if st.session_state.page == "Lançamento Folha 📝" and st.session_state['role'] == 'user':
        st.header("Adicionar Novo Lançamento de Produção")
        
        obra_logada = st.session_state['obra_logada']
        mes_selecionado = st.session_state.selected_month
        obra_logada_id = obras_df.loc[obras_df['NOME DA OBRA'] == obra_logada, 'id'].iloc[0]
        mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)
        folha_lancada_row = folhas_df[(folhas_df['obra_id'] == obra_logada_id) & (folhas_df['Mes'] == mes_selecionado_dt)]
        is_launched = not folha_lancada_row.empty

        if is_launched:
            st.error(f" Mês Fechado: A folha de {mes_selecionado} para a obra {obra_logada} já foi lançada. Não é possível adicionar ou alterar lançamentos.")
        else:
            col_form, col_view = st.columns(2)
            with col_form:
                
                st.markdown(f"##### 📍 Lançamento para a Obra: **{st.session_state['obra_logada']}**")
                with st.container(border=True):
                    obra_selecionada = st.session_state['obra_logada']
                    opcoes_funcionario = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique()
                    funcionario_selecionado = st.selectbox("Selecione o Funcionário", options=opcoes_funcionario, index=None, placeholder="Selecione um funcionário...")
                    if funcionario_selecionado:
                        funcao_selecionada = funcionarios_df.loc[funcionarios_df['NOME'] == funcionario_selecionado, 'FUNÇÃO'].iloc[0]
                        st.metric(label="Função do Colaborador", value=funcao_selecionada)

                st.markdown("##### 🛠️ Selecione o Serviço Principal")
                with st.container(border=True):
                    disciplinas = precos_df['DISCIPLINA'].unique()
                    disciplina_selecionada = st.selectbox("Disciplina", options=disciplinas, index=None, placeholder="Selecione...")
                    opcoes_servico = []
                    if disciplina_selecionada:
                        opcoes_servico = precos_df[precos_df['DISCIPLINA'] == disciplina_selecionada]['DESCRIÇÃO DO SERVIÇO'].unique()
                    servico_selecionado = st.selectbox("Descrição do Serviço", options=opcoes_servico, index=None, placeholder="Selecione uma disciplina...", disabled=(not disciplina_selecionada))
                    
                    quantidade_principal = 0 
                    if servico_selecionado:
                        servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                        kpi1, kpi2 = st.columns(2)
                        kpi1.metric(label="Unidade", value=servico_info['UNIDADE'])
                        kpi2.metric(label="Valor Unitário", value=format_currency(servico_info['VALOR']))
                        
                        col_qtd, col_parcial = st.columns(2)
                        with col_qtd:
                            quantidade_principal = st.number_input("Quantidade", min_value=0, step=1, key="qty_principal")
                        with col_parcial:
                            valor_unitario = safe_float(servico_info.get('VALOR'))
                            valor_parcial_servico = quantidade_principal * valor_unitario
                            st.metric(label="Subtotal do Serviço", value=format_currency(valor_parcial_servico))
                        
                        col_data_princ, col_obs_princ = st.columns(2)
                        with col_data_princ:
                            data_servico_principal = st.date_input("Data do Serviço", value=None, key="data_principal", format="DD/MM/YYYY")
                        with col_obs_princ:
                            obs_principal = st.text_area("Observação (Obrigatório)", key="obs_principal")
                
                st.markdown("##### Adicione Itens Extras")
                with st.expander("📝 Lançar Item Diverso"):
                    descricao_diverso = st.text_input("Descrição do Item Diverso")
                    valor_diverso = st.number_input("Valor Unitário (R$)", min_value=0.0, step=1.00, format="%.2f", key="valor_diverso")
                    quantidade_diverso = st.number_input("Quantidade", min_value=0, step=1, key="qty_diverso")
                    
                    col_data_div, col_obs_div = st.columns(2)
                    with col_data_div:
                        data_servico_diverso = st.date_input("Data do Serviço", value=None, key="data_diverso", format="DD/MM/YYYY")
                    with col_obs_div:
                        obs_diverso = st.text_area("Observação (Obrigatório)", key="obs_diverso")

                if st.button("✅ Adicionar Lançamento", use_container_width=True, type="primary"):
                    if not funcionario_selecionado:
                        st.warning("Por favor, selecione um funcionário.")
                    else:
                        erros = []
                        if servico_selecionado and quantidade_principal > 0 and not obs_principal.strip():
                            erros.append("Para o Serviço Principal, o campo 'Observação' é obrigatório.")
                        if descricao_diverso and quantidade_diverso > 0 and not obs_diverso.strip():
                            erros.append("Para o Item Diverso, o campo 'Observação' é obrigatório.")
                        for extra in extras_selecionados:
                            if quantidades_extras.get(extra, 0) > 0:
                                if not datas_servico_extras.get(extra):
                                    erros.append(f"Para o Item Extra '{extra}', a 'Data do Serviço' é obrigatória.")
                                if not observacoes_extras.get(extra, "").strip():
                                    erros.append(f"Para o Item Extra '{extra}', a 'Observação' é obrigatória.")
                        
                        if erros:
                            for erro in erros:
                                st.warning(erro)
                        else:
                            novos_lancamentos_dicts = []
                            agora = datetime.now()
                            data_de_hoje = date.today()
                            obra_selecionada_nome = st.session_state['obra_logada']
                            if servico_selecionado and quantidade_principal > 0:
                                servico_info = precos_df[precos_df['DESCRIÇÃO DO SERVIÇO'] == servico_selecionado].iloc[0]
                                valor_unitario = safe_float(servico_info.get('VALOR', 0))
                                novos_lancamentos_dicts.append({
                                    'data_servico': data_servico_principal if data_servico_principal else data_de_hoje,
                                    'obra_nome': obra_selecionada_nome, 'funcionario_nome': funcionario_selecionado,
                                    'servico_id': servico_info['id'], 'valor_extra_id': None, 'servico_diverso_descricao': None,
                                    'quantidade': quantidade_principal, 'valor_unitario': valor_unitario, 'observacao': obs_principal, 'data_lancamento': agora, 'servico_nome': servico_selecionado
                                })
                            if descricao_diverso and quantidade_diverso > 0 and valor_diverso > 0:
                                novos_lancamentos_dicts.append({
                                    'data_servico': data_servico_diverso if data_servico_diverso else data_de_hoje,
                                    'obra_nome': obra_selecionada_nome, 'funcionario_nome': funcionario_selecionado,
                                    'servico_id': None, 'valor_extra_id': None, 'servico_diverso_descricao': descricao_diverso,
                                    'quantidade': quantidade_diverso, 'valor_unitario': valor_diverso, 'observacao': obs_diverso, 'data_lancamento': agora, 'servico_nome': descricao_diverso
                                })

                            for extra in extras_selecionados:
                                if quantidades_extras.get(extra, 0) > 0:
                                    extra_info = valores_extras_df[valores_extras_df['VALORES EXTRAS'] == extra].iloc[0]
                                    valor_unitario_extra = safe_float(extra_info.get('VALOR', 0))
                                    novos_lancamentos_dicts.append({
                                        'data_servico': datas_servico_extras[extra],
                                        'obra_nome': obra_selecionada_nome, 'funcionario_nome': funcionario_selecionado,
                                        'servico_id': None, 'valor_extra_id': extra_info['id'], 'servico_diverso_descricao': None,
                                        'quantidade': quantidades_extras[extra], 'valor_unitario': valor_unitario_extra, 'observacao': observacoes_extras[extra], 'data_lancamento': agora, 'servico_nome': extra
                                    })
       
                            if novos_lancamentos_dicts:
                                df_para_salvar = pd.DataFrame(novos_lancamentos_dicts)
                                obra_id_map = obras_df.set_index('NOME DA OBRA')['id']
                                func_id_map = funcionarios_df.set_index('NOME')['id']

                                df_para_salvar['obra_id'] = df_para_salvar['obra_nome'].map(obra_id_map)
                                df_para_salvar['funcionario_id'] = df_para_salvar['funcionario_nome'].map(func_id_map)
                                colunas_db = [
                                    'data_servico', 'obra_id', 'funcionario_id', 'servico_id',
                                    'valor_extra_id', 'servico_diverso_descricao', 'quantidade',
                                    'valor_unitario', 'observacao', 'data_lancamento'
                                ]
                                df_final_para_db = df_para_salvar[colunas_db]
                                df_final_para_db['servico_id'] = df_final_para_db['servico_id'].astype('Int64')
                                df_final_para_db['valor_extra_id'] = df_final_para_db['valor_extra_id'].astype('Int64')


                                if salvar_novos_lancamentos(df_final_para_db, engine):
                                    st.success("Lançamento(s) adicionado(s) com sucesso!")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.info("Nenhum serviço ou item com quantidade maior que zero foi adicionado.")
                                    pass
                                    
            with col_view:
                if 'funcionario_selecionado' in locals() and funcionario_selecionado:
                    st.subheader("Status")
                    obra_logada_nome = st.session_state['obra_logada']
                    mes_selecionado_dt = pd.to_datetime(st.session_state.selected_month).date().replace(day=1)
                    status_do_funcionario_row = status_df[
                        (status_df['Obra'] == obra_logada_nome) &
                        (status_df['Funcionario'] == funcionario_selecionado) &
                        (status_df['Mes'] == mes_selecionado_dt)
                    ]

                    status_atual = 'A Revisar'
                    comentario_auditoria = ""
                    if not status_do_funcionario_row.empty:
                        status_atual = status_do_funcionario_row['Status'].iloc[0]
                        comentario_auditoria = status_do_funcionario_row['Comentario'].iloc[0]

                    display_status_box(f"Status de {funcionario_selecionado}", status_atual)
                    
                    comment = ""
                    st.markdown("---")
                    st.subheader("Comentário")
                    if comentario_auditoria and str(comentario_auditoria).strip():
                        st.warning(f"Comentário: {comentario_auditoria}")

                    
                    st.markdown("---")

                st.subheader("Histórico Recente na Obra")
                if not lancamentos_do_mes_df.empty:
                    lancamentos_da_obra = lancamentos_do_mes_df[lancamentos_do_mes_df['Obra'] == st.session_state['obra_logada']]
                    colunas_display = ['Data', 'Funcionário','Disciplina', 'Serviço','Unidade', 'Quantidade','Valor Unitário', 'Valor Parcial', 'Data do Serviço', 'Observação']
                    colunas_existentes = [col for col in colunas_display if col in lancamentos_da_obra.columns]

                    st.dataframe(lancamentos_da_obra.sort_values(by='Data', ascending=False).head(10)[colunas_existentes].style.format({'Valor Unitário': 'R$ {:,.2f}', 'Valor Parcial': 'R$ {:,.2f}'}), use_container_width=True)
                else:
                    st.info("Nenhum lançamento adicionado ainda neste mês.")

   
    elif st.session_state.page == "Gerenciar Funcionários" and st.session_state['role'] == 'admin':
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
                    col_salario.text_input("Salário Base", value=format_currency(salario), disabled=True)
                with st.form("add_funcionario_form", clear_on_submit=True):
                    nome = st.text_input("2. Nome do Funcionário")
                    obra = st.selectbox("3. Alocar na Obra", options=obras_df['NOME DA OBRA'].unique())
                    submitted = st.form_submit_button("Adicionar Funcionário")
                    if submitted:
                        if nome and funcao_selecionada and obra:
                            obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra, 'id'].iloc[0])
                            funcao_id = int(funcoes_df.loc[funcoes_df['FUNÇÃO'] == funcao_selecionada, 'id'].iloc[0])
                            if adicionar_funcionario(engine, nome, funcao_id, obra_id):
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
                    "Selecione o funcionário para remover", 
                    options=sorted(df_para_remover['NOME'].unique()), 
                    index=None, 
                    placeholder="Selecione um funcionário da lista acima..."
                )
                if func_para_remover:
                    if st.button(f"Remover {func_para_remover}", type="primary"):
                        funcionario_id = int(funcionarios_df.loc[funcionarios_df['NOME'] == func_para_remover, 'id'].iloc[0])
                        if remover_funcionario(engine, funcionario_id, func_para_remover):
                            st.success(f"Funcionário '{func_para_remover}' removido com sucesso!")
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
                            funcionarios_df[funcionarios_df['OBRA'] == obra_origem]['NOME'].unique()
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

                        if mudar_funcionario_de_obra(engine, funcionario_id, nova_obra_id, func_para_mudar, obra_destino):
                            st.toast(f"Funcionário '{func_para_mudar}' movido para a obra '{obra_destino}'!", icon="✅")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.warning("Por favor, preencha todos os três campos: obra de origem, funcionário e obra de destino.")
 


    elif st.session_state.page == "Gerenciar Obras" and st.session_state['role'] == 'admin':
        st.header("Gerenciar Obras 🏗️")
        st.subheader("Adicionar Nova Obra")
        with st.form("add_obra", clear_on_submit=True):
            col1, col2 = st.columns(2)
    
            with col1:
                nome_obra = st.text_input("Nome da Nova Obra")
    
            with col2:
                codigo_acesso = st.text_input("Código de Acesso para a Obra")
            submitted = st.form_submit_button("Adicionar Obra")
            if submitted:
                if nome_obra and codigo_acesso: 
                    if adicionar_obra(engine, nome_obra, codigo_acesso):
                        st.success(f"Obra '{nome_obra}' adicionada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.warning("Por favor, insira o nome e o código de acesso da obra.")

        
        st.markdown("---")
        st.subheader("Remover Obra Existente")
        if obras_df.empty:
            st.info("Nenhuma obra cadastrada.")
        else:
            mes_selecionado_dt = pd.to_datetime(st.session_state.selected_month).date().replace(day=1)
            status_do_mes_df = status_df[
                (status_df['Funcionario'] == 'Status Geral da Obra') &
                (status_df['Mes'] == mes_selecionado_dt)
            ]
            df_para_exibir = pd.merge(
                obras_df,
                status_do_mes_df[['obra_id', 'Status']], 
                left_on='id',
                right_on='obra_id',
                how='left'
            )
            df_para_exibir['Status'] = df_para_exibir['Status'].fillna('A Revisar')
            st.dataframe(
                df_para_exibir[['NOME DA OBRA', 'Status']].style.applymap(
                    style_status,
                    subset=['Status']
                ),
                use_container_width=True
            )  
            obra_para_remover = st.selectbox(
                "Selecione a obra para remover", 
                options=obras_df['NOME DA OBRA'].unique(), 
                index=None, 
                placeholder="Selecione..."
            )
            if obra_para_remover:
                st.warning(f"Atenção: Remover uma obra não remove ou realoca os funcionários associados a ela. Certifique-se de que nenhum funcionário esteja alocado em '{obra_para_remover}' antes de continuar.")
                if st.button(f"Remover Obra '{obra_para_remover}'", type="primary"):
                    obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_remover, 'id'].iloc[0])

                    if remover_obra(engine, obra_id, obra_para_remover):
                        st.success(f"Obra '{obra_para_remover}' removida com sucesso!")
                        st.cache_data.clear()
                        st.rerun()


        st.markdown("---")
        st.subheader("Alterar Código de Acesso")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                obra_para_alterar_codigo = st.selectbox(
                    "1. Selecione a Obra",
                    options=obras_df['NOME DA OBRA'].unique(),
                    index=None,
                    placeholder="Selecione..."
                )
            with col2:
                novo_codigo = st.text_input("2. Digite o Novo Código de Acesso", type="password")

            if st.button("Alterar Código", use_container_width=True):
                if obra_para_alterar_codigo and novo_codigo:
                    obra_id = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_para_alterar_codigo, 'id'].iloc[0])
                    if mudar_codigo_acesso_obra(engine, obra_id, novo_codigo, obra_para_alterar_codigo):
                        st.toast(f"Código de acesso da obra '{obra_para_alterar_codigo}' alterado com sucesso!", icon="🔑")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.warning("Por favor, selecione uma obra e digite o novo código.")
                    
    
    elif st.session_state.page == "Resumo da Folha 📊":
        st.header("Resumo da Folha")
        base_para_resumo = funcionarios_df.copy()
        if st.session_state['role'] == 'user':
            base_para_resumo = base_para_resumo[base_para_resumo['OBRA'] == st.session_state['obra_logada']]
            funcionarios_disponiveis = base_para_resumo['NOME'].unique()
            funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s) específico(s):", options=funcionarios_disponiveis, key="resumo_func_user")
            if funcionarios_filtrados:
                base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
        else: 
            filtro_col1, filtro_col2 = st.columns(2)
            with filtro_col1:
                obras_disponiveis = obras_df['NOME DA OBRA'].unique()
                obras_filtradas = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis, key="resumo_obras_admin")
                if obras_filtradas:
                    base_para_resumo = base_para_resumo[base_para_resumo['OBRA'].isin(obras_filtradas)]
            
            with filtro_col2:
                funcionarios_disponiveis = base_para_resumo['NOME'].unique()
                funcionarios_filtrados = st.multiselect("Filtrar por Funcionário(s):", options=funcionarios_disponiveis, key="resumo_func_admin")
                if funcionarios_filtrados:
                    base_para_resumo = base_para_resumo[base_para_resumo['NOME'].isin(funcionarios_filtrados)]
                    
       
        if base_para_resumo.empty:
            st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
        else:
            if not lancamentos_df.empty:
                producao_por_funcionario = lancamentos_do_mes_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
                producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
                resumo_df = pd.merge(base_para_resumo, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            else:
                resumo_df = base_para_resumo.copy()
                resumo_df['PRODUÇÃO (R$)'] = 0
        
            
        if 'Funcionário' in resumo_df.columns:
            resumo_df = resumo_df.drop(columns=['Funcionário'])

        resumo_df.rename(columns={'id': 'funcionario_id'}, inplace=True)
        resumo_df_com_ids = resumo_df 

        mes_selecionado_dt = pd.to_datetime(st.session_state.selected_month).date().replace(day=1)
        status_mes_df = status_df[status_df['Mes'] == mes_selecionado_dt]

        resumo_com_status_df = pd.merge(
            resumo_df_com_ids,
            status_mes_df,
            on=['funcionario_id', 'obra_id'],
            how='left'
        )

        resumo_com_status_df['Status'] = resumo_com_status_df['Status'].fillna('A Revisar')
        resumo_com_status_df['PRODUÇÃO (R$)'] = resumo_com_status_df['PRODUÇÃO (R$)'].fillna(0)
        resumo_final_df = resumo_com_status_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
        resumo_final_df['SALÁRIO A RECEBER (R$)'] = resumo_final_df.apply(calcular_salario_final, axis=1)

        colunas_finais = ['Funcionário', 'FUNÇÃO', 'TIPO', 'SALÁRIO BASE (R$)', 'PRODUÇÃO (R$)', 'SALÁRIO A RECEBER (R$)', 'Status']
        if st.session_state['role'] == 'admin':
            colunas_finais.insert(1, 'OBRA')

        colunas_existentes = [col for col in colunas_finais if col in resumo_final_df.columns]
        resumo_final_df = resumo_final_df[colunas_existentes].reset_index(drop=True)
        
        st.dataframe(
            resumo_final_df.style.format({
                'SALÁRIO BASE (R$)': 'R$ {:,.2f}',
                'PRODUÇÃO (R$)': 'R$ {:,.2f}',
                'SALÁRIO A RECEBER (R$)': 'R$ {:,.2f}'
            }).applymap(
                style_status, subset=['Status']
            ),
            use_container_width=True
        )

    elif st.session_state.page == "Remover Lançamentos 🗑️":
        st.header("Gerenciar Lançamentos")
        
        df_para_editar = lancamentos_do_mes_df.copy()

        if df_para_editar.empty:
            st.info("Não há lançamentos para gerenciar no mês selecionado.")
        else:
            df_filtrado = df_para_editar.copy()

            if st.session_state['role'] == 'user':
                funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
                funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_user")
                if funcionario_filtrado:
                    df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
            else: 
                filtro_col1, filtro_col2 = st.columns(2)
                with filtro_col1:
                    ids_obras_disponiveis = df_filtrado['obra_id'].unique()
                    nomes_obras_disponiveis = sorted(obras_df[obras_df['id'].isin(ids_obras_disponiveis)]['NOME DA OBRA'].unique())
                    obras_filtradas_nomes = st.multiselect("Filtrar por Obra(s):", options=nomes_obras_disponiveis, key="editar_obras_admin")

                    if obras_filtradas_nomes:
                        ids_obras_filtradas = obras_df[obras_df['NOME DA OBRA'].isin(obras_filtradas_nomes)]['id'].tolist()
                        df_filtrado = df_filtrado[df_filtrado['obra_id'].isin(ids_obras_filtradas)]
                    
                with filtro_col2:
                    funcionarios_para_filtrar = sorted(df_filtrado['Funcionário'].unique())
                    funcionario_filtrado = st.multiselect("Filtrar por Funcionário:", options=funcionarios_para_filtrar, key="editar_func_admin")
                    if funcionario_filtrado:
                        df_filtrado = df_filtrado[df_filtrado['Funcionário'].isin(funcionario_filtrado)]
          
            if df_filtrado.empty:
                st.info("Nenhum lançamento encontrado para os filtros selecionados.")
            else:
                df_filtrado['Remover'] = False
            
                colunas_visiveis = [
                    'id', 'Remover', 'Data', 'Obra', 'Funcionário', 'Disciplina', 'Serviço', 
                    'Quantidade', 'Valor Unitário', 'Valor Parcial', 'Observação', 'Data do Serviço'
                ]
                colunas_existentes = [col for col in colunas_visiveis if col in df_filtrado.columns]
            
                st.write("Marque as caixas dos lançamentos que deseja apagar e clique no botão de remoção.")
              
                df_modificado = st.data_editor(
                    df_filtrado[colunas_existentes],
                    hide_index=True,
                    column_config={
                        "id": None, 
                        "Remover": st.column_config.CheckboxColumn(required=True),
                        "Disciplina": st.column_config.TextColumn("Disciplina"),
                        "Valor Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Valor Parcial": st.column_config.NumberColumn(format="R$ %.2f")
                    },
                    disabled=df_filtrado.columns.drop(['Remover'], errors='ignore') 
                )
              
                linhas_para_remover = df_modificado[df_modificado['Remover']]
            
                if not linhas_para_remover.empty:
                    st.warning("Atenção! Você selecionou os seguintes lançamentos para remoção permanente:")
                    st.dataframe(linhas_para_remover.drop(columns=['Remover'], errors='ignore')) 
                
                    razao_remocao = ""
                    if st.session_state['role'] == 'admin':
                        razao_remocao = st.text_area("Justificativa para a remoção (obrigatório):", key="razao_remocao_admin")
 
                    confirmacao_remocao = st.checkbox("Sim, confirmo que desejo remover os itens selecionados.")
                
                    is_disabled = not confirmacao_remocao
                    if st.session_state['role'] == 'admin':
                       is_disabled = not confirmacao_remocao or not razao_remocao.strip()


                    if st.button("Remover Itens Selecionados", ...):
                        ids_a_remover = linhas_para_remover['id'].tolist()
                        if remover_lancamentos_por_id(ids_a_remover, engine, razao_remocao):
                            st.cache_data.clear()
                            st.rerun()
                        if st.session_state['role'] == 'admin' and razao_remocao:
                            funcionarios_afetados = { (row['Obra'], row['Funcionário']) for _, row in linhas_para_remover.iterrows() }

                            for obra, funcionario in funcionarios_afetados:
                                status_df = save_comment_data(status_df, obra, funcionario, razao_remocao, append=True)
                            pass
                        st.cache_data.clear()
                        st.rerun()

    elif st.session_state.page == "Dashboard de Análise 📈":
        st.header("Dashboard de Análise")
        df_para_o_dashboard = lancamentos_do_mes_df.copy()
        if st.session_state['role'] == 'user':
            df_para_o_dashboard = df_para_o_dashboard[df_para_o_dashboard['Obra'] == st.session_state['obra_logada']]
        if df_para_o_dashboard.empty:
            st.info("Ainda não há lançamentos para analisar neste mês ou para a obra selecionada.")
        else:
            st.markdown("#### Filtros Adicionais")
            df_filtrado_dash = df_para_o_dashboard.copy()
            if st.session_state['role'] == 'admin':
                filtro_col1, filtro_col2 = st.columns(2)
                with filtro_col1:
                    obras_disponiveis = sorted(df_filtrado_dash['Obra'].unique())
                    obras_filtradas_dash = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis)
                    if obras_filtradas_dash:
                        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Obra'].isin(obras_filtradas_dash)]
                with filtro_col2:
                    funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
                    funcionarios_filtrados_dash = st.multiselect(
                        "Filtrar por Funcionário(s)", 
                        options=funcionarios_disponiveis, 
                        key="dash_func_admin"
                    )
                    if funcionarios_filtrados_dash:
                        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]

            else: 
                funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
                funcionarios_filtrados_dash = st.multiselect(
                    "Filtrar por Funcionário(s)", 
                    options=funcionarios_disponiveis, 
                    key="dash_func_user"
                )
                if funcionarios_filtrados_dash:
                    df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]

            if df_filtrado_dash.empty:
                st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
            else:
                
                st.markdown("---")
                total_produzido = df_filtrado_dash['Valor Parcial'].sum()
                top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
                top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()
                top_funcionario_display = (top_funcionario[:22] + '...') if len(top_funcionario) > 22 else top_funcionario
                top_servico_display = (top_servico[:22] + '...') if len(top_servico) > 22 else top_servico

                if st.session_state['role'] == 'admin':
                    kpi_cols = st.columns(4)
                    kpi_cols[0].metric("Produção Total", format_currency(total_produzido))
                    top_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().idxmax()
                    kpi_cols[1].metric("Obra Destaque", top_obra)
                    kpi_cols[2].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
                    kpi_cols[3].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)
                else:
                    kpi_cols = st.columns(3)
                    kpi_cols[0].metric("Produção Total", format_currency(total_produzido))
                    kpi_cols[1].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
                    kpi_cols[2].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)

                st.markdown("---")
                cor_padrao = '#E37026'

                if st.session_state['role'] == 'admin':
                    st.subheader("Produção por Obra")
                    prod_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                    fig_bar_obra = px.bar(prod_obra, x='Obra', y='Valor Parcial', text_auto=True, title="Produção Total por Obra",template="plotly_dark")
                    fig_bar_obra.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                    st.plotly_chart(fig_bar_obra, use_container_width=True)
                
                st.subheader("Produção por Funcionário")
                prod_func = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
                fig_bar_func = px.bar(prod_func, x='Funcionário', y='Valor Parcial', text_auto=True, title="Produção Total por Funcionário")
                fig_bar_func.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                st.plotly_chart(fig_bar_func, use_container_width=True)
                
                
                st.markdown("---")
                st.subheader("Produção ao Longo do Tempo")
                col_diag, col_mes = st.columns(2)
                with col_diag:
                    prod_dia = df_filtrado_dash.set_index('Data').resample('D')['Valor Parcial'].sum().reset_index()
                    fig_line = px.line(prod_dia, x='Data', y='Valor Parcial', markers=True, title="Evolução Diária da Produção")
                    fig_line.update_traces(line_color=cor_padrao, marker=dict(color=cor_padrao))
                    st.plotly_chart(fig_line, use_container_width=True)
                with col_mes:
                    prod_mes = df_filtrado_dash.set_index('Data').resample('ME')['Valor Parcial'].sum().reset_index()
                    prod_mes['Mês'] = prod_mes['Data'].dt.strftime('%Y-%m')
                    fig_bar_mes = px.bar(prod_mes, x='Mês', y='Valor Parcial', text_auto=True, title="Produção Total Mensal")
                    fig_bar_mes.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
                    st.plotly_chart(fig_bar_mes, use_container_width=True)
            
                if st.session_state['role'] == 'admin':
                    st.markdown("---")
                    st.subheader("Análise de Serviços")
                    col_freq, col_custo = st.columns(2)

                    with col_freq:
                        serv_freq = df_filtrado_dash['Serviço'].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
                        serv_freq.columns = ['Serviço', 'Contagem']
                        fig_freq = px.bar(serv_freq, y='Serviço', x='Contagem', orientation='h', title="Top 10 Serviços Mais Realizados (Frequência)")
                        fig_freq.update_traces(marker_color=cor_padrao, texttemplate='%{x}', textposition='outside')
                        st.plotly_chart(fig_freq, use_container_width=True)

                    with col_custo:
                        serv_custo = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                        fig_custo = px.bar(serv_custo, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços de Maior Custo Total", text_auto=True)
                        fig_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                        st.plotly_chart(fig_custo, use_container_width=True)
                        
                    st.markdown("---")
                    st.subheader("Análise de Disciplinas")
                    col_disc_freq, col_disc_custo = st.columns(2)
                    with col_disc_freq:
                        disc_freq = df_filtrado_dash['Disciplina'].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
                        disc_freq.columns = ['Disciplina', 'Contagem']
                        fig_disc_freq = px.bar(disc_freq, y='Disciplina', x='Contagem', orientation='h', title="Top 10 Disciplinas Mais Realizadas")
                        fig_disc_freq.update_traces(marker_color=cor_padrao, texttemplate='%{x}', textposition='outside')
                        st.plotly_chart(fig_disc_freq, use_container_width=True)
                    with col_disc_custo:
                        disc_custo = df_filtrado_dash.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                        fig_disc_custo = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas de Maior Custo")
                        fig_disc_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                        st.plotly_chart(fig_disc_custo, use_container_width=True)

                
    elif st.session_state.page == "Auditoria ✏️" and st.session_state['role'] == 'admin':
        st.header(f"Auditoria de Lançamentos - {st.session_state.selected_month}")
        col_filtro1, col_filtro2 = st.columns(2)
        ids_obras_disponiveis = lancamentos_df['obra_id'].unique()
        nomes_obras_disponiveis = sorted(obras_df[obras_df['id'].isin(ids_obras_disponiveis)]['NOME DA OBRA'].unique())
        obra_selecionada = col_filtro1.selectbox("1. Selecione a Obra para auditar", options=nomes_obras_disponiveis, index=None, placeholder="Selecione uma obra...")
        
        funcionarios_filtrados = []
        if obra_selecionada:
            funcionarios_da_obra = sorted(funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]['NOME'].unique())
            funcionarios_filtrados = col_filtro2.multiselect("2. Filtre por Funcionário (Opcional)", options=funcionarios_da_obra)
        
        if obra_selecionada:
            mes_selecionado = st.session_state.selected_month
            mes_selecionado_dt = pd.to_datetime(mes_selecionado).date().replace(day=1)
            lancamentos_obra_df = lancamentos_df[lancamentos_df['Obra'] == obra_selecionada]
            funcionarios_obra_df = funcionarios_df[funcionarios_df['OBRA'] == obra_selecionada]
            
            status_geral_row = status_df[
                (status_df['Obra'] == obra_selecionada) & 
                (status_df['Funcionario'] == 'Status Geral da Obra') & 
                (status_df['Mes'] == mes_selecionado_dt) 
            ]
            status_atual_obra = status_geral_row['Status'].iloc[0] if not status_geral_row.empty else "A Revisar"
            
            folha_lancada_row = folhas_df[(folhas_df['Obra'] == obra_selecionada) & (folhas_df['Mes'] == mes_selecionado_dt)] 
            is_launched = not folha_lancada_row.empty
            

            folha_lancada = is_launched
            edicao_bloqueada = (status_atual_obra == "Aprovado") or folha_lancada
            if folha_lancada:
                st.success(f"✅ A folha para {obra_selecionada} em {mes_selecionado} já foi lançada e arquivada. Nenhuma edição é permitida.")
            elif edicao_bloqueada:
                st.warning(f"🔒 A obra {obra_selecionada} está com status 'Aprovado' para o mês {mes_selecionado}. As edições estão bloqueadas.")

            st.markdown("---")
            col_status_geral, col_aviso_geral = st.columns(2)

            with col_status_geral:
                st.markdown("##### Status e Finalização do Mês")
                display_status_box("Status Geral", status_atual_obra)
                
                with st.popover("Alterar Status", disabled=folha_lancada):
                    todos_aprovados = True
                    nomes_funcionarios_ativos = lancamentos_obra_df['Funcionário'].unique()
                    if len(nomes_funcionarios_ativos) > 0:
                        status_funcionarios_obra = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Mes'] == mes_selecionado_dt)]
                        for nome in nomes_funcionarios_ativos:
                            status_func_row = status_funcionarios_obra[status_funcionarios_obra['Funcionario'] == nome]
                            status_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else 'A Revisar'
                            if status_func != 'Aprovado':
                                todos_aprovados = False
                            break
                
                    status_options = ['A Revisar', 'Analisar']
                    if todos_aprovados:
                        status_options.append('Aprovado')
                    else:
                        st.info("Para aprovar a obra, todos os funcionários COM LANÇAMENTOS no mês devem ter o status 'Aprovado'.")
                    idx = status_options.index(status_atual_obra) if status_atual_obra in status_options else 0
                    selected_status_obra = st.radio("Defina um novo status", options=status_options, index=idx, horizontal=True, key=f"radio_status_obra_{obra_selecionada}")
                    if st.button("Salvar Status da Obra", key=f"btn_obra_{obra_selecionada}"):
                        if selected_status_obra != status_atual_obra:
                            obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
                            if save_geral_status_obra(engine, obra_id_selecionada, selected_status_obra, mes_referencia=mes_selecionado, obra_nome=obra_selecionada):
                                st.cache_data.clear()
                                st.rerun()
                
                is_launch_disabled = (status_atual_obra != 'Aprovado')

                if st.button("Lançar Folha Mensal", 
                             type="primary", 
                             use_container_width=True, 
                             disabled=is_launch_disabled, 
                             help="A obra precisa estar com o status 'Aprovado' para lançar a folha." if is_launch_disabled else ""):
        
                    obra_id_selecionada = obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0]
                    mes_datetime = pd.to_datetime(st.session_state.selected_month)
                    if launch_monthly_sheet(obra_id_selecionada, mes_datetime, obra_selecionada):
                        st.rerun()

                        if is_launch_disabled and not is_launched:
                            st.info("A obra precisa estar com o status 'Aprovado' para que a folha possa ser lançada.")

            with col_aviso_geral:
                st.markdown("##### Aviso Geral da Obra")
                aviso_atual = ""
                if 'Aviso' in obras_df.columns and not obras_df[obras_df['NOME DA OBRA'] == obra_selecionada].empty:
                    aviso_atual = obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'Aviso'].iloc[0]
                
                novo_aviso = st.text_area(
                    "Aviso para a Obra:", value=aviso_atual, key=f"aviso_{obra_selecionada}", label_visibility="collapsed"
                )
                if st.button("Salvar Aviso", key=f"btn_aviso_{obra_selecionada}", disabled=edicao_bloqueada):
                    if save_aviso_data(engine, obra_selecionada, novo_aviso):
                        st.toast("Aviso salvo com sucesso!", icon="✅")
                        st.cache_data.clear()
                        st.rerun()
            
            producao_por_funcionario = lancamentos_obra_df.groupby('Funcionário')['Valor Parcial'].sum().reset_index()
            producao_por_funcionario.rename(columns={'Valor Parcial': 'PRODUÇÃO (R$)'}, inplace=True)
            resumo_df = pd.merge(funcionarios_obra_df, producao_por_funcionario, left_on='NOME', right_on='Funcionário', how='left')
            if 'Funcionário' in resumo_df.columns:
                resumo_df = resumo_df.drop(columns=['Funcionário'])
            if 'PRODUÇÃO (R$)' not in resumo_df.columns:
                resumo_df['PRODUÇÃO (R$)'] = 0
            else:
                resumo_df['PRODUÇÃO (R$)'] = resumo_df['PRODUÇÃO (R$)'].fillna(0)
            resumo_df = resumo_df.rename(columns={'NOME': 'Funcionário', 'SALARIO_BASE': 'SALÁRIO BASE (R$)'})
            resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(calcular_salario_final, axis=1)

            if funcionarios_filtrados:
                resumo_df = resumo_df[resumo_df['Funcionário'].isin(funcionarios_filtrados)]
                duplicatas_encontradas = resumo_df[resumo_df.duplicated(subset=['Funcionário'], keep=False)]
                
            total_producao_obra = resumo_df['PRODUÇÃO (R$)'].sum()
            num_funcionarios = len(resumo_df)

            col1, col2 = st.columns(2)
            col1.metric("Produção Total da Obra", f"R$ {total_producao_obra:,.2f}")
            col2.metric("Nº de Funcionários", num_funcionarios)
        
            st.markdown("---")
            st.subheader("Análise por Funcionário")

            if resumo_df.empty:
                st.warning("Nenhum funcionário encontrado para os filtros selecionados.")
            else:
                for index, row in resumo_df.iterrows():
                    with st.container(border=True):
                        funcionario = row['Funcionário']
                        header_cols = st.columns([3, 2, 2, 2, 2])
                        header_cols[0].markdown(f"**Funcionário:** {row['Funcionário']} ({row['FUNÇÃO']})")
                        header_cols[1].metric("Salário Base", format_currency(row['SALÁRIO BASE (R$)']))
                        header_cols[2].metric("Produção", format_currency(row['PRODUÇÃO (R$)']))
                        header_cols[3].metric("Salário a Receber", format_currency(row['SALÁRIO A RECEBER (R$)']))
                        status_func_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario) & (status_df['Mes'] == mes_selecionado_dt)]
                        status_atual_func = status_func_row['Status'].iloc[0] if not status_func_row.empty else "A Revisar"
                    
                    with header_cols[4]:
                        display_status_box("Status", status_atual_func)

                    with st.expander("Ver Lançamentos, Alterar Status e Editar Observações", expanded=False):
                        col_status, col_comment = st.columns(2)
                        with col_status:
                            st.markdown("##### Status do Funcionário")
                            status_options_func = ['A Revisar', 'Aprovado', 'Analisar']
                            idx_func = status_options_func.index(status_atual_func)
                            selected_status_func = st.radio(
                                "Definir Status:", options=status_options_func, index=idx_func, horizontal=True, 
                                key=f"status_{obra_selecionada}_{funcionario}",
                                disabled=edicao_bloqueada
                            )
                            if st.button("Salvar Status do Funcionário", key=f"btn_func_{obra_selecionada}_{funcionario}", disabled=edicao_bloqueada):
                                if selected_status_func != status_atual_func:
                                    obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
                                    funcionario_id_selecionado = int(funcionarios_df.loc[funcionarios_df['NOME'] == funcionario, 'id'].iloc[0])
                                    if save_status_data(engine, obra_id_selecionada, funcionario_id_selecionado, selected_status_func, mes_referencia=mes_selecionado, func_nome=funcionario, obra_nome=obra_selecionada):
                                        st.cache_data.clear()
                                        st.rerun()
                                    
                        with col_comment:
                            st.markdown("##### Comentário de Auditoria")
                            comment_row = status_df[(status_df['Obra'] == obra_selecionada) & (status_df['Funcionario'] == funcionario) & (status_df['Mes'] == mes_selecionado)]
                            current_comment = ""
                            if not comment_row.empty and 'Comentario' in comment_row.columns:
                                current_comment = str(comment_row['Comentario'].iloc[0])
                            new_comment = st.text_area(
                                "Adicionar/Editar Comentário:", value=current_comment, key=f"comment_{obra_selecionada}_{funcionario}",
                                help="Este comentário será visível na tela de lançamento.", label_visibility="collapsed",
                                disabled=edicao_bloqueada
                            )
                            if st.button("Salvar Comentário", key=f"btn_comment_{obra_selecionada}_{funcionario}", disabled=edicao_bloqueada):
                                obra_id_selecionada = int(obras_df.loc[obras_df['NOME DA OBRA'] == obra_selecionada, 'id'].iloc[0])
                                funcionario_id_selecionado = int(funcionarios_df.loc[funcionarios_df['NOME'] == funcionario, 'id'].iloc[0])
                                if save_comment_data(engine, obra_id_selecionada, funcionario_id_selecionado, new_comment, mes_referencia=mes_selecionado, func_nome=funcionario, obra_nome=obra_selecionada):
                                    st.toast("Comentário salvo com sucesso!", icon="💬")
                                    st.cache_data.clear()
                                    st.rerun()
                                        
                        st.markdown("---")
                        st.markdown("##### Lançamentos e Observações")
                        lancamentos_do_funcionario = lancamentos_obra_df[lancamentos_obra_df['Funcionário'] == funcionario].copy()
                        if lancamentos_do_funcionario.empty:
                            st.info("Nenhum lançamento de produção para este funcionário.")
                        else:
                            colunas_visiveis = [
                                'id', 'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 'Quantidade',
                                'Valor Unitário', 'Valor Parcial', 'Observação'
                            ]
                            colunas_config = {
                                "id": None, 
                                "Data": st.column_config.DatetimeColumn("Data Lançamento", format="DD/MM/YYYY HH:mm"),
                                "Data do Serviço": st.column_config.DateColumn("Data Serviço", format="DD/MM/YYYY"),
                                "Disciplina": st.column_config.TextColumn("Disciplina"),
                                "Serviço": st.column_config.TextColumn("Serviço", width="large"),
                                "Valor Unitário": st.column_config.NumberColumn("V. Unit.", format="R$ %.2f"),
                                "Valor Parcial": st.column_config.NumberColumn("V. Parcial", format="R$ %.2f"),
                                "Observação": st.column_config.TextColumn("Observação (Editável)", width="medium")
                            }
                            colunas_desabilitadas = [
                                'Data', 'Data do Serviço', 'Disciplina', 'Serviço', 
                                'Quantidade', 'Valor Unitário', 'Valor Parcial'
                            ]
                            
                            edited_df = st.data_editor(
                                lancamentos_do_funcionario[colunas_visiveis],
                                key=f"editor_{obra_selecionada}_{funcionario}",
                                hide_index=True,
                                column_config=colunas_config,
                                disabled=colunas_desabilitadas
                            )
                            if not edited_df.equals(lancamentos_do_funcionario[colunas_visiveis]):
                                if st.button("Salvar Alterações nas Observações", key=f"save_obs_{obra_selecionada}_{funcionario}", type="primary", disabled=edicao_bloqueada):
                                    original_obs = lancamentos_do_funcionario.set_index('id')['Observação']
                                    edited_obs = edited_df.set_index('id')['Observação']
                                    alteracoes = edited_obs[original_obs != edited_obs]

                                    if not alteracoes.empty:
                                        updates_list = [
                                            {'id': lanc_id, 'obs': nova_obs}
                                            for lanc_id, nova_obs in alteracoes.items()
                                        ]

                                        if atualizar_observacoes(engine, updates_list):
                                            st.toast("Observações salvas com sucesso!", icon="✅")
                                            st.cache_data.clear()
                                            st.rerun()
                                    else:
                                        st.toast("Nenhuma alteração detectada.", icon="🤷")

