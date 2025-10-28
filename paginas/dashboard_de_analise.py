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

    if funcionarios_df.empty: 
        st.info(f"Nenhum funcionário ativo encontrado para o mês {mes_selecionado}.")
        return 

    producao_bruta_df = pd.DataFrame()
    total_gratificacoes_df = pd.DataFrame()

    if not lancamentos_df.empty:
        lancamentos_df['Valor Parcial'] = lancamentos_df['Valor Parcial'].apply(utils.safe_float)
        
        lanc_producao = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']
        if not lanc_producao.empty:
            producao_bruta_df = lanc_producao.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
            producao_bruta_df.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)
            
        lanc_gratificacoes = lancamentos_df[lancamentos_df['Disciplina'] == 'GRATIFICAÇÃO']
        if not lanc_gratificacoes.empty:
            total_gratificacoes_df = lanc_gratificacoes.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
            total_gratificacoes_df.rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'}, inplace=True)

    resumo_df = funcionarios_df.copy()
    if not producao_bruta_df.empty:
        resumo_df = pd.merge(resumo_df, producao_bruta_df, left_on='id', right_on='funcionario_id', how='left')
    else:
        resumo_df['PRODUÇÃO BRUTA (R$)'] = 0.0
        
    if not total_gratificacoes_df.empty:
        merge_suffixes = ('', '_grat') if 'funcionario_id' in resumo_df.columns else ('', '')
        resumo_df = pd.merge(resumo_df, total_gratificacoes_df, left_on='id', right_on='funcionario_id', how='left', suffixes=merge_suffixes)
        if 'funcionario_id_grat' in resumo_df.columns: resumo_df.drop(columns=['funcionario_id_grat'], inplace=True)
        if 'funcionario_id' in resumo_df.columns and 'id' in resumo_df.columns and 'funcionario_id' != 'id': resumo_df.drop(columns=['funcionario_id'], inplace=True)
    else:
        resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = 0.0

    resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)', 'NOME': 'Funcionário'}, inplace=True)
    resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
    resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = resumo_df['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
    resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0) 
    resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1) 
    resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1) 
    resumo_df['EFICIENCIA (Líquida/Base)'] = 0.0 
    mask_salario_positivo = resumo_df['SALÁRIO BASE (R$)'] > 0
    resumo_df.loc[mask_salario_positivo, 'EFICIENCIA (Líquida/Base)'] = \
        (resumo_df.loc[mask_salario_positivo, 'PRODUÇÃO LÍQUIDA (R$)'] / resumo_df.loc[mask_salario_positivo, 'SALÁRIO BASE (R$)'])
    resumo_df['EFICIENCIA (Líquida/Base)'] = resumo_df['EFICIENCIA (Líquida/Base)'].fillna(0)
    
    st.markdown("---")
    st.subheader("Indicadores Chave")
    
    total_prod_bruta = df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].sum()
    total_prod_liquida = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].sum()
    total_gratificacoes_kpi = df_filtrado_resumo['TOTAL GRATIFICAÇÕES (R$)'].sum() 
    media_prod_liquida_func = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].mean() if not df_filtrado_resumo.empty else 0
    
    top_funcionario_bruta = "N/A"
    if not df_filtrado_resumo.empty and df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].max() > 0:
         try: 
             idx_max_bruta = df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].idxmax()
             if 'Funcionário' in df_filtrado_resumo.columns:
                  top_funcionario_bruta = df_filtrado_resumo.loc[idx_max_bruta, 'Funcionário']
         except KeyError:
             st.error("Erro ao encontrar funcionário destaque (ID não encontrado).")

    top_servico_custo = "N/A"
    lanc_sem_grat = df_filtrado_lanc[df_filtrado_lanc['Disciplina'] != 'GRATIFICAÇÃO']
    if not lanc_sem_grat.empty:
        serv_grouped = lanc_sem_grat.groupby('Serviço')['Valor Parcial'].sum()
        if not serv_grouped.empty:
            top_servico_custo = serv_grouped.idxmax()


    num_cols = 5 
    kpi_cols = st.columns(num_cols)
    
    kpi_cols[0].metric("💰 Prod. Bruta Total", utils.format_currency(total_prod_bruta))
    kpi_cols[1].metric("📈 Prod. Líquida Total", utils.format_currency(total_prod_liquida))
    kpi_cols[2].metric("⭐ Total Gratificações", utils.format_currency(total_gratificacoes_kpi))
    kpi_cols[3].metric("👤 Prod. Líquida Média / Func.", utils.format_currency(media_prod_liquida_func))
    kpi_cols[4].metric("🏆 Funcionário Destaque (Bruta)", str(top_funcionario_bruta)) 

    if st.session_state['role'] == 'admin':
        kpi_cols_admin = st.columns(num_cols) 
        top_obra_bruta = "N/A"; top_obra_eficiencia = "N/A"; top_obra_grat = "N/A" 
        if not df_filtrado_resumo.empty:
            soma_bruta_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum()
            if soma_bruta_obra.sum() > 0:
                 try: top_obra_bruta = soma_bruta_obra.idxmax()
                 except ValueError: pass 
            
            media_liquida_por_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean()
            if not media_liquida_por_obra.empty:
                try: top_obra_eficiencia = media_liquida_por_obra.idxmax()
                except ValueError: pass

            soma_grat_obra = df_filtrado_resumo.groupby('OBRA')['TOTAL GRATIFICAÇÕES (R$)'].sum() 
            if soma_grat_obra.sum() > 0:
                 try: top_obra_grat = soma_grat_obra.idxmax()
                 except ValueError: pass

        
        kpi_cols_admin[0].metric("🏆 Obra Destaque (Bruta)", str(top_obra_bruta))
        kpi_cols_admin[1].metric("🚀 Obra Mais Eficiente (Líq/Func)", str(top_obra_eficiencia))
        kpi_cols_admin[2].metric("⭐ Obra com Mais Gratificações", str(top_obra_grat)) 
        kpi_cols_admin[3].metric("🔧 Serviço de Maior Custo", str(top_servico_custo))


    cor_bruta = '#E37026' 
    cor_liquida = '#1E88E5' 
    
    def format_label_brl(value):
        try:
            return f"R$ {float(value):_.2f}".replace('.',',').replace('_','.')
        except (ValueError, TypeError):
            return ""

    if not df_filtrado_resumo.empty:
        if st.session_state['role'] == 'admin' and len(obra_selecionada) > 1 : 
            st.markdown("---")
            st.subheader("Análise por Obra")
            col_obra1, col_obra2 = st.columns(2)
            with col_obra1:
                prod_bruta_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False)
                fig_bar_obra_bruta = px.bar(prod_bruta_obra, x='OBRA', y='PRODUÇÃO BRUTA (R$)', text_auto=True, title="Produção Bruta Total por Obra", labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'})
                fig_bar_obra_bruta.update_traces(
                    texttemplate='%{y:,.2f}', 
                    textposition='outside', 
                    marker_color=cor_bruta,
                    textfont_size=10 
                ) 
                fig_bar_obra_bruta.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide') 
                st.plotly_chart(fig_bar_obra_bruta, use_container_width=True)
            with col_obra2:
                prod_liquida_media_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False)
                fig_bar_obra_liq_media = px.bar(prod_liquida_media_obra, x='OBRA', y='PRODUÇÃO LÍQUIDA (R$)', text_auto=True, title="Produção Líquida Média por Funcionário por Obra", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Prod. Líquida Média / Func. (R$)'})
                fig_bar_obra_liq_media.update_traces(
                    texttemplate='%{y:,.2f}', 
                    textposition='outside', 
                    marker_color=cor_liquida,
                    textfont_size=10
                )
                fig_bar_obra_liq_media.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                st.plotly_chart(fig_bar_obra_liq_media, use_container_width=True)

        st.markdown("---")
        st.subheader("Análise por Funcionário")
        col_func1, col_func2 = st.columns(2)
        with col_func1:
            prod_bruta_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO BRUTA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO BRUTA (R$)', ascending=False).head(15) 
            fig_bar_func_bruta = px.bar(prod_bruta_func, x='Funcionário', y='PRODUÇÃO BRUTA (R$)', text_auto=True, title="Top 15 Funcionários por Produção Bruta", labels={'PRODUÇÃO BRUTA (R$)': 'Produção Bruta (R$)'})
            fig_bar_func_bruta.update_traces(
                texttemplate='%{y:,.2f}', 
                textposition='outside', 
                marker_color=cor_bruta,
                textfont_size=10
            )
            fig_bar_func_bruta.update_layout(xaxis_title=None, xaxis_tickangle=-45, uniformtext_minsize=8, uniformtext_mode='hide') # Rotaciona labels do eixo X
            st.plotly_chart(fig_bar_func_bruta, use_container_width=True)
        with col_func2:
            prod_liquida_func = df_filtrado_resumo.groupby('Funcionário')['PRODUÇÃO LÍQUIDA (R$)'].sum().reset_index().sort_values(by='PRODUÇÃO LÍQUIDA (R$)', ascending=False).head(15) 
            fig_bar_func_liquida = px.bar(prod_liquida_func, x='Funcionário', y='PRODUÇÃO LÍQUIDA (R$)', text_auto=True, title="Top 15 Funcionários por Produção Líquida", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Produção Líquida (R$)'})
            fig_bar_func_liquida.update_traces(
                texttemplate='%{y:,.2f}', 
                textposition='outside', 
                marker_color=cor_liquida,
                textfont_size=10
            )
            fig_bar_func_liquida.update_layout(xaxis_title=None, xaxis_tickangle=-45, uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig_bar_func_liquida, use_container_width=True)

        st.markdown("---")
        st.subheader("Distribuição da Eficiência dos Funcionários")
        fig_hist_liquida = px.histogram(df_filtrado_resumo, x="PRODUÇÃO LÍQUIDA (R$)", nbins=20, title="Distribuição da Produção Líquida por Funcionário", labels={'PRODUÇÃO LÍQUIDA (R$)': 'Faixa de Produção Líquida (R$)', 'count': 'Nº de Funcionários'}, color_discrete_sequence=[cor_liquida], text_auto=True) # Adiciona contagem nas barras
        fig_hist_liquida.update_layout(yaxis_title="Nº de Funcionários", bargap=0.1)
        fig_hist_liquida.update_traces(textposition='outside')
        st.plotly_chart(fig_hist_liquida, use_container_width=True)
        st.caption("Este gráfico mostra quantos funcionários se encaixam em cada faixa de produção líquida.")

    if not df_filtrado_lanc.empty:
        st.markdown("---")
        st.subheader("Produção Bruta ao Longo do Tempo")
        df_filtrado_lanc['Data do Serviço'] = pd.to_datetime(df_filtrado_lanc['Data do Serviço']) 
        prod_dia = df_filtrado_lanc.groupby(df_filtrado_lanc['Data do Serviço'].dt.date)['Valor Parcial'].sum().reset_index()
        prod_dia.rename(columns={'Valor Parcial': 'Produção Bruta Diária (R$)'}, inplace=True)
        fig_line_dia = px.line(prod_dia, x='Data do Serviço', y='Produção Bruta Diária (R$)', markers=True, title="Evolução Diária da Produção Bruta", labels={'Data do Serviço': 'Dia', 'Produção Bruta Diária (R$)': 'Produção Bruta (R$)'})
        fig_line_dia.update_traces(line_color=cor_bruta, marker=dict(color=cor_bruta))
        st.plotly_chart(fig_line_dia, use_container_width=True)

        if st.session_state['role'] == 'admin':
            if not df_filtrado_resumo.empty and len(funcao_selecionada) > 1 : 
                st.markdown("---")
                st.subheader("Análise de Custo x Benefício por Função")
                custo_beneficio_funcao = df_filtrado_resumo.groupby('FUNÇÃO').agg(
                    salario_base_medio=('SALÁRIO BASE (R$)', 'mean'),
                    producao_bruta_media=('PRODUÇÃO BRUTA (R$)', 'mean'),
                    producao_liquida_media=('PRODUÇÃO LÍQUIDA (R$)', 'mean'),
                    contagem=('id', 'nunique') 
                ).reset_index()
                fig_scatter_funcao = px.scatter(custo_beneficio_funcao, x="salario_base_medio", y="producao_liquida_media", size="contagem", color="FUNÇÃO", hover_name="FUNÇÃO", hover_data={'salario_base_medio': ':.2f', 'producao_bruta_media': ':.2f', 'producao_liquida_media': ':.2f', 'contagem': True, 'FUNÇÃO': False}, title="Custo (Salário Base Médio) vs Benefício (Produção Líquida Média) por Função", labels={"salario_base_medio": "Salário Base Médio (R$)", "producao_liquida_media": "Produção Líquida Média (R$)", "contagem": "Nº Funcionários"})
                fig_scatter_funcao.update_layout(xaxis_title="Custo Médio (Salário Base)", yaxis_title="Benefício Médio (Produção Líquida)")
                st.plotly_chart(fig_scatter_funcao, use_container_width=True)
                st.caption("Cada bolha representa uma função. Eixo X = custo médio, Eixo Y = benefício médio. Tamanho da bolha = nº de funcionários.")

            st.markdown("---")
            st.subheader("Análise Detalhada de Serviços e Disciplinas (Custo)")
            col_serv, col_disc = st.columns(2)
            with col_serv:
                serv_custo = df_filtrado_lanc.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig_custo_serv = px.bar(serv_custo, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços por Custo Total (Prod. Bruta)", text_auto=True, labels={'Valor Parcial': 'Custo Total (R$)'})
                fig_custo_serv.update_traces(
                    marker_color=cor_bruta, 
                    texttemplate='R$ %{x:,.2f}', 
                    textposition='outside',
                    textfont_size=10
                )
                fig_custo_serv.update_layout(yaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                st.plotly_chart(fig_custo_serv, use_container_width=True)
            with col_disc:
                disc_custo = df_filtrado_lanc.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).reset_index().sort_values('Valor Parcial', ascending=True)
                fig_custo_disc = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas por Custo Total (Prod. Bruta)", text_auto=True, labels={'Valor Parcial': 'Custo Total (R$)'})
                fig_custo_disc.update_traces(
                    marker_color=cor_bruta, 
                    texttemplate='R$ %{x:,.2f}', 
                    textposition='outside',
                    textfont_size=10
                )
                fig_custo_disc.update_layout(yaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                st.plotly_chart(fig_custo_disc, use_container_width=True)
   
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
                    
                    if obra_selecionada:
                        folhas_enviadas_filtrado = folhas_enviadas_df[folhas_enviadas_df['Obra'].isin(obra_selecionada)]
                    else: 
                        folhas_enviadas_filtrado = pd.DataFrame(columns=folhas_enviadas_df.columns)

                    if not folhas_enviadas_filtrado.empty:
                        media_atraso_por_obra = folhas_enviadas_filtrado.groupby('Obra')['dias_atraso'].mean().round(1).reset_index()
                        fig_atraso = px.bar(media_atraso_por_obra.sort_values(by='dias_atraso', ascending=False), x='Obra', y='dias_atraso', title="Média de Dias de Atraso na Entrega da Folha", text_auto=True, labels={'dias_atraso': 'Média Dias Atraso'}) # Label mais curto
                        fig_atraso.update_traces(
                            marker_color='#E37026', 
                            textposition='outside', 
                            texttemplate='%{y:.1f}'
                        ) 
                        fig_atraso.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
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
                    fig_envios = px.bar(envios_por_obra.sort_values('contador_envios', ascending=False), x='Obra', y='contador_envios', title=f"Total de Envios para Auditoria em {mes_selecionado}", labels={'contador_envios': 'Nº de Envios'}, text_auto=True)
                    fig_envios.update_traces(
                        marker_color='#E37026', 
                        textposition='outside',
                        texttemplate='%{y}'
                    ) 
                    fig_envios.update_layout(xaxis_title=None, uniformtext_minsize=8, uniformtext_mode='hide')
                    st.plotly_chart(fig_envios, use_container_width=True)
                else:
                    st.info("Nenhuma folha enviada para auditoria nas obras selecionadas neste mês.")
        else:
             st.info(f"Nenhuma folha encontrada para o mês {mes_selecionado} para análise de envios.")
