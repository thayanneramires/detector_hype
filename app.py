"""
Detector de Hype de Produto
Aplicativo Streamlit para analisar o "hype" de um termo de pesquisa usando
dados do TikTok e do Google Trends. O aplicativo calcula um 
Índice de Hype do Produto (IHP) e exibe métricas detalhadas.
"""

import streamlit as st
import requests
import math
import pandas as pd
import plotly.express as px
from pytrends.request import TrendReq
from datetime import datetime, date, timedelta
import time
import base64
import io

# --- 1. CONFIGURAÇÕES GLOBAIS E CHAVES DE API ---

TEMA_COR = "#E02E30"

# Carrega as chaves de API do TikTok
try:
    API_KEY = st.secrets["tiktok_api"]["key"]
    TIKTOK_HOST = st.secrets["tiktok_api"]["host"]
except Exception as e:
    st.error(f"ERRO: As chaves da API do TikTok não foram encontradas nos segredos. {e}")
    API_KEY = "dummy_key"
    TIKTOK_HOST = "dummy_host"

# --- 2. CONFIGURAÇÃO DA PÁGINA STREAMLIT ---

st.set_page_config(
    page_title="Detector de Hype", 
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 3. ESTILOS CSS CONSOLIDADOS ---

# Carrega a imagem da capa (se existir)
try:
    with open("capa.png", "rb") as f:
        img_bytes = f.read()
    img_base64 = base64.b64encode(img_bytes).decode()
except FileNotFoundError:
    # Placeholder 1x1 transparente se a imagem não for encontrada
    img_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

st.markdown(f"""
<style>
    /* === RESET E OCULTA ELEMENTOS PADRÃO === */
    [data-testid="stSidebar"] {{ display: none !important; }}
    #MainMenu, footer {{ visibility: hidden; }}
    
    /* === CAPA (HEADER) === */
    .hype-cover {{
        position: relative;
        width: 100%;
        height: 220px;
        border-radius: 12px;
        background-image: url('data:image/png;base64,{img_base64}');
        background-size: cover;
        background-position: center;
        display: flex;
        align-items: center;
        justify-content: flex-start; 
        margin-bottom: 30px;
        padding-left: 5%;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }}
    .hype-cover::after {{
        content: "";
        position: absolute;
        top: 0; left: 0;
        width: 100%; height: 100%;
        border-radius: 12px;
        background: rgba(0, 0, 0, 0.4); 
    }}
    .hype-cover h1 {{
        position: relative;
        color: "#E02E30";
        font-size: 2.5rem;
        font-weight: 800;
        text-align: left !important;
        z-index: 2;
        margin: 0;
    }}

    /* === CARDS DE MÉTRICA (PADRÃO STREAMLIT - 30 DIAS) === */
    [data-testid="stMetric"] {{
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 12px; 
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
        height: 100%;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.9rem; 
        color: #555; 
        font-weight: 500;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 2.5rem; 
        font-weight: 700; 
        color: {TEMA_COR}; /* COR DO TEMA */
    }}

    /* === ESTILO UNIFICADO DE CARD (IHP, TIKTOK TOTALS, GOOGLE TRENDS) === */
    .metric-card, .metric-card-trends {{
        background-color: #ffffff;
        border: 1px solid {TEMA_COR}; /* AGORA SEMPRE VERMELHO (TEMA_COR) */
        border-radius: 12px; 
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
        /* Mantemos o transition para os efeitos de hover */
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        height: 100%; 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}

    /* Efeito de hover que usa a COR DO TEMA na borda */
    .metric-card:hover, .metric-card-trends:hover {{
        transform: translateY(-4px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        border-color: {TEMA_COR}; /* Destaque em vermelho no hover */
    }}

    /* Valor principal do IHP (agora em vermelho) */
    .metric-card .metric-value {{
        font-size: 28px;
        font-weight: 700;
        color: {TEMA_COR}; /* COR DO TEMA */
        margin-bottom: 6px;
    }}

    /* Labels (subtítulos dos cards) */
    .metric-card .metric-label {{
        font-size: 13px;
        color: #555; 
    }}

    /* Valor dos cards de TikTok Totais (agora em preto) */
    .metric-card .metric-value-white {{
        font-size: 28px;
        font-weight: 700;
        color: #222222; /* Texto escuro para fundo claro */
        margin-bottom: 6px;
    }}

    /* Labels dos cards do Google Trends */
    .metric-card-trends .metric-label-trends {{
        font-size: 13px;
        color: #555;
        margin-bottom: 2px;
        font-weight: 500;
    }}

    /* Valores dos cards do Google Trends */
    .metric-card-trends .metric-value-trends {{
        font-size: 20px;
        font-weight: 700;
        color: {TEMA_COR}; /* COR DO TEMA */
    }}

    /* === BLOCO DE RECOMENDAÇÃO (IHP) === */
    .recommendation-box {{
        background-color: #ffffff;
        border: 1px solid #e0e0e0; /* Borda padronizada */
        border-radius: 12px; 
        padding: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
        height: 100%; 
    }}
    .recommendation-title {{
        font-size: 1.2rem;
        font-weight: 700;
        color: #222;
        margin-bottom: 10px;
        border-bottom: 2px solid {TEMA_COR}; 
        padding-bottom: 5px;
    }}
    .recommendation-text {{
        font-size: 1.1rem;
        font-weight: 600;
        color: {TEMA_COR}; 
        margin-bottom: 10px;
    }}

    /* === TABELA DE MÉDIAS (TIKTOK) - TEMA CLARO === */
    .thirtyd-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
        font-size: 15px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    .thirtyd-table thead th {{
        background-color: #f8f9fa; 
        color: #333; 
        font-weight: 600;
        text-align: right; 
        padding: 12px 15px;
        border-bottom: 2px solid #dee2e6; 
    }}
    .thirtyd-table thead th:first-child {{
        text-align: left;
    }}
    .thirtyd-table tbody td {{
        color: #555; 
        padding: 12px 15px;
        border-bottom: 1px solid #f0f0f0; 
        text-align: right; 
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 15px;
        background-color: #ffffff;
    }}
    .thirtyd-table tbody tr:last-child td {{
        border-bottom: none; 
    }}
    .thirtyd-table tbody tr:hover td {{
        background-color: #f9f9f9; 
    }}
    .thirtyd-table td:first-child {{
        font-weight: 600;
        color: #222; 
        text-align: left;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
</style>
""", unsafe_allow_html=True)

# --- 4. FUNÇÕES AUXILIARES ---

def format_number(num):
    """
    Formata números grandes para K, M, B, ou arredonda números menores.

    :param num: O número (int ou float) a ser formatado.
    :return: String formatada.
    """
    if num >= 1_000_000_000:
        return f"{(num / 1_000_000_000):.1f}".replace('.0', '') + 'B'
    if num >= 1_000_000:
        return f"{(num / 1_000_000):.1f}".replace('.0', '') + 'M'
    if num >= 1_000:
        return f"{(num / 1_000):.1f}".replace('.0', '') + 'K'
    
    # Arredonda números menores que 1000 para o inteiro mais próximo
    return f"{num:.0f}"


# --- 5. FUNÇÕES DE BUSCA (APIs) ---

@st.cache_data(ttl=3600)
def fetch_tiktok_data(term):
    """
    Busca dados na API do TikTok com cache de 1 hora.

    :param term: O termo de pesquisa.
    :return: Lista de vídeos (dict) ou None se falhar.
    """
    if not API_KEY or TIKTOK_HOST == "dummy_host":
        st.warning("Chaves da API do TikTok não configuradas. Pulando busca no TikTok.")
        return None

    url = f"https://{TIKTOK_HOST}/feed/search?keywords={term}&count=20"
    headers = {
        'x-rapidapi-key': API_KEY,
        'x-rapidapi-host': TIKTOK_HOST
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()  # Levanta erro para status HTTP 4xx/5xx
        data = res.json()
        if data.get("code") == 0 and data.get("data", {}).get("videos"):
            return data["data"]["videos"]
        return []  # Retorna lista vazia se a API respondeu mas não há vídeos
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar à API do TikTok: {e}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado ao processar dados do TikTok: {e}")
        return None


@st.cache_data(ttl=3600)
def fetch_google_trends(term, time_period, geo):
    """
    Busca dados no Google Trends com cache de 1 hora.

    :param term: O termo de pesquisa (string).
    :param time_period: O período de tempo (ex: 'today 12-m').
    :param geo: A localização (ex: 'BR').
    :return: Um dicionário contendo DataFrames ou uma chave 'error'.
    """
    try:
        # AJUSTE: Adiciona retries=3 e backoff_factor=1 para lidar com erros 429
        pytrends = TrendReq(hl='pt-BR', tz=360, retries=3, backoff_factor=1)
        
        keywords = [term]
        pytrends.build_payload(keywords, cat=0, timeframe=time_period, geo=geo, gprop='')
        time.sleep(1)  # Pequena pausa para evitar rate limit

        df_time = pytrends.interest_over_time()

        if df_time.empty or term not in df_time.columns or df_time[term].max() == 0:
            return {'error': f"A pesquisa de série temporal do Google Trends não retornou dados para '{term}'."}

        if 'isPartial' in df_time.columns:
            df_time = df_time.drop(columns=['isPartial'])
        df_time.columns = ['interest']
        df_time = df_time.reset_index()

        # Só busca por região se a geolocalização for um país (ex: 'BR')
        df_region = pd.DataFrame()
        if len(geo) <= 2:
            df_region = pytrends.interest_by_region(resolution='REGION', inc_low_vol=True, inc_geo_code=False)
            if not df_region.empty:
                df_region.columns = ['interest']
                df_region = df_region.sort_values(by='interest', ascending=False).reset_index().rename(columns={'geoName': 'Região'})
                df_region.set_index('Região', inplace=True)

        related_queries = pytrends.related_queries()
        top_queries = related_queries.get(term, {}).get('top', pd.DataFrame())
        rising_queries = related_queries.get(term, {}).get('rising', pd.DataFrame())

        return {
            'df_time': df_time,
            'df_region': df_region,
            'top_queries': top_queries,
            'rising_queries': rising_queries
        }

    except Exception as e:
        return {'error': f"Erro na biblioteca PyTrends (Google Trends). Detalhe: {e}"}


# --- 6. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def calculate_growth_metrics(df):
    """
    Calcula as métricas de média diária (14d vs 60d) para o IHP.

    :param df: DataFrame de vídeos do TikTok.
    :return: Dicionário com as métricas de média, ou None se o df for inválido.
    """
    if df.empty or 'create_time' not in df.columns or 'play_count' not in df.columns:
        return None

    today = datetime.now()
    start_14d = today - timedelta(days=14)
    start_60d = today - timedelta(days=60)

    df_14d = df[df['create_time'] >= start_14d]
    df_60d = df[df['create_time'] >= start_60d]

    # Somas
    views_sum_14d = df_14d['play_count'].sum()
    views_sum_60d = df_60d['play_count'].sum()
    likes_sum_14d = df_14d['digg_count'].sum() if 'digg_count' in df_14d.columns else 0
    likes_sum_60d = df_60d['digg_count'].sum() if 'digg_count' in df_60d.columns else 0
    comments_sum_14d = df_14d['comment_count'].sum() if 'comment_count' in df_14d.columns else 0
    comments_sum_60d = df_60d['comment_count'].sum() if 'comment_count' in df_60d.columns else 0
    shares_sum_14d = df_14d['share_count'].sum() if 'share_count' in df_14d.columns else 0
    shares_sum_60d = df_60d['share_count'].sum() if 'share_count' in df_60d.columns else 0

    # Médias diárias (Soma / N dias).
    # Usamos 14.0 e 60.0 fixos para normalizar a média diária.
    return {
        'views_14d_avg': views_sum_14d / 14.0,
        'views_60d_avg': views_sum_60d / 60.0,
        'likes_14d_avg': likes_sum_14d / 14.0,
        'likes_60d_avg': likes_sum_60d / 60.0,
        'comments_14d_avg': comments_sum_14d / 14.0,
        'comments_60d_avg': comments_sum_60d / 60.0,
        'shares_14d_avg': shares_sum_14d / 14.0,
        'shares_60d_avg': shares_sum_60d / 60.0,
    }


def calculate_trends_metrics(df_trends):
    """
    Calcula as médias de 14d e 60d do Google Trends para o IHP.

    :param df_trends: DataFrame do Google Trends (deve cobrir 60d).
    :return: Dicionário com as métricas de média, ou None se o df for inválido.
    """
    if df_trends is None or df_trends.empty:
        return None

    today = datetime.now().date()
    start_14d = today - timedelta(days=14)
    start_60d = today - timedelta(days=60)

    # Converte 'date' para date objects para comparação
    df_trends['date_only'] = pd.to_datetime(df_trends['date']).dt.date

    df_14d = df_trends[df_trends['date_only'] >= start_14d]
    df_60d = df_trends[df_trends['date_only'] >= start_60d]

    # Calcula a média de 'interest' para os períodos
    trends_14d_avg = df_14d['interest'].mean() if not df_14d.empty else 0
    trends_60d_avg = df_60d['interest'].mean() if not df_60d.empty else 0

    return {
        'trends_14d_avg': trends_14d_avg,
        'trends_60d_avg': trends_60d_avg,
    }


# --- 7. FUNÇÕES DE LÓGICA (IHP) ---

def get_momentum_score(recent_avg, historical_avg):
    """
    Calcula o 'momentum' (0-200) comparando a média recente (14d)
    com a histórica (60d).

    :param recent_avg: Média dos últimos 14 dias.
    :param historical_avg: Média dos últimos 60 dias.
    :return: Pontuação de momentum (float) entre 0 e 200.
    """
    # Trata divisão por zero: se o histórico era 0 e o recente é > 0, é hype máximo.
    if historical_avg == 0:
        return 200.0 if recent_avg > 0 else 0.0

    ratio = recent_avg / historical_avg
    capped_ratio = min(ratio, 2.0)  # Limita (CAP) em 2x (200%)
    score = capped_ratio * 100  # Escala para 0-200
    return score


def calculate_ihp(tiktok_metrics, trends_metrics):
    """
    Calcula o Índice de Hype do Produto (IHP) com base no momentum
    de 14d vs 60d e pesos pré-definidos.

    :param tiktok_metrics: Dicionário retornado por `calculate_growth_metrics`.
    :param trends_metrics: Dicionário retornado por `calculate_trends_metrics`.
    :return: Dicionário com a pontuação IHP final e os scores de momentum.
    """
    # 1. Pega os dados do TikTok. Se não existirem, usa 0.
    tm = tiktok_metrics or {}
    views_14d_avg = tm.get('views_14d_avg', 0)
    views_60d_avg = tm.get('views_60d_avg', 0)
    likes_14d_avg = tm.get('likes_14d_avg', 0)
    likes_60d_avg = tm.get('likes_60d_avg', 0)
    comments_14d_avg = tm.get('comments_14d_avg', 0)
    comments_60d_avg = tm.get('comments_60d_avg', 0)
    shares_14d_avg = tm.get('shares_14d_avg', 0)
    shares_60d_avg = tm.get('shares_60d_avg', 0)

    # 2. Pega os dados do Trends. Se não existirem, usa 0.
    trm = trends_metrics or {}
    trends_14d_avg = trm.get('trends_14d_avg', 0)
    trends_60d_avg = trm.get('trends_60d_avg', 0)

    # 3. Calcula o Momentum Score (0-200) para cada dimensão
    T_m = get_momentum_score(trends_14d_avg, trends_60d_avg)
    V_m = get_momentum_score(views_14d_avg, views_60d_avg)
    L_m = get_momentum_score(likes_14d_avg, likes_60d_avg)
    C_m = get_momentum_score(comments_14d_avg, comments_60d_avg)
    S_m = get_momentum_score(shares_14d_avg, shares_60d_avg)

    # 4. Aplica os pesos e calcula o IHP final (escala 0-200)
    ihp_total_score = (
        (T_m * 0.30) +
        (V_m * 0.25) +
        (L_m * 0.20) +
        (C_m * 0.15) +
        (S_m * 0.10)
    )

    return {
        'ihp_total_score': ihp_total_score,
        'trends_momentum': T_m,
        'views_momentum': V_m,
        'likes_momentum': L_m,
        'comments_momentum': C_m,
        'shares_momentum': S_m,
    }


def get_ihp_recommendation(ihp_total_score):
    """
    Retorna uma string de recomendação baseada na pontuação IHP (0-200).

    :param ihp_total_score: A pontuação final do IHP.
    :return: Uma string de interpretação.
    """
    if ihp_total_score >= 150:
        return "Viral — tendência explosiva"
    elif ihp_total_score >= 100:
        return "Em alta — hype crescendo"
    elif ihp_total_score >= 60:
        return "Estável — atenção sustentada"
    else:
        return "Interesse em queda — produto esfriando"


# --- 8. INTERFACE PRINCIPAL E FLUXO DO APLICATIVO ---

def main():
    """Função principal que renderiza a interface do Streamlit."""
    
    # --- CAPA (HEADER) ---
    st.markdown("""
    <div class="hype-cover">
        <h1>Detector de Hype</h1>
    </div>
    """, unsafe_allow_html=True)

    # --- ENTRADA DE PESQUISA ---
    search_term = st.text_input("Digite o termo a ser analisado", key="search_term")

    if not search_term:
        st.info("Por favor, digite um termo na barra de pesquisa acima para começar a análise.")
        return

    search_term = search_term.strip()

    # --- OPÇÕES DE FILTRO (Google Trends) ---
    col_time, col_geo = st.columns(2)
    time_period_options = {
        "Últimos 12 meses": "today 12-m",
        "Últimos 5 anos": "today 5-y",
        "Desde 2004 (Histórico)": "all"
    }
    time_label = col_time.selectbox(
        "Período de Análise (Google Trends):",
        list(time_period_options.keys()),
        index=0,
        key="trends_time"
    )
    time_value = time_period_options[time_label]
    geo_input_value = col_geo.text_input("Região (BR, BR-AM):", value="BR", max_chars=8).upper()
    geo_value = geo_input_value.replace(' ', '')

    # --- 1. COLETA E PROCESSAMENTO DE DADOS ---
    
    videos = None
    df = pd.DataFrame()
    trends_results_display = None
    trends_results_ihp = None
    growth_data = None
    trends_ihp_metrics = None

    with st.spinner(f"Coletando e analisando dados para '{search_term}'..."):
        
        # 1a. TIKTOK
        videos = fetch_tiktok_data(search_term)
        
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
            
            growth_data = calculate_growth_metrics(df)

        # 2. GOOGLE TRENDS
        # 2a. Fetch para IHP (últimos 90 dias, para cobrir 14d e 60d)
        trends_results_ihp = fetch_google_trends(search_term, 'today 3-m', geo_value)
        trends_df_90d = trends_results_ihp.get('df_time') if isinstance(trends_results_ihp, dict) else None
        trends_ihp_metrics = calculate_trends_metrics(trends_df_90d)

        # 2b. Fetch para Display (período selecionado pelo usuário)
        if time_value == 'today 3-m' and trends_results_ihp:
             trends_results_display = trends_results_ihp
        else:
             # AJUSTE: Adiciona uma pausa de 2 segundos antes da segunda chamada de API
             # para evitar o erro 429 (Too Many Requests)
             time.sleep(2)
             trends_results_display = fetch_google_trends(search_term, time_value, geo_value)
        
        trends_df_time_display = trends_results_display.get('df_time') if isinstance(trends_results_display, dict) else None

        # 3. CÁLCULO FINAL DO IHP
        ihp_metrics = calculate_ihp(growth_data, trends_ihp_metrics)
        ihp_total_score = ihp_metrics['ihp_total_score']
        recommendation = get_ihp_recommendation(ihp_total_score)


    # --- 2. EXIBIÇÃO DO IHP E RECOMENDAÇÃO ---
    
    st.markdown("<h3>Índice de Hype do Produto (IHP)</h3>", unsafe_allow_html=True)
    
    col_ihp, col_rec, col_tooltip = st.columns([1.7, 3, 0.5])
    
    # 2.1. Card do IHP
    delta_text = (
        f"Trends: {ihp_metrics['trends_momentum']:.0f} | "
        f"Views: {ihp_metrics['views_momentum']:.0f} | "
        f"Likes: {ihp_metrics['likes_momentum']:.0f} | "
        f"Coments: {ihp_metrics['comments_momentum']:.0f} | "
        f"Shares: {ihp_metrics['shares_momentum']:.0f}"
    )

    col_ihp.markdown(f"""
    <div class="metric-card" style="height: 100%;">
        <div class="metric-value">{ihp_total_score:.0f}/200</div>
        <div class="metric-label" title="{delta_text}">{delta_text}</div>
    </div>
    """, unsafe_allow_html=True)

    # Avisos caso dados estejam faltando
    if not growth_data:
        col_ihp.warning("A pontuação do TikTok é 0 (API falhou ou não retornou dados).")
    if not trends_ihp_metrics:
        col_ihp.warning("A pontuação do Google Trends é 0 (não há dados de 14/60 dias).")

    # 2.2. Recomendação
    with col_rec:
        # Usando o CSS .recommendation-box
        st.markdown(f"""
        <div class="recommendation-box">
            <div class="recommendation-title">Interpretação</div>
            <div class="recommendation-text">{recommendation}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2.3. Popover de Ajuda
    with col_tooltip:
        st.popover("❓").markdown("""
            ##### O que é o IHP?
            O IHP (0-200) mede o **momentum** de um produto. Ele compara a média de engajamento dos últimos 14 dias com a média dos últimos 60 dias.
            
            - **Pontuação 100:** Significa que o interesse recente (14d) é **igual** ao histórico (60d).
            - **Pontuação 200:** Interesse recente é **o dobro** (ou mais) do histórico.
            - **Pontuação < 100:** Interesse recente é **menor** que o histórico.

            ---
            **Peso de Cada Métrica:**
            * **Google Trends:** 30%
            * **TikTok Views:** 25%
            * **TikTok Likes:** 20%
            * **TikTok Comentários:** 15%
            * **TikTok Shares:** 10%
            """)


    # --- 3. ABAS DE DETALHES (TIKTOK E TRENDS) ---
    
    st.markdown("<br>", unsafe_allow_html=True)
    tab_tiktok, tab_trends = st.tabs(["Análise do TikTok", "Análise do Google Trends"])

    # --- ABA TIKTOK ---
    with tab_tiktok:
        if videos is None:
            st.warning("Não foi possível conectar à API do TikTok ou obter dados.")
        elif not videos:
            st.warning(f"Nenhum vídeo encontrado para '{search_term}' no TikTok.")
        else:
            # Métricas Totais (Cards Escuros)
            tiktok_views = df['play_count'].sum()
            tiktok_likes = df['digg_count'].sum()
            tiktok_comments = df['comment_count'].sum()
            tiktok_shares = df['share_count'].sum()

            st.header(f"Engajamento Total para '{search_term}'")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total de Views</div>
                <div class="metric-value-white">{format_number(tiktok_views)}</div>
            </div>""", unsafe_allow_html=True)
            c2.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total de Likes</div>
                <div class="metric-value-white">{format_number(tiktok_likes)}</div>
            </div>""", unsafe_allow_html=True)
            c3.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Comentários</div>
                <div class="metric-value-white">{format_number(tiktok_comments)}</div>
            </div>""", unsafe_allow_html=True)
            c4.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Compartilhamentos</div>
                <div class="metric-value-white">{format_number(tiktok_shares)}</div>
            </div>""", unsafe_allow_html=True)

            st.divider()

            # Gráfico de Linha
            df['month'] = df['create_time'].dt.to_period('M').dt.to_timestamp()
            df_time = (df.groupby('month', as_index=False)['play_count'].sum().sort_values('month'))
            
            if not df_time.empty:
                fig = px.line(df_time, x='month', y='play_count', markers=True, 
                                 title="Visualizações ao longo do tempo (baseado nos vídeos da busca)", 
                                 labels={'month': 'Mês', 'play_count': 'Visualizações'}, 
                                 color_discrete_sequence=[TEMA_COR])
                st.plotly_chart(fig, use_container_width=True)

            # Tabela de Médias (Tema Claro)
            if growth_data and (growth_data['views_14d_avg'] > 0 or growth_data['views_60d_avg'] > 0):
                st.subheader("Análise de Momentum (Média Diária)")
                st.markdown(f"""
                    <table class="thirtyd-table">
                        <thead>
                            <tr>
                                <th>Média Diária</th>
                                <th>Views</th>
                                <th>Likes</th>
                                <th>Comentários</th>
                                <th>Compartilhamentos</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Últimos 14 dias</td>
                                <td>{format_number(growth_data['views_14d_avg'])}</td>
                                <td>{format_number(growth_data['likes_14d_avg'])}</td>
                                <td>{format_number(growth_data['comments_14d_avg'])}</td>
                                <td>{format_number(growth_data['shares_14d_avg'])}</td>
                            </tr>
                            <tr>
                                <td>Últimos 60 dias</td>
                                <td>{format_number(growth_data['views_60d_avg'])}</td>
                                <td>{format_number(growth_data['likes_60d_avg'])}</td>
                                <td>{format_number(growth_data['comments_60d_avg'])}</td>
                                <td>{format_number(growth_data['shares_60d_avg'])}</td>
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
                    views = format_number(row['play_count'])
                    likes = format_number(row['digg_count'])
                    
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
        st.header(f"Interesse de Pesquisa para '{search_term}' ({time_label})")

        if 'error' in trends_results_display:
            st.error(f"**Erro no Google Trends:** {trends_results_display['error']}")
            st.info(f"Termo: **{search_term}** | Período: **{time_label}** | Região: **{geo_value}**")
        
        elif trends_df_time_display is not None and not trends_df_time_display.empty:
            
            interest_mean_period = trends_df_time_display['interest'].mean()
            
            # Pega as médias do IHP (14d/60d) para exibir
            avg_14d = trends_ihp_metrics.get('trends_14d_avg', 0) if trends_ihp_metrics else 0
            avg_60d = trends_ihp_metrics.get('trends_60d_avg', 0) if trends_ihp_metrics else 0

            # --- CARDS (Tema Claro) ---
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
            
            st.divider()
            
            # --- Gráfico de Linha ---
            fig = px.line(trends_df_time_display, x='date', y='interest', markers=True,
                            title=f"Interesse ao longo do tempo",
                            labels={'date': 'Data', 'interest': 'Nível de Interesse'},
                            color_discrete_sequence=['#ff4b4b'])
            st.plotly_chart(fig, use_container_width=True)

            # --- Interesse por Região ---
            df_region = trends_results_display.get('df_region')
            
            if isinstance(df_region, pd.DataFrame) and not df_region.empty:
                st.subheader("Interesse por Sub-Região")
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
                        "Região": "Estado/Região"
                    }
                )
            elif len(geo_value) > 2:
                st.info("A análise por sub-região só está disponível ao pesquisar por um país inteiro (ex: 'BR').")

        else:
            st.info("Não foram encontrados dados no Google Trends para os filtros selecionados.")


# --- PONTO DE ENTRADA DO SCRIPT ---
if __name__ == "__main__":
    main()

# =======================================================
            
            # Botão de Download para Google Trends
            #csv_trends = trends_df_time.to_csv(index=False).encode('utf-8')
            #st.download_button(
                #label="Baixar Dados da Série Temporal (CSV)",
                #data=csv_trends,
                #file_name=f'trends_interest_series_{search_term}.csv',
                #mime='text/csv',
                #key='download-trends-series-v2' )