import streamlit as st
import pandas as pd
import plotly.express as px
import db_utils
import utils

def render_page():
    
    mes_selecionado = st.session_state.selected_month
    lancamentos_df = db_utils.get_lancamentos_do_mes(mes_selecionado)
    folhas_df = db_utils.get_folhas(mes_selecionado)

    st.header("Dashboard de Análise")

    if lancamentos_df.empty:
        st.info("Ainda não há lançamentos para analisar neste mês.")
    else:
        df_filtrado_dash = lancamentos_df.copy()
        if st.session_state['role'] == 'admin':
            st.markdown("#### Filtros Adicionais")
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
            df_filtrado_dash = df_filtrado_dash[df_filtrado_dash['Obra'] == st.session_state['obra_logada']]
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
            
            if not df_filtrado_dash.empty:
                top_funcionario = df_filtrado_dash.groupby('Funcionário')['Valor Parcial'].sum().idxmax()
                top_servico = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().idxmax()
                if st.session_state['role'] == 'admin':
                    top_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().idxmax()
            else:
                top_funcionario, top_servico, top_obra = "N/A", "N/A", "N/A"
            
            cor_padrao = '#E37026'

            if st.session_state['role'] == 'admin':
                kpi_cols = st.columns(4)
                kpi_cols[0].metric("Produção Total", utils.format_currency(total_produzido))
                top_obra = df_filtrado_dash.groupby('Obra')['Valor Parcial'].sum().idxmax()
                kpi_cols[1].metric("Obra Destaque", top_obra)
                kpi_cols[2].metric("Funcionário Destaque", top_funcionario)
                kpi_cols[3].metric("Serviço de Maior Custo", top_servico)
            else:
                kpi_cols = st.columns(3)
                kpi_cols[0].metric("Produção Total", utils.format_currency(total_produzido))
                kpi_cols[1].metric("Funcionário Destaque", top_funcionario)
                kpi_cols[2].metric("Serviço de Maior Custo", top_servico)

            st.markdown("---")
            
            if st.session_state['role'] == 'admin':
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
                        title="Média de Dias de Atraso na Entrega da Folha", text_auto=True,
                        labels={'dias_atraso': 'Média de Dias de Atraso', 'Obra': 'Obra'}
                    )
                    fig_atraso.update_traces(marker_color=cor_padrao , textposition='outside')
                    st.plotly_chart(fig_atraso, use_container_width=True)
                else:
                    st.info("Ainda não há dados de envio de folhas para analisar os prazos.")

                st.subheader("Análise de Envios para Auditoria")
                if not folhas_df.empty:
                    envios_por_obra = folhas_df.groupby('Obra')['contador_envios'].sum().reset_index()
                    fig_envios = px.bar(
                        envios_por_obra.sort_values('contador_envios', ascending=False),
                        x='Obra', y='contador_envios',
                        title=f"Total de Envios para Auditoria em {mes_selecionado}",
                        labels={'contador_envios': 'Número de Envios', 'Obra': 'Obra'},
                        text_auto=True
                    )
                    fig_envios.update_traces(marker_color=cor_padrao, textposition='outside')
                    st.plotly_chart(fig_envios, use_container_width=True)
                else:
                    st.info("Nenhuma folha enviada para auditoria neste mês.")

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
            st.subheader("Produção ao Longo do Tempo")
            df_filtrado_dash['Data'] = pd.to_datetime(df_filtrado_dash['Data'])
            prod_dia = df_filtrado_dash.set_index('Data').resample('D')['Valor Parcial'].sum().reset_index()
            fig_line = px.line(prod_dia, x='Data', y='Valor Parcial', markers=True, title="Evolução Diária da Produção")
            fig_line.update_traces(line_color=cor_padrao, marker=dict(color=cor_padrao))
            st.plotly_chart(fig_line, use_container_width=True)
        
            if st.session_state['role'] == 'admin':
                st.markdown("---")
                st.subheader("Análise de Serviços e Disciplinas")
                col_serv, col_disc = st.columns(2)
                with col_serv:
                    serv_custo = df_filtrado_dash.groupby('Serviço')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                    fig_custo = px.bar(serv_custo, y='Serviço', x='Valor Parcial', orientation='h', title="Top 10 Serviços de Maior Custo", text_auto=True)
                    fig_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                    st.plotly_chart(fig_custo, use_container_width=True)
                with col_disc:
                    disc_custo = df_filtrado_dash.groupby('Disciplina')['Valor Parcial'].sum().nlargest(10).sort_values(ascending=True).reset_index()
                    fig_disc_custo = px.bar(disc_custo, y='Disciplina', x='Valor Parcial', orientation='h', title="Top 10 Disciplinas de Maior Custo")
                    fig_disc_custo.update_traces(marker_color=cor_padrao, texttemplate='R$ %{x:,.2f}', textposition='outside')
                    st.plotly_chart(fig_disc_custo, use_container_width=True)

