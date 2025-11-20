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

   
