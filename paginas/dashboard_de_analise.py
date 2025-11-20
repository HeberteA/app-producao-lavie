import streamlit as st
import pandas as pd
import plotly.express as px
import db_utils
import utils

def render_page():
    st.markdown("""
    <style>
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.05); /* Fundo escuro transparente */
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-title {
        font-size: 0.85rem;
        color: #AAA;
        margin-bottom: 5px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #FFF;
    }
    .kpi-highlight { color: #E37026; } /* Laranja */
    .kpi-blue { color: #3b82f6; } /* Azul */
    .kpi-green { color: #10b981; } /* Verde */
    
    /* Ajuste para gráficos em fundo escuro */
    .js-plotly-plot .plotly .main-svg {
        background: rgba(0,0,0,0) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    cor_bruta = '#E37026'
    cor_liquida = '#1E88E5'

    def format_label_brl(value):
        try: return f"R$ {float(value):_.2f}".replace('.',',').replace('_','.')
        except (ValueError, TypeError): return ""

    def make_kpi(title, value, color_class=""):
        return f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value {color_class}">{value}</div>
        </div>
        """
    
    def style_fig(fig):
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',  
            font=dict(color='#E0E0E0'),    
            xaxis=dict(showgrid=False, color='#A0A0A0'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', color='#A0A0A0'),
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    mes_selecionado = st.session_state.selected_month
    st.header(f"Dashboard de Análise - {mes_selecionado}")

    @st.cache_data
    def get_data(mes):
        return db_utils.get_lancamentos_do_mes(mes), db_utils.get_funcionarios(), db_utils.get_folhas_mensais(mes), db_utils.get_obras()
    
    lancamentos_df, funcionarios_df, folhas_df, obras_df = get_data(mes_selecionado)
    
    if funcionarios_df.empty: st.info("Sem dados."); return

    lancamentos_df['Valor Parcial'] = lancamentos_df['Valor Parcial'].apply(utils.safe_float)
    prod = lancamentos_df[lancamentos_df['Disciplina']!='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'})
    grat = lancamentos_df[lancamentos_df['Disciplina']=='GRATIFICAÇÃO'].groupby('funcionario_id')['Valor Parcial'].sum().reset_index().rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'})
    
    resumo = funcionarios_df.merge(prod, left_on='id', right_on='funcionario_id', how='left').merge(grat, left_on='id', right_on='funcionario_id', how='left')
    resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']] = resumo[['PRODUÇÃO BRUTA (R$)', 'TOTAL GRATIFICAÇÕES (R$)']].fillna(0.0)
    resumo['SALÁRIO BASE (R$)'] = resumo['SALARIO_BASE'].apply(utils.safe_float)
    resumo['PRODUÇÃO LÍQUIDA (R$)'] = resumo.apply(utils.calcular_producao_liquida, axis=1)
    resumo['Funcionário'] = resumo['NOME']

    with st.expander("Filtros Avançados", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        obras_opts = sorted(resumo['OBRA'].unique())
        sel_obras = col_f1.multiselect("Obras", obras_opts, default=obras_opts if st.session_state['role'] == 'admin' else [st.session_state['obra_logada']])
        
        if sel_obras: resumo = resumo[resumo['OBRA'].isin(sel_obras)]
        
        sel_func = col_f2.multiselect("Funções", sorted(resumo['FUNÇÃO'].unique()))
        if sel_func: resumo = resumo[resumo['FUNÇÃO'].isin(sel_func)]

    tot_bruta = resumo['PRODUÇÃO BRUTA (R$)'].sum()
    tot_liq = resumo['PRODUÇÃO LÍQUIDA (R$)'].sum()
    tot_grat = resumo['TOTAL GRATIFICAÇÕES (R$)'].sum()
    media_liq = resumo['PRODUÇÃO LÍQUIDA (R$)'].mean()
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(make_kpi("Produção Bruta", utils.format_currency(tot_bruta), "kpi-highlight"), unsafe_allow_html=True)
    with c2: st.markdown(make_kpi("Produção Líquida", utils.format_currency(tot_liq), "kpi-blue"), unsafe_allow_html=True)
    with c3: st.markdown(make_kpi("Gratificações", utils.format_currency(tot_grat), "kpi-green"), unsafe_allow_html=True)
    with c4: st.markdown(make_kpi("Média / Func.", utils.format_currency(media_liq)), unsafe_allow_html=True)

    st.markdown("---")
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("##### Top Produtividade (Bruta)")
        top_bruta = resumo.nlargest(10, 'PRODUÇÃO BRUTA (R$)')
        fig_bar = px.bar(top_bruta, x='PRODUÇÃO BRUTA (R$)', y='Funcionário', orientation='h', text_auto='.2s',
                         color='PRODUÇÃO BRUTA (R$)', color_continuous_scale=['#333', '#E37026'])
        fig_bar.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
        fig_bar = style_fig(fig_bar)
        fig_bar.update_layout(yaxis=dict(categoryorder='total ascending'), coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
        st.markdown("##### Distribuição de Eficiência")
        fig_hist = px.histogram(resumo, x="PRODUÇÃO LÍQUIDA (R$)", nbins=15, 
                                color_discrete_sequence=['#1E88E5'], opacity=0.8)
        fig_hist = style_fig(fig_hist)
        fig_hist.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("---")
    st.subheader("Análise Hierárquica de Custos")
    
    if not lancamentos_df.empty and 'Obra' in lancamentos_df.columns:
        df_sun = lancamentos_df[lancamentos_df['Obra'].isin(sel_obras)].copy() if sel_obras else lancamentos_df.copy()
        df_sun = df_sun[df_sun['Disciplina'] != 'GRATIFICAÇÃO'] 
        if not df_sun.empty:
             df_grouped = df_sun.groupby(['Obra', 'Disciplina', 'Serviço'])['Valor Parcial'].sum().reset_index()
             df_grouped = df_grouped[df_grouped['Valor Parcial'] > 100] 
             
             fig_sun = px.sunburst(df_grouped, path=['Obra', 'Disciplina', 'Serviço'], values='Valor Parcial',
                                   color='Valor Parcial', color_continuous_scale='Oranges')
             fig_sun = style_fig(fig_sun)
             fig_sun.update_layout(height=600)
             st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.info("Dados insuficientes para gráfico hierárquico de produção.")

    if not df_filtrado_resumo.empty:
        if st.session_state['role'] == 'admin' and len(obra_selecionada_filt) > 1 : 
            st.markdown("---")
            st.subheader("Análise por Obra")
            col_obra1, col_obra2 = st.columns(2)
            with col_obra1:
                 prod_bruta_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False)
                 fig_bar_obra_bruta = px.bar(prod_bruta_obra, x='OBRA', y='PRODUÇÃO BRUTA (R$)', text_auto=True, title="Produção Bruta Total por Obra", labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'})
                 fig_bar_obra_bruta.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_bruta, textfont_size=10)
                 fig_bar_obra_bruta.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                 st.plotly_chart(fig_bar_obra_bruta, use_container_width=True)
            with col_obra2:
                 prod_liquida_media_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False)
                 fig_bar_obra_liq_media = px.bar(prod_liquida_media_obra, x='OBRA', y='PRODUÇÃO LÍQUIDA (R$)', text_auto=True, title="Produção Líquida Média por Funcionário por Obra", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Prod. Líquida Média / Func. (R$)'})
                 fig_bar_obra_liq_media.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_liquida, textfont_size=10)
                 fig_bar_obra_liq_media.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                 st.plotly_chart(fig_bar_obra_liq_media, use_container_width=True)

        st.markdown("---")
        st.subheader("Análise por Funcionário")
        col_func1, col_func2 = st.columns(2)
        with col_func1:
            prod_bruta_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False).head(15)
            fig_bar_func_bruta = px.bar(prod_bruta_func, x='Funcionário', y='PRODUÇÃO BRUTA (R$)', text_auto=True, title="Top 15 Funcionários por Produção Bruta", labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'})
            fig_bar_func_bruta.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_bruta, textfont_size=10)
            fig_bar_func_bruta.update_layout(xaxis_title=None, xaxis_tickangle=-45, uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig_bar_func_bruta, use_container_width=True)
        with col_func2:
            prod_liquida_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO LÍQUIDA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False).head(15)
            fig_bar_func_liquida = px.bar(prod_liquida_func, x='Funcionário', y='PRODUÇÃO LÍQUIDA (R$)', text_auto=True, title="Top 15 Funcionários por Produção Líquida", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Produção Líquida (R$)'})
            fig_bar_func_liquida.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_liquida, textfont_size=10)
            fig_bar_func_liquida.update_layout(xaxis_title=None, xaxis_tickangle=-45, uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig_bar_func_liquida, use_container_width=True)

        st.markdown("---")
        st.subheader("Distribuição da Eficiência dos Funcionários")
        fig_hist_liquida = px.histogram(df_filtrado_resumo, x="PRODUÇÃO LÍQUIDA (R$)", nbins=20, title="Distribuição da Produção Líquida por Funcionário", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Faixa de Produção Líquida (R$)', 'count': 'Nº de Funcionários'}, color_discrete_sequence=[cor_liquida], text_auto=True)
        fig_hist_liquida.update_layout(yaxis_title="Nº de Funcionários", bargap=0.1)
        fig_hist_liquida.update_traces(textposition='outside')
        st.plotly_chart(fig_hist_liquida, use_container_width=True)
        st.caption("Este gráfico mostra quantos funcionários se encaixam em cada faixa de produção líquida.")

    if not df_filtrado_lanc.empty:
        st.markdown("---")
        st.subheader("Produção Bruta ao Longo do Tempo")
        try:
            df_filtrado_lanc['Data do Serviço'] = pd.to_datetime(df_filtrado_lanc['Data do Serviço'])
            prod_dia = df_filtrado_lanc.groupby(df_filtrado_lanc['Data do Serviço'].dt.date)['Valor Parcial'].sum().reset_index()
            prod_dia.rename(columns={'Valor Parcial': 'Produção Bruta Diária (R$)'}, inplace=True)
            fig_line_dia = px.line(prod_dia, x='Data do Serviço', y='Produção Bruta Diária (R$)', markers=True, title="Evolução Diária da Produção Bruta", labels={'Data do Serviço': 'Dia', 'Produção Bruta Diária (R$)': 'Produção Bruta (R$)'})
            fig_line_dia.update_traces(line_color=cor_bruta, marker=dict(color=cor_bruta))
            st.plotly_chart(fig_line_dia, use_container_width=True)
        except Exception as e_time: st.warning(f"Não foi possível gerar o gráfico temporal: {e_time}")

        if st.session_state['role'] == 'admin':
            if not df_filtrado_resumo.empty and len(funcao_selecionada_filt) > 1 : 
                st.markdown("---")
                st.subheader("Análise de Custo x Benefício por Função")
                custo_beneficio_funcao = df_filtrado_resumo.groupby('FUNÇÃO').agg(salario_base_medio=('SALÁRIO BASE (R$)', 'mean'), producao_bruta_media=('PRODUÇÃO BRUTA (R$)', 'mean'), producao_liquida_media=('PRODUÇÃO LÍQUIDA (R$)', 'mean'), contagem=('id', 'nunique')).reset_index()
                fig_scatter_funcao = px.scatter(custo_beneficio_funcao, x="salario_base_medio", y="producao_liquida_media", size="contagem", color="FUNÇÃO", hover_name="FUNÇÃO", hover_data={'salario_base_medio': ':.2f', 'producao_bruta_media': ':.2f', 'producao_liquida_media': ':.2f', 'contagem': True, 'FUNÇÃO': False}, title="Custo (Salário Base Médio) vs Benefício (Produção Líquida Média) por Função", labels={"salario_base_medio": "Salário Base Médio (R$)", "producao_liquida_media": "Produção Líquida Média (R$)", "contagem": "Nº Funcionários"})
                fig_scatter_funcao.update_layout(xaxis_title="Custo Médio (Salário Base)", yaxis_title="Benefício Médio (Produção Líquida)")
                st.plotly_chart(fig_scatter_funcao, use_container_width=True)
                st.caption("Cada bolha representa uma função. Eixo X = custo médio, Eixo Y = benefício médio. Tamanho da bolha = nº de funcionários.")

            st.markdown("---")
            st.subheader("Análise Detalhada (Custo)")
            col_serv, col_disc = st.columns(2)
            if not lanc_sem_grat.empty:
                with col_serv:
                    serv_custo = lanc_sem_grat.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                    fig_custo_serv = px.bar(serv_custo, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços (Exceto Grat.) por Custo", text_auto=True, labels={'Valor Parcial': 'Custo Total (R$)'})
                    fig_custo_serv.update_traces(marker_color=cor_bruta, texttemplate='R$ %{x:,.2f}', textposition='outside', textfont_size=10)
                    fig_custo_serv.update_layout(yaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                    st.plotly_chart(fig_custo_serv, use_container_width=True)
                with col_disc:
                    disc_custo = lanc_sem_grat.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                    fig_custo_disc = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas (Exceto Grat.) por Custo", text_auto=True, labels={'Valor Parcial': 'Custo Total (R$)'})
                    fig_custo_disc.update_traces(marker_color=cor_bruta, texttemplate='R$ %{x:,.2f}', textposition='outside', textfont_size=10)
                    fig_custo_disc.update_layout(yaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                    st.plotly_chart(fig_custo_disc, use_container_width=True)
            else: st.info("Nenhum serviço (exceto gratificações) encontrado para análise detalhada.")

    elif df_filtrado_resumo.empty and not resumo_df.empty : pass
    elif resumo_df.empty and funcionarios_df.empty: pass
    elif resumo_df.empty: pass
    else: st.info(f"Nenhum lançamento encontrado para gerar análises detalhadas.")


    if st.session_state['role'] == 'admin':
        if not folhas_df.empty:
             st.markdown("---")
             st.subheader("Análise de Prazos e Envios")
             col_prazo1, col_prazo2 = st.columns(2)
             with col_prazo1:
                folhas_enviadas_df = folhas_df[folhas_df['data_lancamento'].notna()].copy()
                if not folhas_enviadas_df.empty:
                    folhas_enviadas_df['data_lancamento'] = pd.to_datetime(folhas_enviadas_df['data_lancamento'])
                    folhas_enviadas_df['Mes_dt'] = pd.to_datetime(folhas_enviadas_df['Mes'])
                    DIA_LIMITE = 23
                    folhas_enviadas_df['data_limite'] = folhas_enviadas_df['Mes_dt'].apply(lambda dt: dt.replace(day=DIA_LIMITE).date() if pd.notna(dt) else pd.NaT)
                    folhas_enviadas_df['data_lancamento_date'] = folhas_enviadas_df['data_lancamento'].dt.date
                    folhas_enviadas_df['dias_atraso'] = folhas_enviadas_df.apply(lambda row: (row['data_lancamento_date'] - row['data_limite']).days if pd.notna(row['data_limite']) and row['data_lancamento_date'] > row['data_limite'] else 0, axis=1)

                    folhas_enviadas_filtrado = pd.DataFrame(columns=folhas_enviadas_df.columns)
                    if obra_selecionada_filt: 
                        folhas_enviadas_filtrado = folhas_enviadas_df[folhas_enviadas_df['Obra'].isin(obra_selecionada_filt)]

                    if not folhas_enviadas_filtrado.empty:
                        media_atraso_por_obra = folhas_enviadas_filtrado.groupby('Obra')['dias_atraso'].mean().round(1).reset_index()
                        fig_atraso = px.bar(media_atraso_por_obra.sort_values(by='dias_atraso', ascending=False), x='Obra', y='dias_atraso', title="Média de Dias de Atraso na Entrega", text_auto=True, labels={'dias_atraso': 'Média Dias Atraso'})
                        fig_atraso.update_traces(marker_color='#E37026', textposition='outside', texttemplate='%{y}')
                        fig_atraso.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                        st.plotly_chart(fig_atraso, use_container_width=True)
                    else: st.info("Nenhum dado de envio para as obras selecionadas.")
                else: st.info("Nenhum dado de envio para analisar prazos.")
             with col_prazo2:
                folhas_filtrado_envios = pd.DataFrame(columns=folhas_df.columns)
                if obra_selecionada_filt: 
                    folhas_filtrado_envios = folhas_df[folhas_df['Obra'].isin(obra_selecionada_filt)]

                if not folhas_filtrado_envios.empty:
                    envios_por_obra = folhas_filtrado_envios.groupby('Obra')['contador_envios'].sum().reset_index()
                    fig_envios = px.bar(envios_por_obra.sort_values('contador_envios', ascending=False), x='Obra', y='contador_envios', title=f"Total de Envios ({mes_selecionado})", labels={'contador_envios': 'Nº de Envios'}, text_auto=True)
                    fig_envios.update_traces(marker_color='#E37026', textposition='outside', texttemplate='%{y}')
                    fig_envios.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                    st.plotly_chart(fig_envios, use_container_width=True)
                else: st.info("Nenhuma folha enviada nas obras selecionadas.")
        else:
             st.info(f"Nenhuma folha encontrada para o mês {mes_selecionado} para análise de envios.")

   
