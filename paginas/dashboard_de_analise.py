import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import db_utils
import utils
import numpy as np
from datetime import datetime, date

def apply_theme():
    st.markdown("""
    <style>
    /* Cards KPI */
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 15px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        border-color: #E37026;
        background-color: rgba(227, 112, 38, 0.05);
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #AAA;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #FFF;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #888;
        margin-top: 4px;
    }
    
    /* Plotly Transparente */
    .js-plotly-plot .plotly .main-svg { background: rgba(0,0,0,0) !important; }
    
    /* Admin Section */
    .admin-box {
        border: 1px dashed rgba(227, 112, 38, 0.4);
        background: rgba(227, 112, 38, 0.02);
        border-radius: 10px;
        padding: 15px;
        margin: 20px 0;
    }
    
    hr { border-color: rgba(255,255,255,0.1); }
    </style>
    """, unsafe_allow_html=True)

def style_fig(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E0E0E0', family="Sans Serif"),
        title_font=dict(size=16, color='#FFF'),
        xaxis=dict(showgrid=False, color='#A0A0A0', gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#A0A0A0'),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(bgcolor='rgba(0,0,0,0)'),
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
    st.header(f"Dashboard de Análise - {mes_selecionado}")

    @st.cache_data
    def get_data(mes):
        return db_utils.get_lancamentos_do_mes(mes), db_utils.get_funcionarios(), db_utils.get_folhas_mensais(mes), db_utils.get_obras()

    lancamentos_df, funcionarios_df, folhas_df, obras_df = get_data(mes_selecionado)
    
    if lancamentos_df.empty:
        st.info("Não há lançamentos no mês selecionado.")

    if funcionarios_df.empty:
        st.info("Sem dados de funcionários.")
        return

    lancamentos_df['Valor Parcial'] = pd.to_numeric(lancamentos_df['Valor Parcial'], errors='coerce').fillna(0)
    funcionarios_df['SALARIO_BASE'] = pd.to_numeric(funcionarios_df['SALARIO_BASE'], errors='coerce').fillna(0)
    lancamentos_df['Data do Serviço'] = pd.to_datetime(lancamentos_df['Data do Serviço'])
    
    prod = lancamentos_df[lancamentos_df['Disciplina']!='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'})
    grat = lancamentos_df[lancamentos_df['Disciplina']=='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'})
    
    resumo = funcionarios_df.merge(prod, left_on='id', right_on='funcionario_id', how='left').merge(grat, left_on='id', right_on='funcionario_id', how='left')
    resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']] = resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']].fillna(0)
    resumo['PRODUÇÃO LÍQUIDA (R$)'] = resumo.apply(utils.calcular_producao_liquida, axis=1)
    resumo['Funcionário'] = resumo['NOME']
    resumo['ROI'] = np.where(resumo['SALARIO_BASE']>0, resumo['PRODUÇÃO BRUTA (R$)']/resumo['SALARIO_BASE'], 0)

    with st.expander("Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        obras_disp = sorted(resumo['OBRA'].unique())
        
        def_obras = obras_disp if st.session_state['role'] == 'admin' else [st.session_state['obra_logada']]
        def_obras = [o for o in def_obras if o in obras_disp]
        sel_obras = c1.multiselect("Obra", obras_disp, default=def_obras)
        
        df_f = resumo[resumo['OBRA'].isin(sel_obras)] if sel_obras else resumo
        lancs_f = lancamentos_df[lancamentos_df['Obra'].isin(sel_obras)] if sel_obras else lancamentos_df
        
        sel_func = c2.multiselect("Função", sorted(df_f['FUNÇÃO'].unique()))
        if sel_func: 
            df_f = df_f[df_f['FUNÇÃO'].isin(sel_func)]
            ids = df_f['id'].unique()
            lancs_f = lancs_f[lancs_f['funcionario_id'].isin(ids)]
            
        sel_tipo = c3.multiselect("Tipo", sorted(df_f['TIPO'].unique()))
        if sel_tipo: df_f = df_f[df_f['TIPO'].isin(sel_tipo)]
        
        sel_nome = c4.multiselect("Nome", sorted(df_f['Funcionário'].unique()))
        if sel_nome: df_f = df_f[df_f['Funcionário'].isin(sel_nome)]

    if df_f.empty: st.warning("Sem dados nos filtros."); return

    tot_bruta = df_f['PRODUÇÃO BRUTA (R$)'].sum()
    tot_liq = df_f['PRODUÇÃO LÍQUIDA (R$)'].sum()
    tot_grat = df_f['TOTAL GRATIFICAÇÕES (R$)'].sum()
    med_liq = df_f['PRODUÇÃO LÍQUIDA (R$)'].mean()
    
    destaque_nome = "N/A"
    if tot_bruta > 0:
        destaque_nome = df_f.loc[df_f['PRODUÇÃO BRUTA (R$)'].idxmax(), 'Funcionário'].split()[0]

    col_kpi = st.columns(5)
    with col_kpi[0]: st.markdown(kpi_html("Prod. Bruta Total", utils.format_currency(tot_bruta), "", "#E37026"), unsafe_allow_html=True)
    with col_kpi[1]: st.markdown(kpi_html("Prod. Líquida Total", utils.format_currency(tot_liq), "", "#1E88E5"), unsafe_allow_html=True)
    with col_kpi[2]: st.markdown(kpi_html("Total Gratificações", utils.format_currency(tot_grat), "", "#8b5cf6"), unsafe_allow_html=True)
    with col_kpi[3]: st.markdown(kpi_html("Média Líq./Func.", utils.format_currency(med_liq), "", "#328c11"), unsafe_allow_html=True)
    with col_kpi[4]: st.markdown(kpi_html("Maior Produtividade", destaque_nome, "",  "#FFFFFF"), unsafe_allow_html=True)

   
    try:
        dias_com_dados = lancs_f['Data do Serviço'].dt.date.nunique()
        ultimo_dia = lancs_f['Data do Serviço'].max().day if not lancs_f.empty else 1
        projecao = (tot_bruta / ultimo_dia) * 30 if ultimo_dia > 0 else 0
        media_diaria = tot_bruta / dias_com_dados if dias_com_dados > 0 else 0
        equipe_ativa = df_f[df_f['PRODUÇÃO BRUTA (R$)'] > 0]['id'].count()
        total_equipe = df_f['id'].count()
        
        recorde_dia = 0
        data_recorde = "-"
        if not lancs_f.empty:
            daily_sum = lancs_f.groupby(lancs_f['Data do Serviço'].dt.date)['Valor Parcial'].sum()
            recorde_dia = daily_sum.max()
            data_recorde = daily_sum.idxmax().strftime('%d/%m')

        st.markdown(" ") 
        col_op = st.columns(4)
        with col_op[0]: st.markdown(kpi_html("Projeção (Mês)", utils.format_currency(projecao), f"Baseado em {ultimo_dia} dias", "#FFFFFF"), unsafe_allow_html=True)
        with col_op[1]: st.markdown(kpi_html("Média Diária", utils.format_currency(media_diaria), "Ritmo atual", "#328c11"), unsafe_allow_html=True)
        with col_op[2]: st.markdown(kpi_html("Recorde Diário", utils.format_currency(recorde_dia), f"Em {data_recorde}", "#328c11"), unsafe_allow_html=True)
        with col_op[3]: st.markdown(kpi_html("Equipe Ativa", f"{equipe_ativa}/{total_equipe}", "Funcionários produzindo", "#FFFFFF"), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao calcular KPIs operacionais: {e}")

    if st.session_state['role'] == 'admin':
        st.markdown(" ") 
        top_obra = df_f.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().idxmax() if not df_f.empty and tot_bruta > 0 else "N/A"
        top_efic = df_f.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().idxmax() if not df_f.empty else "N/A"
        
        lancs_prod = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO']
        top_serv = lancs_prod.groupby('Serviço')['Valor Parcial'].sum().idxmax() if not lancs_prod.empty else "N/A"
        if len(str(top_serv)) > 20: top_serv = str(top_serv)[:20] + "..."

        ak1, ak2, ak3, ak4 = st.columns(4)
        with ak1: st.markdown(kpi_html("Maior Obra (Volume)", top_obra, "", "#FFFFFF"), unsafe_allow_html=True)
        with ak2: st.markdown(kpi_html("Obra Mais Eficiente", top_efic, "", "#FFFFFF"), unsafe_allow_html=True)
        with ak3: st.markdown(kpi_html("Serviço Mais Caro", top_serv, "", "#FFFFFF"), unsafe_allow_html=True)
        with ak4: st.markdown(kpi_html("Ticket Médio/Serviço", utils.format_currency(lancs_prod['Valor Parcial'].mean() if not lancs_prod.empty else 0), "", "#328c11"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    cor_bruta = '#E37026'
    cor_liquida = '#1E88E5'

    if st.session_state['role'] == 'admin' and sel_obras: 
        st.markdown("---")
        st.subheader("Comparativo de Obras")
        c_o1, c_o2 = st.columns(2)
        with c_o1:
            g_obr_b = df_f.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values('PRODUÇÃO BRUTA (R$)', ascending=False)
            fig = px.bar(g_obr_b, x='OBRA', y='PRODUÇÃO BRUTA (R$)', text_auto='.2s', title="Total Bruto por Obra")
            fig.update_traces(marker_color=cor_bruta, textposition='outside')
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with c_o2:
            g_obr_l = df_f.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().reset_index().sort_values('PRODUÇÃO LÍQUIDA (R$)', ascending=False)
            fig = px.bar(g_obr_l, x='OBRA', y='PRODUÇÃO LÍQUIDA (R$)', text_auto='.2f', title="Média Líquida por Funcionário")
            fig.update_traces(marker_color=cor_liquida, textposition='outside')
            st.plotly_chart(style_fig(fig), use_container_width=True)

    st.markdown("---")
    st.subheader("Performance Individual")
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        top_b = df_f.nlargest(15, 'PRODUÇÃO BRUTA (R$)')
        fig = px.bar(top_b, x='Funcionário', y='PRODUÇÃO BRUTA (R$)', text_auto='.2s', title="Top 15 - Produção Bruta")
        fig.update_traces(marker_color=cor_bruta, textposition='outside')
        st.plotly_chart(style_fig(fig), use_container_width=True)
    with c_f2:
        top_l = df_f.nlargest(15, 'PRODUÇÃO LÍQUIDA (R$)')
        fig = px.bar(top_l, x='Funcionário', y='PRODUÇÃO LÍQUIDA (R$)', text_auto='.2s', title="Top 15 - Produção Líquida")
        fig.update_traces(marker_color=cor_liquida, textposition='outside')
        st.plotly_chart(style_fig(fig), use_container_width=True)

    st.markdown("---")
    st.subheader("Distribuição")
    fig_hist = px.histogram(df_f, x="PRODUÇÃO LÍQUIDA (R$)", nbins=20, title="Distribuição de Prod. Líquida", color_discrete_sequence=[cor_liquida], text_auto=True)
    fig_hist.update_layout(bargap=0.1)
    st.plotly_chart(style_fig(fig_hist), use_container_width=True)

    st.markdown("---")
    st.subheader("Análise Avançada")
    
    c_adv1, c_adv2 = st.columns(2)
    with c_adv1:
        fig_box = px.box(df_f[df_f['PRODUÇÃO BRUTA (R$)']>0], x='FUNÇÃO', y='PRODUÇÃO BRUTA (R$)', color='FUNÇÃO', title="Consistência das Equipes")
        fig_box.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig_box), use_container_width=True)
    
    with c_adv2:
        fig_scat = px.scatter(df_f[df_f['PRODUÇÃO BRUTA (R$)']>0], x='SALARIO_BASE', y='PRODUÇÃO BRUTA (R$)', 
                              size='ROI', color='FUNÇÃO', hover_name='Funcionário',
                              title="Matriz Custo (Base) x Benefício (Produção)")
        st.plotly_chart(style_fig(fig_scat), use_container_width=True)

    st.markdown("---")
    st.subheader("Detalhamento de Custos")
    c_det1, c_det2 = st.columns(2)
    
    with c_det1:
        if not lancs_f.empty:
            st.markdown("##### Curva ABC de Serviços (Pareto)")
            pareto = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO'].groupby('Serviço')['Valor Parcial'].sum().reset_index().sort_values('Valor Parcial', ascending=False)
            pareto['Acum'] = pareto['Valor Parcial'].cumsum() / pareto['Valor Parcial'].sum() * 100
            
            pareto = pareto.head(15)
            
            pareto['Serviço_Visual'] = pareto['Serviço'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)

            fig_par = go.Figure()
            fig_par.add_trace(go.Bar(x=pareto['Serviço_Visual'], y=pareto['Valor Parcial'], name='Valor (R$)', marker_color=cor_bruta))
            
            fig_par.add_trace(go.Scatter(x=pareto['Serviço_Visual'], y=pareto['Acum'], name='Acumulado %', yaxis='y2', mode='lines+markers', line=dict(color=cor_liquida)))
            
            fig_par.update_layout(
                yaxis2=dict(overlaying='y', side='right', range=[0, 110], showgrid=False), 
                showlegend=False, 
                xaxis=dict(tickangle=-45)
            )
            st.plotly_chart(style_fig(fig_par), use_container_width=True)
    with c_det2:
        lancs_hier = lancs_f[(lancs_f['Disciplina']!='GRATIFICAÇÃO') & (lancs_f['Valor Parcial'] > 50)]
        if not lancs_hier.empty:
            fig_sun = px.sunburst(lancs_hier, path=['Obra', 'Disciplina', 'Serviço'], values='Valor Parcial', color='Valor Parcial', color_continuous_scale='Oranges', title="Hierarquia (Sunburst)")
            st.plotly_chart(style_fig(fig_sun), use_container_width=True)

    st.markdown("---")
    st.subheader("Evolução Temporal")
    c_t1, c_t2 = st.columns([2,1])
    with c_t1:
        lancs_f['Data do Serviço'] = pd.to_datetime(lancs_f['Data do Serviço'])
        evo = lancs_f.groupby(lancs_f['Data do Serviço'].dt.date)['Valor Parcial'].sum().reset_index()
        fig_line = px.line(evo, x='Data do Serviço', y='Valor Parcial', markers=True, title="Produção Diária")
        fig_line.update_traces(line_color=cor_bruta)
        st.plotly_chart(style_fig(fig_line), use_container_width=True)
    
    with c_t2:
        lancs_f['Dia'] = lancs_f['Data do Serviço'].dt.day
        heat_df = pd.merge(lancs_f[['Dia', 'funcionario_id', 'Valor Parcial']], funcionarios_df[['id', 'FUNÇÃO']], left_on='funcionario_id', right_on='id')
        piv = heat_df.pivot_table(index='FUNÇÃO', columns='Dia', values='Valor Parcial', aggfunc='sum').fillna(0)
        if not piv.empty:
            fig_heat = px.imshow(piv, aspect='auto', color_continuous_scale='magma', title="Mapa de Calor (Dia x Função)")
            fig_heat.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig_heat), use_container_width=True)

    if st.session_state['role'] == 'admin':
        st.markdown("---")
        st.subheader("Detalhes e Prazos")
        
        c_d1, c_d2 = st.columns(2)
        lancs_prod = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO']
        if not lancs_prod.empty:
            with c_d1:
                top_s = lancs_prod.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig = px.bar(top_s, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços (Custo)", text_auto='.2s')
                fig.update_traces(marker_color=cor_bruta, textposition='outside')
                st.plotly_chart(style_fig(fig), use_container_width=True)
            with c_d2:
                top_d = lancs_prod.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig = px.bar(top_d, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas (Custo)", text_auto='.2s')
                fig.update_traces(marker_color=cor_bruta, textposition='outside')
                st.plotly_chart(style_fig(fig), use_container_width=True)

        if not folhas_df.empty:
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                folhas_env = folhas_df[folhas_df['data_lancamento'].notna()].copy()
                if not folhas_env.empty and sel_obras: folhas_env = folhas_env[folhas_env['Obra'].isin(sel_obras)]
                
                if not folhas_env.empty:
                    folhas_env['dt_envio'] = pd.to_datetime(folhas_env['data_lancamento'])
                    folhas_env['limite'] = pd.to_datetime(folhas_env['Mes']).apply(lambda x: x.replace(day=23) if pd.notna(x) else pd.NaT)
                    
                    def calc_delay(row):
                        try:
                            if pd.isna(row['limite']) or pd.isna(row['dt_envio']): return 0
                            d_env = row['dt_envio'].date()
                            d_lim = row['limite'].date()
                            if d_env > d_lim: return (d_env - d_lim).days
                            return 0
                        except: return 0

                    folhas_env['atraso'] = folhas_env.apply(calc_delay, axis=1)
                    
                    atraso_med = folhas_env.groupby('Obra')['atraso'].mean().reset_index()
                    fig = px.bar(atraso_med, x='Obra', y='atraso', title="Dias de Atraso (Média)", text_auto=True)
                    fig.update_traces(marker_color='#ef4444', textposition='outside')
                    st.plotly_chart(style_fig(fig), use_container_width=True)
                else: st.info("Sem dados de envio para cálculo de atraso.")
            
            with c_p2:
                folhas_count = folhas_df.copy()
                if sel_obras: folhas_count = folhas_count[folhas_count['Obra'].isin(sel_obras)]
                if not folhas_count.empty:
                    env_count = folhas_count.groupby('Obra')['contador_envios'].sum().reset_index()
                    fig = px.bar(env_count, x='Obra', y='contador_envios', title="Total de Envios/Revisões", text_auto=True)
                    fig.update_traces(marker_color=cor_bruta, textposition='outside')
                    st.plotly_chart(style_fig(fig), use_container_width=True)
