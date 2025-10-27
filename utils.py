import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from pytrends.request import TrendReq
from datetime import datetime, date, timedelta
import time
import base64

# =======================================================
# FUNÇÕES DE BUSCA DE DADOS
# =======================================================

@st.cache_data(ttl=86400)
def fetch_tiktok_data(term):
    """
    Busca dados na API do TikTok com cache de 24 horas.

    :param term: O termo de pesquisa.
    :return: Lista de vídeos (dict) ou None se falhar.
    """
    try:
        API_KEY = st.secrets["tiktok_api"]["key"]
        TIKTOK_HOST = st.secrets["tiktok_api"]["host"]
    except Exception as e:
        st.error(f"ERRO: As chaves da API do TikTok não foram encontradas nos segredos. {e}")
        return None

    if not API_KEY or TIKTOK_HOST == "dummy_host" or API_KEY == "dummy_key":
        st.warning("Chaves da API do TikTok não configuradas. Pulando busca no TikTok.")
        return None

    url = f"https://{TIKTOK_HOST}/feed/search?keywords={term}&count=20"
    headers = {
        'x-rapidapi-key': API_KEY,
        'x-rapidapi-host': TIKTOK_HOST
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()  # Levanta erro para status HTTP
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


@st.cache_data(ttl=86400)
def fetch_google_trends(term, time_period, geo):
    """
    Busca dados no Google Trends com cache de 24 horas.

    :param term: O termo de pesquisa.
    :param time_period: O período de tempo.
    :param geo: A localização.
    :return: Um dicionário contendo DataFrames ou uma chave 'error'.
    """
    try:
        pytrends = TrendReq(hl='pt-BR', tz=360)
        keywords = [term]
        pytrends.build_payload(keywords, cat=0, timeframe=time_period, geo=geo, gprop='')
        time.sleep(1)

        df_time = pytrends.interest_over_time()

        if df_time.empty or term not in df_time.columns or df_time[term].max() == 0:
            return {'error': f"A pesquisa do Google Trends não retornou dados para '{term}'."}

        if 'isPartial' in df_time.columns:
            df_time = df_time.drop(columns=['isPartial'])
        df_time.columns = ['interest']
        df_time = df_time.reset_index()

        # Só busca por região se a geolocalização for um país
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

# =======================================================
# FUNÇÕES DE LÓGICA 
# =======================================================

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
    capped_ratio = min(ratio, 2.0)  # Limita em 2x (200%)
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
    # Pega os dados do TikTok. Se não existirem, usa 0.
    tm = tiktok_metrics or {}
    views_14d_avg = tm.get('views_14d_avg', 0)
    views_60d_avg = tm.get('views_60d_avg', 0)
    likes_14d_avg = tm.get('likes_14d_avg', 0)
    likes_60d_avg = tm.get('likes_60d_avg', 0)
    comments_14d_avg = tm.get('comments_14d_avg', 0)
    comments_60d_avg = tm.get('comments_60d_avg', 0)
    shares_14d_avg = tm.get('shares_14d_avg', 0)
    shares_60d_avg = tm.get('shares_60d_avg', 0)

    # Pega os dados do Trends. Se não existirem, usa 0.
    trm = trends_metrics or {}
    trends_14d_avg = trm.get('trends_14d_avg', 0)
    trends_60d_avg = trm.get('trends_60d_avg', 0)

    # Calcula o Momentum Score (0-200) para cada dimensão
    T_m = get_momentum_score(trends_14d_avg, trends_60d_avg)
    V_m = get_momentum_score(views_14d_avg, views_60d_avg)
    L_m = get_momentum_score(likes_14d_avg, likes_60d_avg)
    C_m = get_momentum_score(comments_14d_avg, comments_60d_avg)
    S_m = get_momentum_score(shares_14d_avg, shares_60d_avg)

    # Aplica os pesos e calcula o IHP final (escala 0-200)
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


# =======================================================
# ESTILOS CSS
# =======================================================

def load_css_styles(img_base64, tema_cor):
    return f"""
<style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    #MainMenu, footer {{ visibility: hidden; }}
    
    /* CAPA  */
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
        color: {tema_cor};
    }}

    .metric-card, .metric-card-trends {{
        background-color: #ffffff;
        border: 1px solid {tema_cor}; 
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

    .metric-card:hover, .metric-card-trends:hover {{
        transform: translateY(-4px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        border-color: {tema_cor};
    }}

    /* Valor principal do IHP */
    .metric-card .metric-value {{
        font-size: 28px;
        font-weight: 700;
        color: {tema_cor};
        margin-bottom: 6px;
    }}

    /* Labels */
    .metric-card .metric-label {{
        font-size: 13px;
        color: #555; 
    }}

    /* Valor dos cards de TikTok */
    .metric-card .metric-value-white {{
        font-size: 28px;
        font-weight: 700;
        color: {tema_cor};
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
        color: {tema_cor}; 
    }}

    /* BLOCO DE RECOMENDAÇÃO (IHP) */
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
        border-bottom: 2px solid {tema_cor}; 
        padding-bottom: 5px;
    }}
    .recommendation-text {{
        font-size: 1.1rem;
        font-weight: 600;
        color: {tema_cor}; 
        margin-bottom: 10px;
    }}

    /* TABELA DE MÉDIAS*/
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
    .ihp-container {{
        display: flex;
        flex-direction: column;
        height: 100%; 
        min-height: 200px; 
        justify-content: space-between; 
    }}
    .recommendation-box {{
        min-height: 200px;
    }}
    .ihp-container [data-testid="stAlert"] {{
        margin-top: 5px;
        margin-bottom: 0px;
        padding: 5px 10px;
    }}
</style>
"""