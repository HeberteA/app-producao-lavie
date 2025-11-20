import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import db_utils
import utils
import numpy as np

def apply_theme():
    st.markdown("""
    <style>
    /* Cards KPI Estilizados */
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .kpi-card:hover {
        transform: translateY(-5px);
        border-color: #E37026;
        background-color: rgba(227, 112, 38, 0.05);
    }
    .kpi-label {
        font-size: 0.85rem;
        color: #A0A0A0;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #FFFFFF;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #666;
        margin-top: 5px;
    }
    
    /* Reset do Plotly para transparência */
    .js-plotly-plot .plotly .main-svg { background: rgba(0,0,0,0) !important; }
    
    /* Ajustes gerais */
    hr { border-color: rgba(255,255,255,0.1); }
    .stExpander { border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

def style_fig(fig):
    """Aplica o estilo dark/transparente a todos os gráficos Plotly"""
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0', family="Sans Serif"),
        title_font=dict(size=16, color='#FFF'),
        xaxis=dict(showgrid=False, color='#A0A0A0', gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#A0A0A0'),
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
        hoverlabel=dict(bgcolor="#333", font_size=12)
    )
    return fig

def kpi_html(label, value, subtext="", color="#E37026"):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color}">{value}</div>
        <div class="kpi-sub">{subtext}</div>
    </div>
    """

def render_page():
    apply_theme()
    
    mes_selecionado = st.session_state.selected_month
    st.header(f"Analytics Avançado - {mes_selecionado}")

    @st.cache_data
    def load_data(mes):
        lancs = db_utils.get_lancamentos_do_mes(mes)
        funcs = db_utils.get_funcionarios()
        return lancs, funcs

    lancamentos_df, funcionarios_df = load_data(mes_selecionado)

    if lancamentos_df.empty:
        st.info("⚠️ Sem dados de lançamentos para gerar análises neste mês.")
        return

    lancamentos_df['Valor Parcial'] = pd.to_numeric(lancamentos_df['Valor Parcial'], errors='coerce').fillna(0)
    lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'])
    if not funcionarios_df.empty:
        funcionarios_df['SALARIO_BASE'] = pd.to_numeric(funcionarios_df['SALARIO_BASE'], errors='coerce').fillna(0)

    with st.expander("Filtros de Escopo (Obra / Função)", expanded=False):
        col_f1, col_f2 = st.columns(2)
        
        obras_disp = sorted(lancamentos_df['Obra'].dropna().unique())
        default_obras = obras_disp if st.session_state.get('role') == 'admin' else [st.session_state.get('obra_logada')]
        default_obras = [o for o in default_obras if o in obras_disp]
        
        sel_obra = col_f1.multiselect("Filtrar Obras", obras_disp, default=default_obras)
        
        if sel_obra:
            lancamentos_df = lancamentos_df[lancamentos_df['Obra'].isin(sel_obra)]
            funcionarios_df = funcionarios_df[funcionarios_df['OBRA'].isin(sel_obra)]
            
        if not funcionarios_df.empty:
            funcoes_disp = sorted(funcionarios_df['FUNÇÃO'].unique())
            sel_funcao = col_f2.multiselect("Filtrar Funções", funcoes_disp)
            if sel_funcao:
                funcionarios_df = funcionarios_df[funcionarios_df['FUNÇÃO'].isin(sel_funcao)]
                ids_filtrados = funcionarios_df['id'].unique()
                lancamentos_df = lancamentos_df[lancamentos_df['funcionario_id'].isin(ids_filtrados)]

    prod_por_func = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
    prod_por_func.columns = ['id', 'Producao_Bruta']
    
    df_performance = pd.merge(funcionarios_df, prod_por_func, on='id', how='left').fillna(0)
    
    df_performance['ROI_Index'] = np.where(
        df_performance['SALARIO_BASE'] > 0, 
        df_performance['Producao_Bruta'] / df_performance['SALARIO_BASE'], 
        0
    )

    total_prod = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']['Valor Parcial'].sum()
    total_grat = lancamentos_df[lancamentos_df['Disciplina'] == 'GRATIFICAÇÃO']['Valor Parcial'].sum()
    ticket_medio = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']['Valor Parcial'].mean()
    roi_medio_global = df_performance[df_performance['Producao_Bruta'] > 0]['ROI_Index'].mean() if not df_performance.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(kpi_html("Produção Total", utils.format_currency(total_prod), "Valor agregado bruto"), unsafe_allow_html=True)
    with c2: st.markdown(kpi_html("Gratificações", utils.format_currency(total_grat), f"{0 if total_prod==0 else (total_grat/total_prod*100):.1f}% sobre produção", color="#8b5cf6"), unsafe_allow_html=True)
    with c3: st.markdown(kpi_html("Eficiência (ROI)", f"{roi_medio_global:.2f}x", "Produção ÷ Salário Base", color="#10b981"), unsafe_allow_html=True)
    with c4: st.markdown(kpi_html("Ticket Médio", utils.format_currency(ticket_medio), "Média por Lançamento"), unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("Performance e Variabilidade de Equipes")
    
    col_stat1, col_stat2 = st.columns([6, 4])
    
    with col_stat1:
        if not df_performance.empty and df_performance['Producao_Bruta'].sum() > 0:
            fig_box = px.box(
                df_performance[df_performance['Producao_Bruta'] > 0], 
                x='FUNÇÃO', 
                y='Producao_Bruta',
                points="all", 
                color='FUNÇÃO',
                title="Dispersão de Produtividade por Função",
                labels={'Producao_Bruta': 'Produção Acumulada (R$)'}
            )
            fig_box.update_layout(showlegend=False)
            style_fig(fig_box)
            st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("Dados insuficientes para Boxplot.")

    with col_stat2:
        if not df_performance.empty and df_performance['Producao_Bruta'].sum() > 0:
            fig_scatter = px.scatter(
                df_performance[df_performance['Producao_Bruta'] > 0],
                x='SALARIO_BASE',
                y='Producao_Bruta',
                color='FUNÇÃO',
                hover_name='NOME',
                size='ROI_Index', 
                title="Matriz Custo (Salário) x Benefício",
                labels={'SALARIO_BASE': 'Salário Base', 'Producao_Bruta': 'Produção'}
            )
            max_axis = max(df_performance['Producao_Bruta'].max(), df_performance['SALARIO_BASE'].max())
            fig_scatter.add_shape(type="line", x0=0, y0=0, x1=max_axis, y1=max_axis, line=dict(color="rgba(255,255,255,0.3)", dash="dash"))
            style_fig(fig_scatter)
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Dados insuficientes para Matriz.")

    st.markdown("---")

    st.subheader("Composição de Custos e Curva ABC")
    
    col_eng1, col_eng2 = st.columns(2)
    
    with col_eng1:
        df_servicos = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']
        if not df_servicos.empty:
            pareto_data = df_servicos.groupby('Serviço')['Valor Parcial'].sum().reset_index().sort_values('Valor Parcial', ascending=False)
            pareto_data['Acumulado'] = pareto_data['Valor Parcial'].cumsum() / pareto_data['Valor Parcial'].sum() * 100
            
            pareto_view = pareto_data.head(12)
            
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(
                x=pareto_view['Serviço'], y=pareto_view['Valor Parcial'],
                name='Valor (R$)', marker_color='#E37026'
            ))
            fig_pareto.add_trace(go.Scatter(
                x=pareto_view['Serviço'], y=pareto_view['Acumulado'],
                name='Acumulado %', yaxis='y2', mode='lines+markers', line=dict(color='#1E88E5', width=2)
            ))
            
            fig_pareto.update_layout(
                title="Pareto: Top Serviços (Curva ABC)",
                yaxis2=dict(overlaying='y', side='right', range=[0, 110], showgrid=False),
                showlegend=False
            )
            style_fig(fig_pareto)
            st.plotly_chart(fig_pareto, use_container_width=True)
        else:
            st.info("Sem dados de serviços.")

    with col_eng2:
        df_sun = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']
        if not df_sun.empty:
            df_sun_grouped = df_sun.groupby(['Obra', 'Disciplina', 'Serviço'])['Valor Parcial'].sum().reset_index()
            df_sun_grouped = df_sun_grouped[df_sun_grouped['Valor Parcial'] > 50]
            
            fig_sun = px.sunburst(
                df_sun_grouped,
                path=['Obra', 'Disciplina', 'Serviço'],
                values='Valor Parcial',
                color='Valor Parcial',
                color_continuous_scale='Oranges',
                title="Drill-down de Custos (Hierarquia)"
            )
            style_fig(fig_sun)
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.info("Dados insuficientes para hierarquia.")

    st.markdown("---")

    st.subheader("Evolução Temporal")
    
    col_time1, col_time2 = st.columns([2, 1])
    
    with col_time1:
        df_dia = lancamentos_df.groupby(lancamentos_df['Data do Serviço'].dt.date)['Valor Parcial'].sum().reset_index()
        if not df_dia.empty:
            fig_line = px.line(
                df_dia, x='Data do Serviço', y='Valor Parcial',
                markers=True, title="Evolução Diária da Produção",
                labels={'Valor Parcial': 'R$'}
            )
            fig_line.update_traces(line_color='#E37026', marker=dict(size=6))
            style_fig(fig_line)
            st.plotly_chart(fig_line, use_container_width=True)
    
    with col_time2:
        if not df_performance.empty:
            lancamentos_df['Dia'] = lancamentos_df['Data do Serviço'].dt.day
            df_heat = pd.merge(lancamentos_df[['Dia', 'funcionario_id', 'Valor Parcial']], funcionarios_df[['id', 'FUNÇÃO']], left_on='funcionario_id', right_on='id')
            
            pivot = df_heat.pivot_table(index='FUNÇÃO', columns='Dia', values='Valor Parcial', aggfunc='sum').fillna(0)
            
            if not pivot.empty:
                fig_heat = px.imshow(
                    pivot,
                    labels=dict(x="Dia", y="Função", color="R$"),
                    color_continuous_scale="magma",
                    title="Mapa de Calor: Intensidade",
                    aspect="auto"
                )
                fig_heat.update_layout(coloraxis_showscale=False)
                style_fig(fig_heat)
                st.plotly_chart(fig_heat, use_container_width=True)
