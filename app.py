"""
Detector de Hype
Aplicativo Streamlit para analisar o "hype" de um termo de pesquisa usando
dados do TikTok e do Google Trends.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import utils  

TEMA_COR = "#E02E30"

st.set_page_config(
    page_title="Detector de Hype", 
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ESTILOS CSS 
try:
    img_base64 = base64.b64encode(open("capa.png", "rb").read()).decode()
except FileNotFoundError:
    st.error("Erro: Arquivo 'capa.png' não encontrado. Certifique-se de que ele está no mesmo diretório.")
    img_base64 = "" 

css_styles = utils.load_css_styles(img_base64, TEMA_COR)
st.markdown(css_styles, unsafe_allow_html=True)


def main():
    """Função principal que renderiza a interface do Streamlit."""
    
    # CAPA
    st.markdown("""
    <div class="hype-cover">
        <h1>Detector de Hype</h1>
    </div>
    """, unsafe_allow_html=True)

    # ENTRADA DE PESQUISA
    search_term = st.text_input("Digite o termo a ser analisado", key="search_term")

    if not search_term:
        st.info("Por favor, digite um termo na barra de pesquisa acima para começar a análise.")
        return

    search_term = search_term.strip()

    # FILTRO (Google Trends)
    time_label = "Últimos 12 meses"
    time_value = "today 12-m"
    geo_value = "BR"


    # COLETA E PROCESSAMENTO DE DADOS 
    
    videos = None
    df = pd.DataFrame()
    trends_results_display = None
    trends_results_ihp = None
    growth_data = None
    trends_ihp_metrics = None

    with st.spinner(f"Coletando e analisando dados para '{search_term}'..."):
        
        # TIKTOK
        videos = utils.fetch_tiktok_data(search_term)
        
        if videos:
            df = pd.DataFrame(videos)
            
            # Garante que as colunas necessárias existam
            required_cols = ['create_time', 'play_count', 'digg_count', 'comment_count', 'share_count', 'desc', 'cover', 'author_user_id', 'id', 'play']
            for col in required_cols:
                if col not in df.columns:
                    if col == 'create_time': df[col] = pd.NA
                    elif col in ['play_count', 'digg_count', 'comment_count', 'share_count']: df[col] = 0
                    else: df[col] = ""
            
            # Conversão de tipos e tratamento de nulos
            df['create_time'] = pd.to_datetime(df['create_time'], unit='s', errors='coerce')
            for col in ['play_count', 'digg_count', 'comment_count', 'share_count']:
                df[col] = df[col].fillna(0).astype(int)
                
            growth_data = utils.calculate_growth_metrics(df)

        # GOOGLE TRENDS
        trends_results_display = utils.fetch_google_trends(search_term, time_value, geo_value)
        trends_df_time_display = trends_results_display.get('df_time') if isinstance(trends_results_display, dict) else None

        # Calcula métricas 14d vs 60d a partir do mesmo dataframe
        trends_ihp_metrics = utils.calculate_trends_metrics(trends_df_time_display)


        # CÁLCULO FINAL DO IHP 
        ihp_metrics = utils.calculate_ihp(growth_data, trends_ihp_metrics)
        ihp_total_score = ihp_metrics['ihp_total_score']
        recommendation = utils.get_ihp_recommendation(ihp_total_score)


    # EXIBIÇÃO DO IHP E RECOMENDAÇÃO 
    
    st.markdown("<h3>Índice de Hype do Produto (IHP)</h3>", unsafe_allow_html=True)
    
    # Cards do IHP
    delta_text = (
        f"Trends: {ihp_metrics['trends_momentum']:.0f} | "
        f"Views: {ihp_metrics['views_momentum']:.0f} | "
        f"Likes: {ihp_metrics['likes_momentum']:.0f} | "
        f"Coments: {ihp_metrics['comments_momentum']:.0f} | "
        f"Shares: {ihp_metrics['shares_momentum']:.0f}"
    )


    col_main, col_tooltip = st.columns([4.2, 0.5])

    with col_main:
        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.markdown(
                f"<div style='font-size:2.4rem; font-weight:800; color:{TEMA_COR}; margin-bottom:6px;'>"
                f"{ihp_total_score:.0f}/200</div>",
                unsafe_allow_html=True
            )

            st.markdown(
                f"<div style='color:#666; font-size:0.95rem;' title='{delta_text}'>"
                f"{delta_text}</div>",
                unsafe_allow_html=True
            )

            if not growth_data:
                st.markdown(
                    "<div class='warning-card'>A pontuação do TikTok é 0 (API falhou ou não retornou dados).</div>",
                    unsafe_allow_html=True
                )
            if not trends_ihp_metrics:
                st.markdown(
                    "<div class='warning-card'>A pontuação do Google Trends é 0 (não há dados de 14/60 dias).</div>",
                    unsafe_allow_html=True
                )

        with right_col:
            st.markdown("<div class='recommendation-title'>Interpretação</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='recommendation-text'>{recommendation}</div>", unsafe_allow_html=True)


    # Popover de Ajuda
    with col_tooltip:
        st.popover("❓").markdown("""
            ##### O que é o IHP?
            O IHP (0-200) mede o **momentum** de um produto. Ele compara a média de engajamento dos últimos 14 dias com a média dos últimos 60 dias.
            
            - **Pontuação 200:** Interesse recente é **o dobro** (ou mais) do histórico.
            - **Pontuação 100:** Significa que o interesse recente (14d) é **igual** ao histórico (60d).
            - **Pontuação < 100:** Interesse recente é **menor** que o histórico.

            ---
            **Peso de Cada Métrica:**
            * **Google Trends:** 30%
            * **TikTok Views:** 25%
            * **TikTok Likes:** 20%
            * **TikTok Comentários:** 15%
            * **TikTok Compartilhamentos:** 10%
            """)


    # ABAS TIKTOK E TRENDS
    
    st.markdown("<br>", unsafe_allow_html=True)
    tab_tiktok, tab_trends = st.tabs(["Análise do TikTok", "Análise do Google Trends"])

    # --- ABA TIKTOK ---
    with tab_tiktok:
        if videos is None:
            st.warning("Não foi possível conectar à API do TikTok ou obter dados.")
        elif not videos:
            st.warning(f"Nenhum vídeo encontrado para '{search_term}' no TikTok.")
        else:
            # Métricas
            tiktok_views = df['play_count'].sum()
            tiktok_likes = df['digg_count'].sum()
            tiktok_comments = df['comment_count'].sum()
            tiktok_shares = df['share_count'].sum()

            st.header(f"Engajamento para '{search_term}'")
            c1, c2, c3, c4 = st.columns(4)
            
            c1.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Views</div>
                <div class="metric-value-white">{utils.format_number(tiktok_views)}</div>
            </div>""", unsafe_allow_html=True)
            c2.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Likes</div>
                <div class="metric-value-white">{utils.format_number(tiktok_likes)}</div>
            </div>""", unsafe_allow_html=True)
            c3.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Comentários</div>
                <div class="metric-value-white">{utils.format_number(tiktok_comments)}</div>
            </div>""", unsafe_allow_html=True)
            c4.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Compartilhamentos</div>
                <div class="metric-value-white">{utils.format_number(tiktok_shares)}</div>
            </div>""", unsafe_allow_html=True)

            # Gráfico
            df['date'] = df['create_time'].dt.to_period('D').dt.to_timestamp()
            df_time = (df.groupby('date', as_index=False)['play_count'].sum().sort_values('date'))

            if not df_time.empty:
                fig = px.line(df_time, x='date', y='play_count', markers=True, 
                                title="Visualizações ao longo do Tempo", 
                                labels={'date': 'Data', 'play_count': 'Visualizações'}, 
                                color_discrete_sequence=[TEMA_COR])
                st.plotly_chart(fig, use_container_width=True)

            # Tabela de Médias
            if growth_data and (growth_data['views_14d_avg'] > 0 or growth_data['views_60d_avg'] > 0):
                st.subheader("Análise de Momentum")
                st.markdown(f"""
                    <table class="thirtyd-table">
                        <thead>
                            <tr>
                                <th>Médias</th>
                                <th>Views</th>
                                <th>Likes</th>
                                <th>Comentários</th>
                                <th>Compartilhamentos</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Últimos 14 dias</td>
                                <td>{utils.format_number(growth_data['views_14d_avg'])}</td>
                                <td>{utils.format_number(growth_data['likes_14d_avg'])}</td>
                                <td>{utils.format_number(growth_data['comments_14d_avg'])}</td>
                                <td>{utils.format_number(growth_data['shares_14d_avg'])}</td>
                            </tr>
                            <tr>
                                <td>Últimos 60 dias</td>
                                <td>{utils.format_number(growth_data['views_60d_avg'])}</td>
                                <td>{utils.format_number(growth_data['likes_60d_avg'])}</td>
                                <td>{utils.format_number(growth_data['comments_60d_avg'])}</td>
                                <td>{utils.format_number(growth_data['shares_60d_avg'])}</td>
                            </tr>
                        </tbody>
                    </table>
                """, unsafe_allow_html=True)
            else:
                st.info("Não há dados de engajamento nos últimos 60 dias para calcular as médias.")

            st.divider()
            
            # Vídeos Mais Populares
            st.subheader("Vídeos Mais Populares")
            df['link'] = df.apply(lambda row: row.get('play', '') or f"https://www.tiktok.com/video/{row.get('id', '')}", axis=1)
            top_videos = df.sort_values('play_count', ascending=False).head(8)
            num_cols = 4

            for i in range(0, len(top_videos), num_cols):
                cols = st.columns(num_cols)
                subset = top_videos.iloc[i:i + num_cols]
                for col, (_, row) in zip(cols, subset.iterrows()):
                    link = row['link']
                    cover_url = row['cover'] or 'https://via.placeholder.com/250x250?text=Capa+Indisponível'
                    
                    views = utils.format_number(row['play_count'])
                    likes = utils.format_number(row['digg_count'])
                    
                    with col:
                        st.markdown(f"""
                        <div style="text-align:center; margin-bottom: 15px;">
                            <a href="{link}" target="_blank">
                                <img src="{cover_url}" 
                                    style="width:100%; height: 250px; object-fit: cover; border-radius:10px;" alt="Capa do Vídeo"/>
                            </a>
                            <div style="margin-top:5px; font-size:0.9rem;">
                                👀 {views} &nbsp;|&nbsp; ❤️ {likes}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # --- ABA GOOGLE TRENDS ---
    with tab_trends:
        st.header(f"Interesse de Pesquisa para '{search_term}'")

        if 'error' in trends_results_display:
            st.error(f"**Erro no Google Trends:** {trends_results_display['error']}")
            st.info(f"Termo: **{search_term}** | Período: **{time_label}** | Região: **{geo_value}**")
        
        elif trends_df_time_display is not None and not trends_df_time_display.empty:
            
            interest_mean_period = trends_df_time_display['interest'].mean()
            
            # Pega as médias do IHP (14d/60d)
            avg_14d = trends_ihp_metrics.get('trends_14d_avg', 0) if trends_ihp_metrics else 0
            avg_60d = trends_ihp_metrics.get('trends_60d_avg', 0) if trends_ihp_metrics else 0

            # --- CARDS ---
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"""
            <div class="metric-card-trends">
                <div class="metric-label-trends">Interesse Médio ({time_label})</div>
                <div class="metric-value-trends">{interest_mean_period:.0f}/100</div>
            </div>
            """, unsafe_allow_html=True)
            c2.markdown(f"""
            <div class="metric-card-trends">
                <div class="metric-label-trends">Média (Últimos 14 dias)</div>
                <div class="metric-value-trends">{avg_14d:.0f}/100</div>
            </div>
            """, unsafe_allow_html=True)
            c3.markdown(f"""
            <div class="metric-card-trends">
                <div class="metric-label-trends">Média (Últimos 60 dias)</div>
                <div class="metric-value-trends">{avg_60d:.0f}/100</div>
            </div>
            """, unsafe_allow_html=True)
            
            
            fig = px.line(trends_df_time_display, x='date', y='interest', markers=True,
                            title=f"Interesse ao longo do tempo",
                            labels={'date': 'Data', 'interest': 'Nível de Interesse'},
                            color_discrete_sequence=[TEMA_COR]) 
            st.plotly_chart(fig, use_container_width=True)

            csv_trends = trends_df_time_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Dados da Série Temporal (CSV)",
                data=csv_trends,
                file_name=f'trends_interest_series_{search_term}.csv',
                mime='text/csv',
                key='download-trends-series')

            # --- Interesse por Região ---
            df_region = trends_results_display.get('df_region')
            
            if isinstance(df_region, pd.DataFrame) and not df_region.empty:
                st.subheader("Interesse por Estado")
                st.dataframe(
                    df_region.head(10).reset_index(), 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "interest": st.column_config.ProgressColumn(
                            "Nível de Interesse (0-100)", 
                            format="%d", 
                            min_value=0, 
                            max_value=100, 
                            width="large"
                        ),
                        "Região": "Estado"
                    }
                )

        else:
            st.info("Não foram encontrados dados no Google Trends para o termo pesquisado.")


# --- PONTO DE ENTRADA  ---
if __name__ == "__main__":
    main()