import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="HR Insight Dashboard", page_icon="👥", layout="wide")

st.title("👥 HR Analytics Dashboard")
st.markdown("### 📈 인력 변동 추이 및 조직 현황")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 (구글 시트 연결)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="시트1") # 🚨 시트 이름 확인 필수!
    
    # 컬럼 매핑 (사용자 환경에 맞게 수정 필요)
    rename_map = {
        '사번': '사번',
        '성명': '이름',
        '이름': '이름',
        '부서': '부서',
        '조직': '부서',
        '소속': '부서',
        '직위': '직급',
        '직급': '직급',
        '입사일': '입사일',
        '그룹입사일': '입사일',
        '퇴사일': '퇴사일',
        '퇴사일자': '퇴사일',
        '성별': '성별'
    }
    df = df.rename(columns=rename_map)

    # 날짜 변환
    if '입사일' in df.columns:
        df['입사일'] = pd.to_datetime(df['입사일'], errors='coerce')
    if '퇴사일' in df.columns:
        df['퇴사일'] = pd.to_datetime(df['퇴사일'], errors='coerce')
        
    return df

try:
    df_master = load_data()
except Exception as e:
    st.error(f"데이터 로드 중 오류 발생: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 필터
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🔍 조회 조건")
    target_date = st.date_input("조회 기준일", datetime.today())
    target_date = pd.to_datetime(target_date)
    
    if '부서' in df_master.columns:
        dept_list = ["전체"] + list(df_master['부서'].unique())
        selected_dept = st.selectbox("부서 선택", dept_list)

# -----------------------------------------------------------------------------
# 4. 데이터 필터링 & KPI 계산
# -----------------------------------------------------------------------------
# (1) 조회 시점 현재 인원
mask_current = (df_master['입사일'] <= target_date) & \
               ( (df_master['퇴사일'].isna()) | (df_master['퇴사일'] >= target_date) )
df_current = df_master[mask_current].copy()

# 부서 필터 적용
if selected_dept != "전체":
    df_current = df_current[df_current['부서'] == selected_dept]

# KPI 1: 총 인원
total_count = len(df_current)

# KPI 2: 평균 근속 연수
if not df_current.empty:
    # (기준일 - 입사일)의 일수 / 365
    df_current['근속년수'] = (target_date - df_current['입사일']).dt.days / 365
    avg_tenure = round(df_current['근속년수'].mean(), 1)
else:
    avg_tenure = 0

# KPI 3: 올해 퇴사자 수 (조회 기준일이 속한 연도의 1월 1일부터 ~ 조회일까지)
start_of_year = datetime(target_date.year, 1, 1)
mask_exit = (df_master['퇴사일'] >= start_of_year) & (df_master['퇴사일'] <= target_date)
if selected_dept != "전체":
    mask_exit = mask_exit & (df_master['부서'] == selected_dept)
exit_count = len(df_master[mask_exit])

# -----------------------------------------------------------------------------
# 5. [신규 기능] 월별 인원 추이 (Trend) 계산 로직
# -----------------------------------------------------------------------------
# 2023년 1월부터 ~ 조회 기준일까지 매월 말일 기준 인원 계산
trend_data = []
start_trend_date = pd.to_datetime("2023-01-31") # 시작점 설정

# 조회일자가 시작점보다 과거면 시작점을 조정
if target_date < start_trend_date:
    date_range = pd.date_range(start=target_date, end=target_date, freq='ME')
else:
    date_range = pd.date_range(start=start_trend_date, end=target_date, freq='ME')

for d in date_range:
    # 해당 시점(d)에 재직 중이었던 사람 카운트
    # 로직: 입사일 <= 그달말일 AND (퇴사일 없거나 OR 퇴사일 > 그달말일)
    mask_month = (df_master['입사일'] <= d) & \
                 ( (df_master['퇴사일'].isna()) | (df_master['퇴사일'] > d) )
    
    # 부서 필터가 있으면 적용
    temp_df = df_master[mask_month]
    if selected_dept != "전체":
        temp_df = temp_df[temp_df['부서'] == selected_dept]
        
    trend_data.append({
        "기준월": d.strftime("%Y-%m"),
        "인원수": len(temp_df)
    })

df_trend = pd.DataFrame(trend_data)

# -----------------------------------------------------------------------------
# 6. 화면 배치 (UI)
# -----------------------------------------------------------------------------
# Top Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("총 재직 인원", f"{total_count}명")
m2.metric("평균 근속기간", f"{avg_tenure}년")
m3.metric("올해 누적 퇴사", f"{exit_count}명")
m4.metric("데이터 기준일", target_date.strftime('%Y-%m-%d'))

st.divider()

# Row 1: 월별 추이 그래프 (Line Chart)
st.subheader("📈 월별 인원 변동 추이 (2023~)")
if not df_trend.empty:
    fig_trend = px.line(df_trend, x='기준월', y='인원수', markers=True, 
                        title=f"{selected_dept} 인원 추이")
    fig_trend.update_yaxes(range=[0, df_trend['인원수'].max() * 1.2]) # Y축 여유 두기
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("추이 데이터를 계산할 수 없습니다.")

# Row 2: 구성 현황
c1, c2 = st.columns(2)

with c1:
    st.subheader("🏢 부서별 분포")
    if not df_current.empty and '부서' in df_current.columns:
        df_dept_group = df_current['부서'].value_counts().reset_index()
        df_dept_group.columns = ['부서', '인원수']
        fig_dept = px.pie(df_dept_group, values='인원수', names='부서', hole=0.4)
        st.plotly_chart(fig_dept, use_container_width=True)

with c2:
    st.subheader("📊 직급/성별 분포")
    if not df_current.empty and '직급' in df_current.columns:
        # 직급별 정렬을 위해 리스트 순서 지정 가능 (필요시 커스텀)
        fig_pos = px.bar(df_current, x='직급', color='성별', barmode='group',
                         title="직급별 성별 현황")
        st.plotly_chart(fig_pos, use_container_width=True)

# Row 3: 상세 데이터 (숨김/펼치기 가능)
with st.expander("📋 상세 명단 보기 (클릭하세요)"):
    st.dataframe(df_current, use_container_width=True, hide_index=True)