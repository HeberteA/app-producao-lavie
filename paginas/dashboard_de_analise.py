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
    .js-plotly-plot .plotly .main-svg { background: rgba(0,0,0,0) !important; }
    button[data-baseweb="tab"] {
        font-size: 16px;
        font-weight: 600;
    }
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
        margin=dict(l=20, r=50, t=40, b=20),
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
    
    st.header("Dashboard de Análise")
    
    folhas_historico = db_utils.get_folhas_mensais()
    
    opcoes_meses_reais = []
    if not folhas_historico.empty:
        folhas_historico['Mes'] = pd.to_datetime(folhas_historico['Mes'])
        opcoes_meses_reais = sorted(folhas_historico['Mes'].dt.strftime('%Y-%m').unique(), reverse=True)
    
    mes_atual = datetime.now().strftime('%Y-%m')
    if mes_atual not in opcoes_meses_reais:
        opcoes_meses_reais.insert(0, mes_atual)
    
    opcoes_multiselect = ["Todos"] + opcoes_meses_reais
    
    default_mes = [mes_atual] if mes_atual in opcoes_multiselect else ["Todos"]
    if 'selected_month' in st.session_state and st.session_state.selected_month in opcoes_multiselect:
        default_mes = [st.session_state.selected_month]

    with st.expander("Filtros Gerais", expanded=True):
        c_mes, c_obra, c_func, c_nome = st.columns(4)
        
        sel_meses_brutos = c_mes.multiselect("Períodos", opcoes_multiselect, default=default_mes)
        
        meses_para_consulta = []
        is_periodo_composto = False 
        
        if not sel_meses_brutos or "Todos" in sel_meses_brutos:
            meses_para_consulta = opcoes_meses_reais
            is_periodo_composto = True
            texto_periodo = "Todo o Histórico"
        else:
            meses_para_consulta = sel_meses_brutos
            is_periodo_composto = len(meses_para_consulta) > 1
            texto_periodo = ", ".join(meses_para_consulta)

        @st.cache_data
        def get_data_multi(lista_meses):
            dfs_lanc = []
            dfs_folha = []
            for m in lista_meses:
                l = db_utils.get_lancamentos_do_mes(m)
                f = db_utils.get_folhas_mensais(m)
                if not l.empty: dfs_lanc.append(l)
                if not f.empty: dfs_folha.append(f)
            
            lanc_final = pd.concat(dfs_lanc, ignore_index=True) if dfs_lanc else pd.DataFrame()
            folha_final = pd.concat(dfs_folha, ignore_index=True) if dfs_folha else pd.DataFrame()
            return lanc_final, folha_final

        funcionarios_df = db_utils.get_funcionarios()
        
        lancamentos_df, folhas_df = get_data_multi(meses_para_consulta)

        if not lancamentos_df.empty:
            obras_disp = sorted(lancamentos_df['Obra'].unique())
        else:
            obras_disp = []

        def_obras = obras_disp if st.session_state['role'] == 'admin' else [st.session_state['obra_logada']]
        def_obras = [o for o in def_obras if o in obras_disp]
        sel_obras = c_obra.multiselect("Obra", obras_disp, default=def_obras)
        
        lancs_f = lancamentos_df.copy()
        if sel_obras and not lancs_f.empty:
            lancs_f = lancs_f[lancs_f['Obra'].isin(sel_obras)]

        funcoes_disp = []
        if not funcionarios_df.empty:
            funcoes_disp = sorted(funcionarios_df['FUNÇÃO'].unique())
            
        sel_func = c_func.multiselect("Função", funcoes_disp)
        
        nomes_disp = []
        if not funcionarios_df.empty:
             nomes_disp = sorted(funcionarios_df['NOME'].unique())
        sel_nome = c_nome.multiselect("Nome", nomes_disp)

    if lancs_f.empty:
        st.warning(f"Sem lançamentos encontrados para: {texto_periodo}")
        return

    lancs_f['Valor Parcial'] = pd.to_numeric(lancs_f['Valor Parcial'], errors='coerce').fillna(0)
    lancs_f.rename(columns={'data_servico': 'Data do Serviço'}, inplace=True)
    lancs_f['Data do Serviço'] = pd.to_datetime(lancs_f['Data do Serviço'])

    funcionarios_df['SALARIO_BASE'] = pd.to_numeric(funcionarios_df['SALARIO_BASE'], errors='coerce').fillna(0)
    
    prod = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'})
    grat = lancs_f[lancs_f['Disciplina']=='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'})
    
    resumo = funcionarios_df.merge(prod, left_on='id', right_on='funcionario_id', how='left').merge(grat, left_on='id', right_on='funcionario_id', how='left')
    resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']] = resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']].fillna(0)
    
    df_f = resumo.copy()
    if sel_obras: df_f = df_f[df_f['OBRA'].isin(sel_obras)]
    if sel_func: df_f = df_f[df_f['FUNÇÃO'].isin(sel_func)]
    if sel_nome: df_f = df_f[df_f['NOME'].isin(sel_nome)]
    
    ids_validos = df_f['id'].unique()
    lancs_f = lancs_f[lancs_f['funcionario_id'].isin(ids_validos)]

    resumo['PRODUÇÃO LÍQUIDA (R$)'] = resumo.apply(utils.calcular_producao_liquida, axis=1)
    resumo['Funcionário'] = resumo['NOME']

    if df_f.empty: st.warning("Sem dados nos filtros selecionados."); return

    st.caption(f"Analisando dados de: {texto_periodo}")

    cor_bruta = '#E37026'
    cor_liquida = '#1E88E5'

    tab_list = ["Visão Geral", "Performance", "Análise Profunda", "Evolução"]
    if st.session_state['role'] == 'admin':
        tab_list.append("Administrativo")
    
    tabs = st.tabs(tab_list)

    with tabs[0]:
        st.subheader("Resumo do Período")
        
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

        st.subheader("Indicadores Operacionais")
        try:
            dias_com_dados = lancs_f['Data do Serviço'].dt.date.nunique()
            ultimo_dia = lancs_f['Data do Serviço'].max().day if not lancs_f.empty else 1
            
            projecao_val = 0
            projecao_txt = "N/A para Geral"
            if not is_periodo_composto:
                projecao_val = (tot_bruta / ultimo_dia) * 30 if ultimo_dia > 0 else 0
                projecao_txt = f"Baseado em {ultimo_dia} dias"

            media_diaria = tot_bruta / dias_com_dados if dias_com_dados > 0 else 0
            equipe_ativa = df_f[df_f['PRODUÇÃO BRUTA (R$)'] > 0]['id'].count()
            total_equipe = df_f['id'].count()
            
            recorde_dia = 0
            data_recorde = "-"
            if not lancs_f.empty:
                daily_sum = lancs_f.groupby(lancs_f['Data do Serviço'].dt.date)['Valor Parcial'].sum()
                recorde_dia = daily_sum.max()
                data_recorde = daily_sum.idxmax().strftime('%d/%m')

            col_op = st.columns(4)
            with col_op[0]: 
                if not is_periodo_composto:
                    st.markdown(kpi_html("Projeção (Mês)", utils.format_currency(projecao_val), projecao_txt, "#FFFFFF"), unsafe_allow_html=True)
                else:
                    st.markdown(kpi_html("Dias Trabalhados", str(dias_com_dados), "Total no período", "#FFFFFF"), unsafe_allow_html=True)
                    
            with col_op[1]: st.markdown(kpi_html("Média Diária", utils.format_currency(media_diaria), "Ritmo atual", "#328c11"), unsafe_allow_html=True)
            with col_op[2]: st.markdown(kpi_html("Recorde Diário", utils.format_currency(recorde_dia), f"Em {data_recorde}", "#328c11"), unsafe_allow_html=True)
            with col_op[3]: st.markdown(kpi_html("Equipe Ativa", f"{equipe_ativa}/{total_equipe}", "Funcionários produzindo", "#FFFFFF"), unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erro ao calcular KPIs operacionais: {e}")

        if st.session_state['role'] == 'admin':
            st.subheader("Destaques Gerais")
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

    with tabs[1]:
        if st.session_state['role'] == 'admin' and (len(sel_obras) > 1 or not sel_obras): 
            st.subheader("Comparativo de Obras")
            c_o1, c_o2 = st.columns(2)
            with c_o1:
                g_obr_b = df_f.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values('PRODUÇÃO BRUTA (R$)', ascending=False)
                fig = px.bar(g_obr_b, x='OBRA', y='PRODUÇÃO BRUTA (R$)', text_auto='.2s', title="Total Bruto por Obra")
                fig.update_traces(marker_color=cor_bruta, textposition='outside', cliponaxis=False)
                st.plotly_chart(style_fig(fig), use_container_width=True)
            with c_o2:
                g_obr_l = df_f.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().reset_index().sort_values('PRODUÇÃO LÍQUIDA (R$)', ascending=False)
                fig = px.bar(g_obr_l, x='OBRA', y='PRODUÇÃO LÍQUIDA (R$)', text_auto='.2f', title="Média Líquida por Funcionário")
                fig.update_traces(marker_color=cor_liquida, textposition='outside', cliponaxis=False)
                st.plotly_chart(style_fig(fig), use_container_width=True)
            st.markdown("---")

        st.subheader("Performance Individual")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            top_b = df_f.nlargest(15, 'PRODUÇÃO BRUTA (R$)')
            fig = px.bar(top_b, x='Funcionário', y='PRODUÇÃO BRUTA (R$)', text_auto='.2s', title="Top 15 - Produção Bruta")
            fig.update_traces(marker_color=cor_bruta, textposition='outside', cliponaxis=False)
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with c_f2:
            top_l = df_f.nlargest(15, 'PRODUÇÃO LÍQUIDA (R$)')
            fig = px.bar(top_l, x='Funcionário', y='PRODUÇÃO LÍQUIDA (R$)', text_auto='.2s', title="Top 15 - Produção Líquida")
            fig.update_traces(marker_color=cor_liquida, textposition='outside', cliponaxis=False)
            st.plotly_chart(style_fig(fig), use_container_width=True)

        st.subheader("Distribuição")
        fig_hist = px.histogram(df_f, x="PRODUÇÃO LÍQUIDA (R$)", nbins=20, title="Distribuição de Prod. Líquida", color_discrete_sequence=[cor_liquida], text_auto=True)
        fig_hist.update_layout(bargap=0.1)
        st.plotly_chart(style_fig(fig_hist), use_container_width=True)

    with tabs[2]:
        st.subheader("Análise Avançada")
        c_adv1, c_adv2 = st.columns(2)
        with c_adv1:
            fig_box = px.box(df_f[df_f['PRODUÇÃO BRUTA (R$)']>0], x='FUNÇÃO', y='PRODUÇÃO BRUTA (R$)', color='FUNÇÃO', title="Consistência das Equipes (Boxplot)")
            fig_box.update_layout(showlegend=False)
            st.plotly_chart(style_fig(fig_box), use_container_width=True)
        
        with c_adv2:
            fig_scat = px.scatter(df_f[df_f['PRODUÇÃO BRUTA (R$)']>0], x='SALARIO_BASE', y='PRODUÇÃO BRUTA (R$)', 
                                size='ROI', color='FUNÇÃO', hover_name='Funcionário',
                                title="Matriz Custo x Benefício")
            st.plotly_chart(style_fig(fig_scat), use_container_width=True)

        st.markdown("---")
        st.subheader("Detalhamento de Custos")
        c_det1, c_det2 = st.columns(2)
        
        with c_det1:
            if not lancs_f.empty:
                pareto = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO'].groupby('Serviço')['Valor Parcial'].sum().reset_index().sort_values('Valor Parcial', ascending=False)
                pareto['Acum'] = pareto['Valor Parcial'].cumsum() / pareto['Valor Parcial'].sum() * 100
                pareto = pareto.head(15)
                pareto['Serviço_Visual'] = pareto['Serviço'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)

                fig_par = go.Figure()
                fig_par.add_trace(go.Bar(x=pareto['Serviço_Visual'], y=pareto['Valor Parcial'], name='Valor (R$)', marker_color=cor_bruta))
                fig_par.add_trace(go.Scatter(x=pareto['Serviço_Visual'], y=pareto['Acum'], name='Acumulado %', yaxis='y2', mode='lines+markers', line=dict(color=cor_liquida)))
                
                fig_par.update_layout(
                    title="Pareto de Serviços (Top 15)",
                    yaxis2=dict(overlaying='y', side='right', range=[0, 110], showgrid=False), 
                    showlegend=False, 
                    xaxis=dict(tickangle=-45)
                )
                st.plotly_chart(style_fig(fig_par), use_container_width=True)
        with c_det2:
            lancs_hier = lancs_f[(lancs_f['Disciplina']!='GRATIFICAÇÃO') & (lancs_f['Valor Parcial'] > 50)]
            if not lancs_hier.empty:
                fig_sun = px.sunburst(lancs_hier, path=['Obra', 'Disciplina', 'Serviço'], values='Valor Parcial', color='Valor Parcial', color_continuous_scale='Oranges', title="Hierarquia de Custos")
                st.plotly_chart(style_fig(fig_sun), use_container_width=True)

    with tabs[3]:
        st.subheader("Linha do Tempo")
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

    if st.session_state['role'] == 'admin' and len(tabs) > 4:
        with tabs[4]:
            st.subheader("Controle de Prazos e Entregas")
            
            c_d1, c_d2 = st.columns(2)
            lancs_prod = lancs_f[lancs_f['Disciplina']!='GRATIFICAÇÃO']
            if not lancs_prod.empty:
                with c_d1:
                    top_s = lancs_prod.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                    fig = px.bar(top_s, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços (Custo Total)", text_auto='.2s')
                    fig.update_traces(marker_color=cor_bruta, textposition='outside', cliponaxis=False)
                    st.plotly_chart(style_fig(fig), use_container_width=True)
                with c_d2:
                    top_d = lancs_prod.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                    fig = px.bar(top_d, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas", text_auto='.2s')
                    fig.update_traces(marker_color=cor_bruta, textposition='outside', cliponaxis=False)
                    st.plotly_chart(style_fig(fig), use_container_width=True)

            if not folhas_df.empty:
                st.markdown("---")
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    folhas_env = folhas_df[folhas_df['data_lancamento'].notna()].copy()
                    if not folhas_env.empty and sel_obras: folhas_env = folhas_env[folhas_env['Obra'].isin(sel_obras)]
                    
                    if not folhas_env.empty:
                        folhas_env['dt_envio'] = pd.to_datetime(folhas_env['data_lancamento'])
                        folhas_env['Mes'] = pd.to_datetime(folhas_env['Mes'], errors='coerce')
                        folhas_env['limite'] = folhas_env['Mes'].apply(lambda x: x.replace(day=23) if pd.notna(x) else pd.NaT)
                        
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
                        fig = px.bar(atraso_med, x='Obra', y='atraso', title="Dias de Atraso Médio no Envio", text_auto='.1f')
                        fig.update_traces(marker_color='#ef4444', textposition='outside', cliponaxis=False)
                        st.plotly_chart(style_fig(fig), use_container_width=True)
                    else: st.info("Sem dados de envio para cálculo de atraso.")
                
                with c_p2:
                    folhas_count = folhas_df.copy()
                    if sel_obras: folhas_count = folhas_count[folhas_count['Obra'].isin(sel_obras)]
                    if not folhas_count.empty:
                        if is_periodo_composto:
                            env_count = folhas_count.groupby('Obra')['contador_envios'].mean().reset_index()
                            titulo_rev = "Média de Revisões (por Mês)"
                            formato_num = '.1f'
                        else:
                            env_count = folhas_count.groupby('Obra')['contador_envios'].sum().reset_index()
                            titulo_rev = "Quantidade Total de Revisões"
                            formato_num = 'd'

                        fig = px.bar(env_count, x='Obra', y='contador_envios', title=titulo_rev, text_auto=formato_num)
                        fig.update_traces(marker_color=cor_bruta, textposition='outside', cliponaxis=False)
                        st.plotly_chart(style_fig(fig), use_container_width=True)
