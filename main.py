import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="상권 분석: 편의점 & 카페 지도",
    page_icon="📍",
    layout="wide"
)

st.title("📍 편의점 & 카페 상권 분석 지도 앱")

# 2. 데이터 불러오기 함수 (캐싱 적용)
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("store.csv")
    except FileNotFoundError:
        try:
            df = pd.read_csv("store_filtered.csv")
        except FileNotFoundError:
            st.error("데이터 파일('store.csv' 또는 'store_filtered.csv')을 찾을 수 없습니다.")
            return None

    # 위도, 경도 숫자형 변환 및 결측치 제거
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    # 편의점, 카페 업종만 필터링
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])]
    
    # 동/구 정보 열이 없을 경우 예외 처리용 열 생성
    if "시군구명" not in df.columns:
        df["시군구명"] = "전체"
    if "법정동명" not in df.columns and "행정동명" in df.columns:
        df["법정동명"] = df["행정동명"]
    elif "법정동명" not in df.columns:
        df["법정동명"] = "전체"
        
    return df

# 3. 하버사인(Haversine) 거리 계산 함수
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # 지구 반지름 (km)
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

# 데이터 로드
df_raw = load_data()

if df_raw is not None and not df_raw.empty:
    # 4. 사이드바 - 지역 및 상세 필터 설정
    st.sidebar.header("🔍 1. 지역 선택")

    # 1단계: 시/도 선택
    sido_list = sorted(df_raw["시도명"].dropna().unique().tolist())
    selected_sido = st.sidebar.selectbox("시/도", sido_list)
    df_filtered = df_raw[df_raw["시도명"] == selected_sido].copy()

    # 2단계: 시/군/구 선택 ("전체" 옵션 포함)
    sigungu_list = ["전체"] + sorted(df_filtered["시군구명"].dropna().unique().tolist())
    selected_sigungu = st.sidebar.selectbox("시/군/구", sigungu_list)
    if selected_sigungu != "전체":
        df_filtered = df_filtered[df_filtered["시군구명"] == selected_sigungu]

    # 3단계: 읍/면/동 선택 ("전체" 옵션 포함)
    dong_list = ["전체"] + sorted(df_filtered["법정동명"].dropna().unique().tolist())
    selected_dong = st.sidebar.selectbox("읍/면/동", dong_list)
    if selected_dong != "전체":
        df_filtered = df_filtered[df_filtered["법정동명"] == selected_dong]

    st.sidebar.markdown("---")
    st.sidebar.header("🎯 2. 업종 및 반경 필터")

    # 업종 선택 (편의점/카페/전체)
    category_option = st.sidebar.radio("표시할 업종", ["전체", "편의점", "카페"])
    if category_option != "전체":
        df_filtered = df_filtered[df_filtered["상권업종소분류명"] == category_option]

    # 반경 검색 기능
    use_radius_search = st.sidebar.checkbox("반경 검색 사용하기")
    subtitle_text = ""
    center_lat, center_lon = None, None

    if use_radius_search:
        df_filtered["매장목록표시"] = df_filtered["상호명"] + " (" + df_filtered["상권업종소분류명"] + ")"
        store_list = df_filtered["매장목록표시"].tolist()
        
        if store_list:
            selected_store_name = st.sidebar.selectbox("기준 매장 선택", store_list)
            radius_km = st.sidebar.slider("검색 반경 (km)", min_value=0.2, max_value=5.0, value=1.0, step=0.1)

            base_store = df_filtered[df_filtered["매장목록표시"] == selected_store_name].iloc[0]
            center_lat, center_lon = base_store["위도"], base_store["경도"]

            df_filtered["거리(km)"] = haversine(center_lat, center_lon, df_filtered["위도"], df_filtered["경도"])
            df_filtered = df_filtered[df_filtered["거리(km)"] <= radius_km]
            
            subtitle_text = f"📍 {base_store['상호명']} 기준 반경 {radius_km} km 이내"
        else:
            st.sidebar.warning("선택한 조건에 해당하는 매장이 없습니다.")

    # 5. 메인 화면 - 요약 지표 카드
    location_title = f"{selected_sido} {selected_sigungu if selected_sigungu != '전체' else ''} {selected_dong if selected_dong != '전체' else ''}".strip()
    st.subheader(f"📊 {location_title} 매장 현황")
    if subtitle_text:
        st.caption(subtitle_text)

    convenience_count = len(df_filtered[df_filtered["상권업종소분류명"] == "편의점"])
    cafe_count = len(df_filtered[df_filtered["상권업종소분류명"] == "카페"])
    total_count = len(df_filtered)

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 매장 수", f"{total_count:,} 개")
    col2.metric("편의점 수", f"{convenience_count:,} 개")
    col3.metric("카페 수", f"{cafe_count:,} 개")

    st.markdown("---")

    # 6. 메인 화면 - 탭 구성을 통한 시각화 다변화
    tab1, tab2, tab3 = st.tabs(["🗺️ 점 지도 (위치 분포)", "🔥 밀도 지도 (히트맵)", "📋 매장 목록"])

    color_map = {"편의점": "#1f77b4", "카페": "#ff7f0e"}
    is_modern_plotly = hasattr(px, "scatter_map")

    if df_filtered.empty:
        st.info("선택한 조건에 맞는 매장이 없습니다.")
    else:
        # --- TAB 1: 기본 점 지도 ---
        with tab1:
            if is_modern_plotly:
                fig_scatter = px.scatter_map(
                    df_filtered,
                    lat="위도", lon="경도",
                    color="상권업종소분류명",
                    color_discrete_map=color_map,
                    hover_name="상호명",
                    hover_data={"상권업종소분류명": True, "위도": False, "경도": False},
                    map_style="open-street-map",
                    zoom=13 if use_radius_search or selected_dong != "전체" else 11,
                    center={"lat": center_lat, "lon": center_lon} if center_lat else None
                )
            else:
                fig_scatter = px.scatter_mapbox(
                    df_filtered,
                    lat="위도", lon="경도",
                    color="상권업종소분류명",
                    color_discrete_map=color_map,
                    hover_name="상호명",
                    hover_data={"상권업종소분류명": True, "위도": False, "경도": False},
                    mapbox_style="open-street-map",
                    zoom=13 if use_radius_search or selected_dong != "전체" else 11,
                    center={"lat": center_lat, "lon": center_lon} if center_lat else None
                )
            fig_scatter.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, legend_title_text="업종")
            st.plotly_chart(fig_scatter, use_container_width=True)

        # --- TAB 2: 밀도 히트맵 ---
        with tab2:
            st.markdown("💡 매장이 어느 구역에 집중되어 있는지 나타내는 히트맵입니다.")
            if hasattr(px, "density_map"):
                fig_density = px.density_map(
                    df_filtered,
                    lat="위도", lon="경도",
                    radius=15,
                    map_style="open-street-map",
                    zoom=12 if selected_dong != "전체" else 10
                )
            else:
                fig_density = px.density_mapbox(
                    df_filtered,
                    lat="위도", lon="경도",
                    radius=15,
                    mapbox_style="open-street-map",
                    zoom=12 if selected_dong != "전체" else 10
                )
            fig_density.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
            st.plotly_chart(fig_density, use_container_width=True)

        # --- TAB 3: 상세 목록 및 데이터 다운로드 ---
        with tab3:
            cols_to_show = ["상호명", "상권업종소분류명", "시도명", "시군구명", "법정동명"]
            display_cols = [c for c in cols_to_show if c in df_filtered.columns]
            
            st.dataframe(df_filtered[display_cols], use_container_width=True)
            
            # CSV 다운로드 버튼
            csv_data = df_filtered[display_cols].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 현재 필터링된 데이터 다운로드 (CSV)",
                data=csv_data,
                file_name="filtered_stores.csv",
                mime="text/csv"
            )
