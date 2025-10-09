import streamlit as st
import io
import pandas as pd

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
