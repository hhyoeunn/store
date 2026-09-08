import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="편의점 & 카페 지도 시각화",
    page_icon="📍",
    layout="wide"
)

st.title("📍 편의점 & 카페 지도 시각화 앱")

# 2. 데이터 불러오기 함수 (캐싱 적용)
@st.cache_data
def load_data():
    # store.csv 시도 후 실패 시 store_filtered.csv 읽기
    try:
        df = pd.read_csv("store.csv")
    except FileNotFoundError:
        try:
            df = pd.read_csv("store_filtered.csv")
        except FileNotFoundError:
            st.error("데이터 파일('store.csv' 또는 'store_filtered.csv')을 찾을 수 없습니다.")
            return None

    # 위도, 경도 열을 숫자형으로 변환 (숫자가 아닌 값은 NaN 처리)
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    
    # 위도·경도가 비어 있거나 결측치인 행 제거
    df = df.dropna(subset=["위도", "경도"])

    # 편의점, 카페 업종만 필터링
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])]
    return df

# 3. 하버사인(Haversine) 거리 계산 함수 (단위: km)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # 지구 반지름 (km)
    
    # 라디안 단위 변환
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # 하버사인 공식 적용
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return R * c

# 데이터 로드
df_raw = load_data()

if df_raw is not None and not df_raw.empty:
    # 4. 사이드바 설정
    st.sidebar.header("🔍 검색 및 필터 설정")

    # [필터 1] 지역(시/도) 선택
    sido_list = sorted(df_raw["시도명"].dropna().unique().tolist())
    selected_sido = st.sidebar.selectbox("시/도를 선택하세요", sido_list)

    # 선택한 지역 데이터로 1차 필터링
    df_filtered = df_raw[df_raw["시도명"] == selected_sido].copy()

    # [필터 2] 반경 검색 기능
    use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")
    
    subtitle_text = ""
    center_lat, center_lon = None, None

    if use_radius_search:
        # 기준 매장 선택 드롭다운 (매장명과 주소/업종을 조합해 식별)
        df_filtered["매장목록표시"] = df_filtered["상호명"] + " (" + df_filtered["상권업종소분류명"] + ")"
        store_list = df_filtered["매장목록표시"].tolist()
        
        if store_list:
            selected_store_name = st.sidebar.selectbox("기준 매장을 선택하세요", store_list)
            radius_km = st.sidebar.slider("검색 반경 (km)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)

            # 선택한 기준 매장의 좌표 추출
            base_store = df_filtered[df_filtered["매장목록표시"] == selected_store_name].iloc[0]
            center_lat = base_store["위도"]
            center_lon = base_store["경도"]

            # 기준 위치로부터 거리 계산 후 필터링
            df_filtered["거리(km)"] = haversine(center_lat, center_lon, df_filtered["위도"], df_filtered["경도"])
            df_filtered = df_filtered[df_filtered["거리(km)"] <= radius_km]
            
            subtitle_text = f"📍 {base_store['상호명']} 기준 반경 {radius_km} km 이내"
        else:
            st.sidebar.warning("선택한 지역에 매장이 없습니다.")

    # 5. 메인 화면 - 지표 카드(st.metric) 출력
    st.subheader(f"📊 매장 현황 ({selected_sido})")
    if subtitle_text:
        st.caption(subtitle_text)

    # 매장 수 집계
    convenience_count = len(df_filtered[df_filtered["상권업종소분류명"] == "편의점"])
    cafe_count = len(df_filtered[df_filtered["상권업종소분류명"] == "카페"])
    total_count = len(df_filtered)

    # 지표 카드 3개 나란히 배치
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 매장 수", f"{total_count:,} 개")
    col2.metric("편의점 수", f"{convenience_count:,} 개")
    col3.metric("카페 수", f"{cafe_count:,} 개")

    st.markdown("---")

    # 6. 메인 화면 - Plotly 지도 출력
    if df_filtered.empty:
        st.info("조건에 맞는 매장이 없습니다. 검색 조건이나 반경을 변경해 보세요.")
    else:
        # 업종별 색상 지정 (편의점: 파란색, 카페: 주황색)
        color_map = {
            "편의점": "#1f77b4",  # Blue
            "카페": "#ff7f0e"     # Orange
        }

        # plotly 버전 호환성 처리 (Plotly 최신 버전은 scatter_map, 구버전은 scatter_mapbox 사용)
        is_modern_plotly = hasattr(px, "scatter_map")

        if is_modern_plotly:
            fig = px.scatter_map(
                df_filtered,
                lat="위도",
                lon="경도",
                color="상권업종소분류명",
                color_discrete_map=color_map,
                hover_name="상호명",
                hover_data={"상권업종소분류명": True, "위도": False, "경도": False},
                map_style="open-street-map",
                zoom=12 if use_radius_search else 10,
                center={"lat": center_lat, "lon": center_lon} if (use_radius_search and center_lat) else None
            )
        else:
            fig = px.scatter_mapbox(
                df_filtered,
                lat="위도",
                lon="경도",
                color="상권업권소분류명",
                color_discrete_map=color_map,
                hover_name="상호명",
                hover_data={"상권업종소분류명": True, "위도": False, "경도": False},
                mapbox_style="open-street-map",
                zoom=12 if use_radius_search else 10,
                center={"lat": center_lat, "lon": center_lon} if (use_radius_search and center_lat) else None
            )

        # 지도 여백 및 레이아웃 설정
        fig.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            legend_title_text="업종 구분"
        )

        st.plotly_chart(fig, use_container_width=True)
