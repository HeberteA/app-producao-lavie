import streamlit as st
import pandas as pd
import plotly.express as px
import db_utils

if 'logged_in' not in st.session_state or not st.session_state.get('logged_in'):
    st.error("Por favor, faça o login primeiro na página principal.")
    st.stop()

engine = db_utils.get_db_connection()
if engine is None:
    st.error("Falha na conexão com o banco de dados. A página não pode ser carregada.")
    st.stop()

# Carregamento otimizado de dados
mes_selecionado = st.session_state.selected_month
lancamentos_df = db_utils.get_lancamentos_do_mes(engine, mes_selecionado)
folhas_df = db_utils.get_folhas_todas(engine) # Pega todas as folhas para a análise histórica de atrasos

st.header("Dashboard de Análise")

df_para_o_dashboard = lancamentos_df.copy()

if st.session_state['role'] == 'user':
    df_para_o_dashboard = df_para_o_dashboard[df_para_o_dashboard['Obra'] == st.session_state['obra_logada']]

if df_para_o_dashboard.empty:
    st.info("Ainda não há lançamentos para analisar neste mês ou para a obra selecionada.")
else:
    st.markdown("#### Filtros Adicionais")
    df_filtrado_dash = df_para_o_dashboard.copy()
    if st.session_state['role'] == 'admin':
        filtro_col1, filtro_col2 = st.columns(2)
        with filtro_col1:
            obras_disponiveis = sorted(df_filtrado_dash['Obra'].unique())
            obras_filtradas_dash = st.multiselect("Filtrar por Obra(s)", options=obras_disponiveis)
            if obras_filtradas_dash:
                df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Obra'].isin(obras_filtradas_dash)]
        with filtro_col2:
            funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
            funcionarios_filtrados_dash = st.multiselect(
                "Filtrar por Funcionário(s)", 
                options=funcionarios_disponiveis, 
                key="dash_func_admin"
            )
            if funcionarios_filtrados_dash:
                df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]

    else: 
        funcionarios_disponiveis = sorted(df_filtrado_dash['Funcionário'].unique())
        funcionarios_filtrados_dash = st.multiselect(
            "Filtrar por Funcionário(s)", 
            options=funcionarios_disponiveis, 
            key="dash_func_user"
        )
        if funcionarios_filtrados_dash:
            df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Funcionário'].isin(funcionarios_filtrados_dash)]

    if df_filtrado_dash.empty:
        st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
    else:
        st.markdown("---")
        total_produzido = df_filtrado_dash['Valor Parcial'].sum()
        top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
        top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()
        
        # Formatação para evitar nomes muito longos nos KPIs
        top_funcionario_display = (top_funcionario[:22] + '...') if len(top_funcionario) > 22 else top_funcionario
        top_servico_display = (top_servico[:22] + '...') if len(top_servico) > 22 else top_servico

        if st.session_state['role'] == 'admin':
            kpi_cols = st.columns(4)
            kpi_cols[0].metric("Produção Total", f"R$ {total_produzido:,.2f}")
            top_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().idxmax()
            kpi_cols[1].metric("Obra Destaque", top_obra)
            kpi_cols[2].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
            kpi_cols[3].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)
        else:
            kpi_cols = st.columns(3)
            kpi_cols[0].metric("Produção Total", f"R$ {total_produzido:,.2f}")
            kpi_cols[1].metric("Funcionário Destaque", top_funcionario_display, help=top_funcionario)
            kpi_cols[2].metric("Serviço de Maior Custo", top_servico_display, help=top_servico)

        st.markdown("---")
        cor_padrao = '#E37026'

        if st.session_state['role'] == 'admin':
            st.markdown("---")
            st.subheader("Análise de Prazos de Entrega")
            folhas_enviadas_df = folhas_df[folhas_df['data_lancamento'].notna()].copy()
        
            if not folhas_enviadas_df.empty:
                folhas_enviadas_df['data_lancamento'] = pd.to_datetime(folhas_enviadas_df['data_lancamento'])
                folhas_enviadas_df['Mes'] = pd.to_datetime(folhas_enviadas_df['Mes'])
                
                folhas_enviadas_df['data_limite'] = folhas_enviadas_df['Mes'].apply(lambda dt: dt.replace(day=23))
                
                folhas_enviadas_df['dias_atraso'] = (folhas_enviadas_df['data_lancamento'].dt.date - folhas_enviadas_df['data_limite'].dt.date).dt.days
                folhas_enviadas_df['dias_atraso'] = folhas_enviadas_df['dias_atraso'].apply(lambda x: max(0, x))
                media_atraso_por_obra = folhas_enviadas_df.groupby('Obra')['dias_atraso'].mean().round(1).reset_index()
                fig_atraso = px.bar(
                    media_atraso_por_obra.sort_values(by='dias_atraso', ascending=False), 
                    x='Obra', y='dias_atraso',
                    title="Média de Dias de Atraso na Entrega da Folha",
                    text_auto=True, labels={'dias_atraso': 'Média de Dias de Atraso', 'Obra': 'Obra'}
                )
                fig_atraso.update_traces(marker_color=cor_padrao , textposition='outside')
                st.plotly_chart(fig_atraso, use_container_width=True)
            else:
                st.info("Ainda não há dados de envio de folhas para analisar os prazos.")
            
            st.markdown("---")
            st.subheader("Análise de Reenvios (Auditoria)")
            
            folhas_mes_selecionado = folhas_df[
                pd.to_datetime(folhas_df['Mes']).dt.strftime('%Y-%m') == mes_selecionado
            ].copy()
            folhas_mes_selecionado = folhas_mes_selecionado[folhas_mes_selecionado['contador_envios'] > 1]
            
            if not folhas_mes_selecionado.empty:
                fig_reenvios = px.bar(
                    folhas_mes_selecionado.sort_values(by='contador_envios', ascending=False),
                    x='Obra', y='contador_envios',
                    title=f"Número de Envios da Folha para Auditoria ({mes_selecionado})",
                    text_auto=True, labels={'contador_envios': 'Nº de Envios', 'Obra': 'Obra'}
                )
                fig_reenvios.update_traces(marker_color=cor_padrao, textposition='outside')
                st.plotly_chart(fig_reenvios, use_container_width=True)
            else:
                st.info(f"Nenhuma obra precisou reenviar a folha para o mês {mes_selecionado}.")

            st.subheader("Produção por Obra")
            prod_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
            fig_bar_obra = px.bar(prod_obra, x='Obra', y='Valor Parcial', text_auto=True, title="Produção Total por Obra",template="plotly_dark")
            fig_bar_obra.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
            st.plotly_chart(fig_bar_obra, use_container_width=True)
        
        st.subheader("Produção por Funcionário")
        prod_func = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().sort_values(ascending=False).reset_index()
        fig_bar_func = px.bar(prod_func, x='Funcionário', y='Valor Parcial', text_auto=True, title="Produção Total por Funcionário")
        fig_bar_func.update_traces(texttemplate='R$ %{y:,.2f}', textposition='outside', marker_color=cor_padrao)
        st.plotly_chart(fig_bar_func, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Análise de Disciplinas")
        col_disc_freq, col_disc_custo = st.columns(2)
        with col_disc_freq:
            disc_freq = df_filtrado_dash['Disciplina'].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
            disc_freq.columns = ['Disciplina', 'Contagem']
            fig_disc_freq = px.bar(disc_freq, y='Disciplina', x='Contagem', orientation='h', title="Top 10 Disciplinas Mais Realizadas")
            fig_disc_freq.update_traces(marker_color=cor_padrao, texttemplate='%{x}', textposition='outside')
            st.plotly_chart(fig_disc_freq, use_container_width=True)
        with col_disc_custo:
            disc_custo = df_filtrado_dash.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_disc_custo = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas de Maior Custo")
            fig_disc_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
            st.plotly_chart(fig_disc_custo, use_container_width=True)

