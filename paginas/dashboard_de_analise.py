import streamlit as st
import pandas as pd
import plotly.express as px
import db_utils
import utils
from datetime import date 

def render_page():
    mes_selecionado = st.session_state.selected_month
    st.header(f"Dashboard de Análise - {mes_selecionado}")

    @st.cache_data
    def get_dashboard_data(mes):
        lancs_df = db_utils.get_lancamentos_do_mes(mes)
        funcs_df = db_utils.get_funcionarios() 
        folhas_df = db_utils.get_folhas_mensais(mes) 
        obras_df = db_utils.get_obras()
        return lancs_df, funcs_df, folhas_df, obras_df

    lancamentos_df, funcionarios_df, folhas_df, obras_df = get_dashboard_data(mes_selecionado)

    if lancamentos_df.empty and funcionarios_df.empty:
        st.info(f"Ainda não há lançamentos ou funcionários cadastrados para o mês {mes_selecionado}.")
        return
    elif lancamentos_df.empty:
         st.info(f"Ainda não há lançamentos de produção para analisar no mês {mes_selecionado}.")
    if not lancamentos_df.empty:
        lancamentos_df['Valor Parcial'] = lancamentos_df['Valor Parcial'].apply(utils.safe_float)
        producao_bruta_agg = lancamentos_df.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
        producao_bruta_agg.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
        resumo_df = pd.merge(
            funcionarios_df, 
            producao_bruta_agg, 
            on='funcionario_id', 
            how='left' 
        )
    else:
        resumo_df = funcionarios_df.copy()
        resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0

    resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)'}, inplace=True)
    resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0).apply(utils.safe_float)
    resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float) 
    
    resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
    resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)
    resumo_df['EFICIENCIA (Líquida/Base)'] = (resumo_df['PRODUÇÃO LÍQUIDA (R$)'] / resumo_df['SALÁRIO BASE (R$)']).fillna(0).replace(float('inf'), 0)
    df_filtrado_resumo = resumo_df.copy()
    df_filtrado_lanc = lancamentos_df.copy() 

    st.sidebar.markdown("---") 
    st.sidebar.subheader("Filtros do Dashboard")
    obras_disponiveis = sorted(resumo_df['OBRA'].unique())
    obra_selecionada = []
    if st.session_state['role'] == 'admin':
        obra_selecionada = st.sidebar.multiselect(
            "Filtrar por Obra(s)", 
            options=obras_disponiveis, 
            key="dash_obras_admin",
            default=obras_disponiveis
        )
    else:
        obra_selecionada = [st.session_state['obra_logada']] 

    if obra_selecionada:
         df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['OBRA'].isin(obra_selecionada)]
         if not df_filtrado_lanc.empty:
             df_filtrado_lanc = df_filtrado_lanc[df_filtrado_lanc['Obra'].isin(obra_selecionada)]
    else:
        df_filtrado_resumo = pd.DataFrame(columns=resumo_df.columns)
        df_filtrado_lanc = pd.DataFrame(columns=lancamentos_df.columns)


    funcoes_disponiveis = sorted(df_filtrado_resumo['FUNÇÃO'].unique())
    funcao_selecionada = st.sidebar.multiselect(
        "Filtrar por Função(ões)",
        options=funcoes_disponiveis,
        key="dash_funcoes",
        default=funcoes_disponiveis 
    )
    if funcao_selecionada:
        df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['FUNÇÃO'].isin(funcao_selecionada)]
        if not df_filtrado_lanc.empty:
            funcs_filtrados_ids = df_filtrado_resumo['funcionario_id'].unique()
            df_filtrado_lanc = df_filtrado_lanc[df_filtrado_lanc['funcionario_id'].isin(funcs_filtrados_ids)]
    else:
        df_filtrado_resumo = pd.DataFrame(columns=resumo_df.columns)
        df_filtrado_lanc = pd.DataFrame(columns=lancamentos_df.columns)


    if df_filtrado_resumo.empty and df_filtrado_lanc.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        return 

    st.markdown("---")
    st.subheader("💡 Indicadores Chave")
    
    total_prod_bruta = df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].sum()
    total_prod_liquida = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].sum()
    media_prod_liquida_func = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].mean() if not df_filtrado_resumo.empty else 0
    
    top_funcionario_bruta = df_filtrado_resumo.loc[df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].idxmax()]['Funcionário'] if not df_filtrado_resumo.empty and df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].max() > 0 else "N/A"
    top_servico_custo = df_filtrado_lanc.groupby('Serviço')['Valor Parcial'].sum().idxmax() if not df_filtrado_lanc.empty else "N/A"

    num_cols = 4 if st.session_state['role'] == 'admin' else 4 
    kpi_cols = st.columns(num_cols)
    
    kpi_cols[0].metric("💰 Prod. Bruta Total", utils.format_currency(total_prod_bruta))
    kpi_cols[1].metric("📈 Prod. Líquida Total", utils.format_currency(total_prod_liquida))
    kpi_cols[2].metric("👤 Prod. Líquida Média / Func.", utils.format_currency(media_prod_liquida_func))
    kpi_cols[3].metric("⭐ Funcionário Destaque (Bruta)", top_funcionario_bruta)

    if st.session_state['role'] == 'admin':
        kpi_cols_admin = st.columns(num_cols)
        top_obra_bruta = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().idxmax() if not df_filtrado_resumo.empty and df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].sum() > 0 else "N/A"
        media_liquida_por_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean()
        top_obra_eficiencia = media_liquida_por_obra.idxmax() if not media_liquida_por_obra.empty else "N/A"
        
        kpi_cols_admin[0].metric("🏆 Obra Destaque (Bruta)", top_obra_bruta)
        kpi_cols_admin[1].metric("🚀 Obra Mais Eficiente (Líq/Func)", top_obra_eficiencia)
        kpi_cols_admin[2].metric("🔧 Serviço de Maior Custo", top_servico_custo)


    cor_bruta = '#E37026' 
    cor_liquida = '#1E88E5' 
    
    if st.session_state['role'] == 'admin' and len(obra_selecionada) > 1 : 
        st.markdown("---")
        st.subheader("🏗️ Análise por Obra")
        
        col_obra1, col_obra2 = st.columns(2)
        
        with col_obra1:
            prod_bruta_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False)
            fig_bar_obra_bruta = px.bar(
                prod_bruta_obra, 
                x='OBRA', y='PRODUÇÃO BRUTA (R$)', 
                text_auto=True, title="Produção Bruta Total por Obra",
                labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'}
            )
            fig_bar_obra_bruta.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_bruta)
            fig_bar_obra_bruta.update_layout(xaxis_title=None)
            st.plotly_chart(fig_bar_obra_bruta, use_container_width=True)

        with col_obra2:
            prod_liquida_media_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False)
            fig_bar_obra_liq_media = px.bar(
                prod_liquida_media_obra,
                x='OBRA', y='PRODUÇÃO LÍQUIDA (R$)',
                text_auto=True, title="Produção Líquida Média por Funcionário por Obra",
                labels={'PRODUÇÃO LÍQUIDA (R$)': 'Prod. Líquida Média / Func. (R$)'}
            )
            fig_bar_obra_liq_media.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_liquida)
            fig_bar_obra_liq_media.update_layout(xaxis_title=None)
            st.plotly_chart(fig_bar_obra_liq_media, use_container_width=True)

    st.markdown("---")
    st.subheader("Análise por Funcionário")
    col_func1, col_func2 = st.columns(2)

    with col_func1:
        prod_bruta_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False).head(15) # Top 15
        fig_bar_func_bruta = px.bar(
            prod_bruta_func, 
            x='Funcionário', y='PRODUÇÃO BRUTA (R$)', 
            text_auto=True, title="Top 15 Funcionários por Produção Bruta",
            labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'}
        )
        fig_bar_func_bruta.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_bruta)
        fig_bar_func_bruta.update_layout(xaxis_title=None)
        st.plotly_chart(fig_bar_func_bruta, use_container_width=True)

    with col_func2:
        prod_liquida_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO LÍQUIDA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False).head(15) # Top 15
        fig_bar_func_liquida = px.bar(
            prod_liquida_func,
            x='Funcionário', y='PRODUÇÃO LÍQUIDA (R$)',
            text_auto=True, title="Top 15 Funcionários por Produção Líquida",
            labels={'PRODUÇÃO LÍQUIDA (R$)': 'Produção Líquida (R$)'}
        )
        fig_bar_func_liquida.update_traces(texttemplate='%{y:,.2f}', textposition='outside', marker_color=cor_liquida)
        fig_bar_func_liquida.update_layout(xaxis_title=None)
        st.plotly_chart(fig_bar_func_liquida, use_container_width=True)

    st.markdown("---")
    st.subheader("Distribuição da Eficiência dos Funcionários")
    if not df_filtrado_resumo.empty:
        fig_hist_liquida = px.histogram(
            df_filtrado_resumo, 
            x="PRODUÇÃO LÍQUIDA (R$)", 
            nbins=20, 
            title="Distribuição da Produção Líquida por Funcionário",
            labels={'PRODUÇÃO LÍQUIDA (R$)': 'Faixa de Produção Líquida (R$)', 'count': 'Nº de Funcionários'},
            color_discrete_sequence=[cor_liquida]
        )
        fig_hist_liquida.update_layout(yaxis_title="Nº de Funcionários")
        st.plotly_chart(fig_hist_liquida, use_container_width=True)
        st.caption("Este gráfico mostra quantos funcionários se encaixam em cada faixa de produção líquida. Ajuda a entender se a maior parte da produção líquida vem de poucos funcionários ou é bem distribuída.")
    else:
        st.info("Não há dados de produção líquida para exibir a distribuição.")

    if not df_filtrado_lanc.empty:
        st.markdown("---")
        st.subheader("Produção Bruta ao Longo do Tempo")
        df_filtrado_lanc['Data do Serviço'] = pd.to_datetime(df_filtrado_lanc['Data do Serviço']) 
        
        prod_dia = df_filtrado_lanc.groupby(df_filtrado_lanc['Data do Serviço'].dt.date)['Valor Parcial'].sum().reset_index()
        prod_dia.rename(columns={'Valor Parcial': 'Produção Bruta Diária (R$)'}, inplace=True)
        
        fig_line_dia = px.line(
            prod_dia, x='Data do Serviço', y='Produção Bruta Diária (R$)', 
            markers=True, title="Evolução Diária da Produção Bruta",
            labels={'Data do Serviço': 'Dia', 'Produção Bruta Diária (R$)': 'Produção Bruta (R$)'}
        )
        fig_line_dia.update_traces(line_color=cor_bruta, marker=dict(color=cor_bruta))
        st.plotly_chart(fig_line_dia, use_container_width=True)
    else:
         st.info("Sem dados de lançamento para análise temporal.")


    if st.session_state['role'] == 'admin':
        
        if len(funcao_selecionada) > 1 : 
            st.markdown("---")
            st.subheader("Análise de Custo x Benefício por Função")
            
            custo_beneficio_funcao = df_filtrado_resumo.groupby('FUNÇÃO').agg(
                salario_base_medio=('SALÁRIO BASE (R$)', 'mean'),
                producao_bruta_media=('PRODUÇÃO BRUTA (R$)', 'mean'),
                producao_liquida_media=('PRODUÇÃO LÍQUIDA (R$)', 'mean'),
                contagem=('funcionario_id', 'nunique') 
            ).reset_index()

            fig_scatter_funcao = px.scatter(
                custo_beneficio_funcao,
                x="salario_base_medio",
                y="producao_liquida_media",
                size="contagem", 
                color="FUNÇÃO", 
                hover_name="FUNÇÃO",
                hover_data={ 
                    'salario_base_medio': ':.2f', 
                    'producao_bruta_media': ':.2f',
                    'producao_liquida_media': ':.2f',
                    'contagem': True,
                    'FUNÇÃO': False
                },
                title="Custo (Salário Base Médio) vs Benefício (Produção Líquida Média) por Função",
                labels={
                    "salario_base_medio": "Salário Base Médio (R$)",
                    "producao_liquida_media": "Produção Líquida Média (R$)",
                    "contagem": "Nº Funcionários"
                }
            )
            fig_scatter_funcao.update_layout(xaxis_title="Custo Médio (Salário Base)", yaxis_title="Benefício Médio (Produção Líquida)")
            st.plotly_chart(fig_scatter_funcao, use_container_width=True)
            st.caption("Cada bolha representa uma função. O eixo X mostra o custo médio (salário base) e o eixo Y o benefício médio (produção líquida) gerado por funcionários dessa função. O tamanho da bolha indica quantos funcionários existem nela. Funções no quadrante superior esquerdo são potencialmente mais eficientes (baixo custo, alto benefício).")

        if not df_filtrado_lanc.empty:
            st.markdown("---")
            st.subheader("Análise Detalhada de Serviços e Disciplinas (Custo)")
            col_serv, col_disc = st.columns(2)
            
            with col_serv:
                serv_custo = df_filtrado_lanc.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig_custo_serv = px.bar(
                    serv_custo, y='Serviço', x='Valor Parcial', 
                    orientation='h', title="Top 10 Serviços por Custo Total (Prod. Bruta)", text_auto=True,
                    labels={'Valor Parcial': 'Custo Total (R$)'}
                )
                fig_custo_serv.update_traces(marker_color=cor_bruta, texttemplate='%{x:,.2f}', textposition='outside')
                fig_custo_serv.update_layout(yaxis_title=None)
                st.plotly_chart(fig_custo_serv, use_container_width=True)

            with col_disc:
                disc_custo = df_filtrado_lanc.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig_custo_disc = px.bar(
                    disc_custo, y='Disciplina', x='Valor Parcial', 
                    orientation='h', title="Top 10 Disciplinas por Custo Total (Prod. Bruta)", text_auto=True,
                     labels={'Valor Parcial': 'Custo Total (R$)'}
                 )
                fig_custo_disc.update_traces(marker_color=cor_bruta, texttemplate='%{x:,.2f}', textposition='outside')
                fig_custo_disc.update_layout(yaxis_title=None)
                st.plotly_chart(fig_custo_disc, use_container_width=True)

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
                    folhas_enviadas_df['data_limite'] = folhas_enviadas_df['Mes_dt'].apply(
                        lambda dt: dt.replace(day=DIA_LIMITE).date() if pd.notna(dt) else pd.NaT
                    )
                    folhas_enviadas_df['data_lancamento_date'] = folhas_enviadas_df['data_lancamento'].dt.date

                    folhas_enviadas_df['dias_atraso'] = folhas_enviadas_df.apply(
                        lambda row: (row['data_lancamento_date'] - row['data_limite']).days 
                                    if pd.notna(row['data_limite']) and row['data_lancamento_date'] > row['data_limite'] 
                                    else 0, 
                        axis=1
                    )
                    
                    if obra_selecionada:
                        folhas_enviadas_filtrado = folhas_enviadas_df[folhas_enviadas_df['Obra'].isin(obra_selecionada)]
                    else:
                        folhas_enviadas_filtrado = pd.DataFrame(columns=folhas_enviadas_df.columns)

                    if not folhas_enviadas_filtrado.empty:
                        media_atraso_por_obra = folhas_enviadas_filtrado.groupby('Obra')['dias_atraso'].mean().round(1).reset_index()
                        fig_atraso = px.bar(
                            media_atraso_por_obra.sort_values(by='dias_atraso', ascending=False),
                            x='Obra', y='dias_atraso',
                            title="Média de Dias de Atraso na Entrega da Folha", text_auto=True,
                            labels={'dias_atraso': 'Média de Dias de Atraso'}
                        )
                        fig_atraso.update_traces(marker_color='#FFAB00', textposition='outside') 
                        fig_atraso.update_layout(xaxis_title=None)
                        st.plotly_chart(fig_atraso, use_container_width=True)
                    else:
                        st.info("Nenhum dado de envio de folha para as obras selecionadas.")
                else:
                    st.info("Ainda não há dados de envio de folhas para analisar os prazos.")

            with col_prazo2:
                if obra_selecionada:
                    folhas_filtrado_envios = folhas_df[folhas_df['Obra'].isin(obra_selecionada)]
                else:
                     folhas_filtrado_envios = pd.DataFrame(columns=folhas_df.columns)

                if not folhas_filtrado_envios.empty:
                    envios_por_obra = folhas_filtrado_envios.groupby('Obra')['contador_envios'].sum().reset_index()
                    fig_envios = px.bar(
                        envios_por_obra.sort_values('contador_envios', ascending=False),
                        x='Obra', y='contador_envios',
                        title=f"Total de Envios para Auditoria em {mes_selecionado}",
                        labels={'contador_envios': 'Número de Envios'},
                        text_auto=True
                    )
                    fig_envios.update_traces(marker_color='#64B5F6', textposition='outside')
                    fig_envios.update_layout(xaxis_title=None)
                    st.plotly_chart(fig_envios, use_container_width=True)
                else:
                    st.info("Nenhuma folha enviada para auditoria nas obras selecionadas neste mês.")
