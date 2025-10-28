import streamlit as st
import io
import pandas as pd
from datetime import date

def calcular_salario_final(row):
    """Calcula o salário final a receber."""
    salario_base = row.get('SALÁRIO BASE (R$)', 0.0)
    producao_bruta = row.get('PRODUÇÃO BRUTA (R$)', 0.0)
    tipo_contrato = str(row.get('TIPO', '')).upper()

    if tipo_contrato == 'PRODUCAO':
        return max(salario_base, producao_bruta)
    else:
        return salario_base + producao_bruta

def calcular_producao_liquida(row):
    """Calcula a produção líquida (bruta - base), mínimo zero."""
    salario_base = row.get('SALÁRIO BASE (R$)', 0.0)
    producao_bruta = row.get('PRODUÇÃO BRUTA (R$)', 0.0)
    return max(0.0, producao_bruta - salario_base)

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DadosFiltrados')
    processed_data = output.getvalue()
    return processed_data

def format_currency(value):
    try:
        float_value = safe_float(value)
        return f"R$ {float_value:,.2f}"
    except (ValueError, TypeError):
        return str(value) 
def safe_float(value):
    if value is None:
        return 0.0
    try:
        s = str(value).replace('R$', '').strip()
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            s = s.replace('.', '').replace(',', '.')
            return float(s) if s else 0.0
        else:
            return 0.0
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


def style_situacao(situacao):
    """Retorna o estilo CSS para a coluna Situação Lançamento."""
    if situacao == 'Concluído':
        return 'color: green; font-weight: bold;'
    else:
        return 'color: gray; font-style: italic;'
