import streamlit as st
import io
import pandas as pd
from datetime import date
import base64

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    HTML = None


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
    """
    Calcula a produção líquida.
    - Para tipo 'PRODUCAO': max(0, bruta - base)
    - Para outros tipos (ex: 'BONUS'): bruta (pois é um adicional)
    """
    salario_base = row.get('SALÁRIO BASE (R$)', 0.0)
    producao_bruta = row.get('PRODUÇÃO BRUTA (R$)', 0.0)
    tipo_contrato = str(row.get('TIPO', '')).upper()

    if tipo_contrato == 'PRODUCAO':
        return max(0.0, producao_bruta - salario_base)
    else: 
        return producao_bruta

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DadosFiltrados')
    processed_data = output.getvalue()
    return processed_data

def format_currency(value):
    try:
        float_value = safe_float(value)
        formatted = f"R$ {float_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except (ValueError, TypeError):
        return str(value)

def safe_float(value):
    if value is None:
        return 0.0
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            s = str(value).replace('R$', '').strip().replace('.', '').replace(',', '.')
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

def gerar_relatorio_pdf(resumo_df, lancamentos_df, logo_path, mes_referencia, obra_nome=None):
    """Gera um PDF com o resumo da folha e os lançamentos."""
    if not WEASYPRINT_AVAILABLE:
        st.error("A biblioteca 'weasyprint' não está instalada. O download do PDF não está disponível.")
        st.warning("Para habilitar o PDF, instale com: pip install weasyprint")
        return None
        
    try:
        with open(logo_path, "rb") as image_file:
            logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        logo_base64 = None
        
    style = """
    @page { size: A4 landscape; margin: 1.5cm; }
    body { font-family: 'Helvetica', sans-serif; font-size: 10px; }
    .header { text-align: center; margin-bottom: 20px; }
    .logo { width: 150px; height: auto; }
    h1 { font-size: 18px; color: #333; }
    h2 { font-size: 14px; color: #555; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 20px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9px; }
    th, td { border: 1px solid #ddd; padding: 4px; text-align: left; word-wrap: break-word; } 
    th { background-color: #f2f2f2; font-weight: bold; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    .currency, .number { text-align: right; }
    td:nth-child(1) { width: 20%; } 
    td:nth-child(2) { width: 10%; } 
    """
    
    resumo_df_html = resumo_df.copy()
    lancamentos_df_html = lancamentos_df.copy()

    currency_cols_resumo = ['SALÁRIO BASE (R$)', 'PRODUÇÃO BRUTA (R$)', 'PRODUÇÃO LÍQUIDA (R$)', 'SALÁRIO A RECEBER (R$)' ]
    for col in currency_cols_resumo:
        if col in resumo_df_html.columns:
            resumo_df_html[col] = resumo_df_html[col].apply(lambda x: f'R$ {safe_float(x):,.2f}'.replace(",", "X").replace(".", ",").replace("X", "."))

    currency_cols_lanc = ['Valor Unitário', 'Valor Parcial']
    number_cols_lanc = ['Quantidade']
    date_cols_lanc = ['Data', 'Data do Serviço']

    for col in currency_cols_lanc:
         if col in lancamentos_df_html.columns:
            lancamentos_df_html[col] = lancamentos_df_html[col].apply(lambda x: f'R$ {safe_float(x):,.2f}'.replace(",", "X").replace(".", ",").replace("X", "."))
    for col in number_cols_lanc:
         if col in lancamentos_df_html.columns:
             lancamentos_df_html[col] = lancamentos_df_html[col].apply(lambda x: f'{safe_float(x):,.2f}'.replace(",", "X").replace(".", ",").replace("X", "."))
    for col in date_cols_lanc:
         if col in lancamentos_df_html.columns:
             try:
                 lancamentos_df_html[col] = pd.to_datetime(lancamentos_df_html[col]).dt.strftime('%d/%m/%Y %H:%M')
             except: 
                  try:
                      lancamentos_df_html[col] = pd.to_datetime(lancamentos_df_html[col]).dt.strftime('%d/%m/%Y')
                  except:
                      pass 

    resumo_html = resumo_df_html.to_html(index=False, na_rep='', classes='table', justify='left', escape=False)
    lancamentos_html = lancamentos_df_html.to_html(index=False, na_rep='', classes='table', justify='left', escape=False)
    
    def add_css_classes_to_td(html_table, df_columns, currency_cols, number_cols):
        try:
            header_row = html_table.split('<thead>')[1].split('</thead>')[0]
        except IndexError:
             return html_table
             
        col_indices = {col: i for i, col in enumerate(df_columns)}
        
        currency_indices = {col_indices[col] for col in currency_cols if col in col_indices}
        number_indices = {col_indices[col] for col in number_cols if col in col_indices}

        try:
            tbody_content = html_table.split('<tbody>')[1].split('</tbody>')[0]
        except IndexError:
             return html_table

        body_rows = tbody_content.split('<tr>')
        new_body_rows = []
        for row_html in body_rows:
            row_html_stripped = row_html.strip()
            if not row_html_stripped or row_html_stripped == '</tr>': continue
            
            cells = row_html.split('<td')
            if len(cells) <= 1: 
                 cells = row_html.split('<th')
                 tag = 'th'
            else:
                 tag = 'td'

            if len(cells) <= 1:
                 new_body_rows.append(row_html)
                 continue

            new_cells = [cells[0]] 
            for i, cell_content in enumerate(cells[1:]):
                if i in currency_indices:
                    new_cells.append(f'<{tag} class="currency"{cell_content}')
                elif i in number_indices:
                    new_cells.append(f'<{tag} class="number"{cell_content}')
                else:
                     new_cells.append(f'<{tag}{cell_content}') 
            new_body_rows.append(''.join(new_cells))
            
        new_tbody = '<tbody>' + '<tr>'.join(new_body_rows) + '</tbody>'
        return html_table.split('<tbody>')[0] + new_tbody + html_table.split('</tbody>')[1]

    resumo_html = add_css_classes_to_td(resumo_html, resumo_df.columns, currency_cols_resumo, [])
    lancamentos_html = add_css_classes_to_td(lancamentos_html, lancamentos_df.columns, currency_cols_lanc, number_cols_lanc)

    html_string = f"""
    <html>
    <head><meta charset="UTF-8"><style>{style}</style></head>
    <body>
        <div class="header">
            {f'<img src="data:image/png;base64,{logo_base64}" class="logo">' if logo_base64 else ''}
            <h1>Relatório de Produção - {mes_referencia}</h1>
            {f'<h2>Obra: {obra_nome}</h2>' if obra_nome else ''}
        </div>
        <h2>Resumo da Folha</h2>
        {resumo_html}
        <h2>Histórico de Lançamentos do Mês</h2>
        {lancamentos_html}
    </body>
    </html>
    """
    try:
        pdf_bytes = HTML(string=html_string).write_pdf()
        return pdf_bytes
    except Exception as e:
         st.error(f"Erro ao gerar PDF com WeasyPrint: {e}")
         st.info("Verifique se as dependências do WeasyPrint (como Pango, Cairo, GDK-PixBuf) estão instaladas corretamente no sistema.")
         return None
