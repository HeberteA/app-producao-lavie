import streamlit as st
import pandas as pd
import plotly.express as px
import db_utils
import utils
from datetime import date, timedelta

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

    resumo_df = pd.DataFrame() 
    try:
        lanc_producao = pd.DataFrame()
        lanc_gratificacoes = pd.DataFrame()
        if not lancamentos_df.empty:
            lancamentos_df['Valor Parcial'] = lancamentos_df['Valor Parcial'].apply(utils.safe_float)
            lanc_producao = lancamentos_df[lancamentos_df['Disciplina'] != 'GRATIFICAÇÃO']
            lanc_gratificacoes = lancamentos_df[lancamentos_df['Disciplina'] == 'GRATIFICAÇÃO']

        producao_bruta_agg = pd.DataFrame()
        if not lanc_producao.empty:
             producao_bruta_agg = lanc_producao.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
             producao_bruta_agg.rename(columns={'Valor Parcial': 'PRODUÇÃO BRUTA (R$)'}, inplace=True)

        total_gratificacoes_agg = pd.DataFrame()
        if not lanc_gratificacoes.empty:
             total_gratificacoes_agg = lanc_gratificacoes.groupby('funcionario_id')['Valor Parcial'].sum().reset_index()
             total_gratificacoes_agg.rename(columns={'Valor Parcial': 'TOTAL GRATIFICAÇÕES (R$)'}, inplace=True)

        resumo_df_merged = funcionarios_df.copy()
        if not producao_bruta_agg.empty:
            resumo_df_merged = pd.merge(resumo_df_merged, producao_bruta_agg, left_on='id', right_on='funcionario_id', how='left')
            if 'funcionario_id' in resumo_df_merged.columns and 'id' in resumo_df_merged.columns: resumo_df_merged = resumo_df_merged.drop(columns=['funcionario_id'])
        else: resumo_df_merged['PRODUÇÃO BRUTA (R$)'] = 0.0

        if not total_gratificacoes_agg.empty:
            resumo_df_merged = pd.merge(resumo_df_merged, total_gratificacoes_agg, left_on='id', right_on='funcionario_id', how='left', suffixes=('', '_grat'))
            if 'funcionario_id_grat' in resumo_df_merged.columns: resumo_df_merged = resumo_df_merged.drop(columns=['funcionario_id_grat'])
            if 'funcionario_id' in resumo_df_merged.columns and 'id' in resumo_df_merged.columns and 'funcionario_id' != 'id': resumo_df_merged = resumo_df_merged.drop(columns=['funcionario_id'])
        else: resumo_df_merged['TOTAL GRATIFICAÇÕES (R$)'] = 0.0

        resumo_df = resumo_df_merged

        if not resumo_df.empty:
            resumo_df.rename(columns={'SALARIO_BASE': 'SALÁRIO BASE (R$)', 'NOME': 'Funcionário'}, inplace=True)
            resumo_df['SALÁRIO BASE (R$)'] = resumo_df['SALÁRIO BASE (R$)'].fillna(0.0).apply(utils.safe_float)
            resumo_df['PRODUÇÃO BRUTA (R$)'] = resumo_df['PRODUÇÃO BRUTA (R$)'].fillna(0.0).apply(utils.safe_float)
            resumo_df['TOTAL GRATIFICAÇÕES (R$)'] = resumo_df['TOTAL GRATIFICAÇÕES (R$)'].fillna(0.0).apply(utils.safe_float)
            resumo_df['PRODUÇÃO LÍQUIDA (R$)'] = resumo_df.apply(utils.calcular_producao_liquida, axis=1)
            resumo_df['SALÁRIO A RECEBER (R$)'] = resumo_df.apply(utils.calcular_salario_final, axis=1)
            resumo_df['EFICIENCIA (Líquida/Base)'] = 0.0
            mask_salario_positivo = resumo_df['SALÁRIO BASE (R$)'] > 0
            if mask_salario_positivo.any():
                 resumo_df.loc[mask_salario_positivo, 'EFICIENCIA (Líquida/Base)'] = \
                     (resumo_df.loc[mask_salario_positivo, 'PRODUÇÃO LÍQUIDA (R$)'] / resumo_df.loc[mask_salario_positivo, 'SALÁRIO BASE (R$)'])
            resumo_df['EFICIENCIA (Líquida/Base)'] = resumo_df['EFICIENCIA (Líquida/Base)'].fillna(0).replace(float('inf'), 0)

    except KeyError as e:
         st.error(f"Erro ao calcular resumo: Chave não encontrada - {e}. Verifique nomes das colunas.")
         resumo_df = pd.DataFrame() 
    except Exception as e:
         st.error(f"Erro inesperado ao calcular resumo: {e}")
         resumo_df = pd.DataFrame() 

    obra_selecionada_filt = []
    funcao_selecionada_filt = []
    tipo_selecionado_filt = []
    funcionario_selecionado_filt = []

    with st.expander("Filtros do Dashboard", expanded=False):

        obras_disponiveis_filt = sorted(resumo_df['OBRA'].unique()) if not resumo_df.empty and 'OBRA' in resumo_df else []
        funcoes_disponiveis_filt = sorted(resumo_df['FUNÇÃO'].unique()) if not resumo_df.empty and 'FUNÇÃO' in resumo_df else []
        tipos_disponiveis_filt = sorted(resumo_df['TIPO'].unique()) if not resumo_df.empty and 'TIPO' in resumo_df else []
        funcionarios_disponiveis_filt = sorted(resumo_df['Funcionário'].unique()) if not resumo_df.empty and 'Funcionário' in resumo_df else []

        filt_col1, filt_col2, filt_col3, filt_col4 = st.columns(4)

        with filt_col1: 
            if st.session_state['role'] == 'admin':
                if obras_disponiveis_filt:
                    default_obras = st.session_state.get('dash_obras_admin_default', obras_disponiveis_filt)
                    default_obras = [o for o in default_obras if o in obras_disponiveis_filt]
                    if not default_obras: default_obras = obras_disponiveis_filt
                    obra_selecionada_filt = st.multiselect("Obra(s)", options=obras_disponiveis_filt, key="dash_obras_admin_main", default=default_obras)
                    st.session_state['dash_obras_admin_default'] = obra_selecionada_filt
                else: st.info("Nenhuma obra com dados.")
            else:
                obra_selecionada_filt = [st.session_state['obra_logada']]
                st.text_input("Obra", value=st.session_state['obra_logada'], disabled=True)

        with filt_col2:
            funcoes_opts_filtradas_filt = funcoes_disponiveis_filt
            if st.session_state['role'] == 'admin' and obra_selecionada_filt and not resumo_df.empty:
                funcoes_opts_filtradas_filt = sorted(resumo_df[resumo_df['OBRA'].isin(obra_selecionada_filt)]['FUNÇÃO'].unique())

            if funcoes_opts_filtradas_filt:
                default_funcoes = st.session_state.get('dash_funcoes_default', funcoes_opts_filtradas_filt)
                default_funcoes = [f for f in default_funcoes if f in funcoes_opts_filtradas_filt]
                if not default_funcoes: default_funcoes = funcoes_opts_filtradas_filt
                funcao_selecionada_filt = st.multiselect("Função(ões)", options=funcoes_opts_filtradas_filt, key="dash_funcoes_main", default=default_funcoes)
                st.session_state['dash_funcoes_default'] = funcao_selecionada_filt
            else: st.multiselect("Função(ões)", [], disabled=True, placeholder="Ajuste outros filtros")

        with filt_col3:
            if tipos_disponiveis_filt:
                default_tipos = st.session_state.get('dash_tipos_default', tipos_disponiveis_filt)
                default_tipos = [t for t in default_tipos if t in tipos_disponiveis_filt]
                if not default_tipos: default_tipos = tipos_disponiveis_filt
                tipo_selecionado_filt = st.multiselect("Tipo Contrato", options=tipos_disponiveis_filt, key="dash_tipos_main", default=default_tipos)
                st.session_state['dash_tipos_default'] = tipo_selecionado_filt
            else: st.multiselect("Tipo Contrato", [], disabled=True)

        with filt_col4:
            funcionarios_opts_filtrados = []
            if not resumo_df.empty:
                df_temp_func_opts = resumo_df.copy()
                if obra_selecionada_filt: df_temp_func_opts = df_temp_func_opts[df_temp_func_opts['OBRA'].isin(obra_selecionada_filt)]
                if funcao_selecionada_filt: df_temp_func_opts = df_temp_func_opts[df_temp_func_opts['FUNÇÃO'].isin(funcao_selecionada_filt)]
                if tipo_selecionado_filt: df_temp_func_opts = df_temp_func_opts[df_temp_func_opts['TIPO'].isin(tipo_selecionado_filt)]
                funcionarios_opts_filtrados = sorted(df_temp_func_opts['Funcionário'].unique())

            if funcionarios_opts_filtrados:
                 default_funcs = st.session_state.get('dash_funcs_default', [])
                 default_funcs = [f for f in default_funcs if f in funcionarios_opts_filtrados]
                 funcionario_selecionado_filt = st.multiselect("Funcionário(s)", options=funcionarios_opts_filtrados, key="dash_funcs_main", default=default_funcs)
                 st.session_state['dash_funcs_default'] = funcionario_selecionado_filt
            else: st.multiselect("Funcionário(s)", [], disabled=True, placeholder="Ajuste outros filtros")

    df_filtrado_resumo = resumo_df.copy() if not resumo_df.empty else pd.DataFrame(columns=resumo_df.columns if isinstance(resumo_df, pd.DataFrame) else [])
    df_filtrado_lanc = lancamentos_df.copy() if not lancamentos_df.empty else pd.DataFrame(columns=lancamentos_df.columns if isinstance(lancamentos_df, pd.DataFrame) else [])

    if not df_filtrado_resumo.empty: 
        if obra_selecionada_filt: df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['OBRA'].isin(obra_selecionada_filt)]
        if funcao_selecionada_filt: df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['FUNÇÃO'].isin(funcao_selecionada_filt)]
        if tipo_selecionado_filt: df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['TIPO'].isin(tipo_selecionado_filt)]
        if funcionario_selecionado_filt: df_filtrado_resumo = df_filtrado_resumo[df_filtrado_resumo['Funcionário'].isin(funcionario_selecionado_filt)]

    if not df_filtrado_lanc.empty and 'funcionario_id' in df_filtrado_lanc.columns:
        if not df_filtrado_resumo.empty and 'id' in df_filtrado_resumo.columns:
             ids_funcs_filtrados = df_filtrado_resumo['id'].unique()
             df_filtrado_lanc = df_filtrado_lanc[df_filtrado_lanc['funcionario_id'].isin(ids_funcs_filtrados)]
        else: 
             df_filtrado_lanc = pd.DataFrame(columns=df_filtrado_lanc.columns)
    else: 
         df_filtrado_lanc = pd.DataFrame(columns=df_filtrado_lanc.columns)


    if df_filtrado_resumo.empty and not resumo_df.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")

    st.markdown("---")
    total_prod_bruta = df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].sum() if not df_filtrado_resumo.empty else 0
    total_prod_liquida = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].sum() if not df_filtrado_resumo.empty else 0
    total_gratificacoes_kpi = df_filtrado_resumo['TOTAL GRATIFICAÇÕES (R$)'].sum() if not df_filtrado_resumo.empty and 'TOTAL GRATIFICAÇÕES (R$)' in df_filtrado_resumo else 0
    media_prod_liquida_func = df_filtrado_resumo['PRODUÇÃO LÍQUIDA (R$)'].mean() if not df_filtrado_resumo.empty else 0
    top_funcionario_bruta = "N/A"
    if not df_filtrado_resumo.empty and total_prod_bruta > 0:
         try:
             idx_max_bruta = df_filtrado_resumo['PRODUÇÃO BRUTA (R$)'].idxmax()
             if 'Funcionário' in df_filtrado_resumo.columns: top_funcionario_bruta = df_filtrado_resumo.loc[idx_max_bruta, 'Funcionário']
         except KeyError: pass
    top_servico_custo = "N/A"
    lanc_sem_grat = df_filtrado_lanc[df_filtrado_lanc['Disciplina'] != 'GRATIFICAÇÃO'] if not df_filtrado_lanc.empty else pd.DataFrame()
    if not lanc_sem_grat.empty:
        serv_grouped = lanc_sem_grat.groupby('Serviço')['Valor Parcial'].sum()
        if not serv_grouped.empty:
            try: top_servico_custo = serv_grouped.idxmax()
            except ValueError: pass
    num_cols = 5
    kpi_cols = st.columns(num_cols)
    kpi_cols[0].metric("Prod. Bruta Total", utils.format_currency(total_prod_bruta))
    kpi_cols[1].metric("Prod. Líquida Total", utils.format_currency(total_prod_liquida))
    kpi_cols[2].metric("Total Gratificações", utils.format_currency(total_gratificacoes_kpi))
    kpi_cols[3].metric("Prod. Líq. Média/Func.", utils.format_currency(media_prod_liquida_func))
    kpi_cols[4].metric("Func. Destaque", str(top_funcionario_bruta))
    if st.session_state['role'] == 'admin':
        kpi_cols_admin = st.columns(num_cols)
        top_obra_bruta = "N/A"; top_obra_eficiencia = "N/A"; top_obra_grat = "N/A"
        if not df_filtrado_resumo.empty:
            soma_bruta_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO BRUTA (R$)'].sum()
            if not soma_bruta_obra.empty and soma_bruta_obra.sum() > 0:
                 try: top_obra_bruta = soma_bruta_obra.idxmax()
                 except ValueError: pass
            media_liquida_por_obra = df_filtrado_resumo.groupby('OBRA')['PRODUÇÃO LÍQUIDA (R$)'].mean()
            if not media_liquida_por_obra.empty:
                try: top_obra_eficiencia = media_liquida_por_obra.idxmax()
                except ValueError: pass
            soma_grat_obra = df_filtrado_resumo.groupby('OBRA')['TOTAL GRATIFICAÇÕES (R$)'].sum() if 'TOTAL GRATIFICAÇÕES (R$)' in df_filtrado_resumo else pd.Series()
            if not soma_grat_obra.empty and soma_grat_obra.sum() > 0:
                 try: top_obra_grat = soma_grat_obra.idxmax()
                 except ValueError: pass
        kpi_cols_admin[0].metric("Obra Destaque (Bruta)", str(top_obra_bruta))
        kpi_cols_admin[1].metric("Obra Eficiente (Líq/Func)", str(top_obra_eficiencia))
        kpi_cols_admin[2].metric("Obra (Gratificações)", str(top_obra_grat))
        kpi_cols_admin[3].metric("Serviço + Custo", str(top_servico_custo))


    cor_bruta = '#E37026'
    cor_liquida = '#1E88E5'

    def format_label_brl(value):
        try: return f"R$ {float(value):_.2f}".replace('.',',').replace('_','.')
        except (ValueError, TypeError): return ""

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
