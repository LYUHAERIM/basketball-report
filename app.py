
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Basketball Player/Game Report", layout="wide")

st.title("🏀 Basketball Player / Game Report (MVP)")

# -----------------------------
# 데이터 로드
# -----------------------------
DEFAULT_PATH = Path("report_outputs/report.json")
report_path = st.sidebar.text_input("report.json 경로", str(DEFAULT_PATH))

if not Path(report_path).exists():
    st.error(f"report.json을 찾을 수 없습니다: {report_path}")
    st.stop()

report = json.loads(Path(report_path).read_text(encoding="utf-8"))
player_df = pd.DataFrame(report["player_report"])
teams_df  = pd.DataFrame(report["game_report"]["teams"])
events_df = pd.DataFrame(report["event_log"])

# -----------------------------
# 경기 요약
# -----------------------------
st.subheader("📌 Game Summary")

c1, c2, c3 = st.columns(3)
c1.metric("Frames", report["game_report"]["video"]["n_frames"])
c2.metric("Duration (s)", round(report["game_report"]["video"]["duration_s"], 1))
c3.metric("Total Shots", report["game_report"]["shots"]["total_shots"])

st.markdown("### 팀별 FG")
st.dataframe(teams_df, use_container_width=True)

st.markdown("### 리더보드")
colA, colB = st.columns(2)
with colA:
    st.markdown("**Top Movers (거리)**")
    st.dataframe(pd.DataFrame(report["game_report"]["leaders"]["top_movers"]), use_container_width=True)
with colB:
    st.markdown("**Top Shooters (FGM)**")
    st.dataframe(pd.DataFrame(report["game_report"]["leaders"]["top_shooters_by_FGM"]), use_container_width=True)

# -----------------------------
# 선수 리포트
# -----------------------------
st.subheader("👤 Player Report")

# 선수 선택 옵션: 이름이 있으면 이름 우선, 없으면 track_id 기반
def _label_row(r):
    name = r.get("player_name")
    jersey = r.get("jersey")
    team = r.get("team_name")
    tid = r.get("track_id")
    if isinstance(name, str) and len(name) > 0:
        return f"[{team}] #{jersey} {name} (tid={tid})"
    return f"[{team}] tid={tid}"

player_df["label"] = player_df.apply(_label_row, axis=1)

sel = st.selectbox("선수 선택", player_df["label"].tolist())
row = player_df[player_df["label"] == sel].iloc[0].to_dict()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("MIN (visible)", round(float(row.get("min_visible", 0.0)), 2))
m2.metric("FG", f'{int(row.get("FGM",0))}-{int(row.get("FGA",0))}')
m3.metric("FG%", "-" if row.get("FG_pct") is None else f'{float(row["FG_pct"])*100:.1f}%')
m4.metric("Dist (px)", int(row.get("dist_px", 0)))
m5.metric("Max Speed (px/s)", round(float(row.get("max_speed_px_s", 0.0)), 1))

st.markdown("### 전체 선수 테이블")
st.dataframe(
    player_df.drop(columns=["label"]).sort_values(["team_id","jersey","track_id"]),
    use_container_width=True
)

# -----------------------------
# 슛 이벤트 로그
# -----------------------------
st.subheader("🎯 Shot Events (MVP)")
if len(events_df) == 0:
    st.info("이 영상에서는 슛 이벤트가 감지되지 않았습니다.")
else:
    st.dataframe(events_df, use_container_width=True)
