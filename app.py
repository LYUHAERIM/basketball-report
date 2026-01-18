import json
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

# ============================================================
# 설정
# ============================================================
st.set_page_config(page_title="Basketball Report", layout="wide")

st.title("🏀 Basketball Report")
st.caption("Computer Vision 기반 선수 추적/등번호/슈팅 이벤트 추정 리포트")

# ============================================================
# 데이터 로드
# ============================================================
REPORT_PATH = Path("report_outputs/report.json")

if not REPORT_PATH.exists():
    st.error("report_outputs/report.json 파일을 찾을 수 없습니다.")
    st.stop()

report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

player_df = pd.DataFrame(report.get("player_report", []))
teams_df  = pd.DataFrame(report.get("game_report", {}).get("teams", []))
events_df = pd.DataFrame(report.get("event_log", []))

video_info = report.get("game_report", {}).get("video", {})
shots_info = report.get("game_report", {}).get("shots", {})
leaders    = report.get("game_report", {}).get("leaders", {})

# ============================================================
# 헬퍼
# ============================================================
def fmt_pct(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{float(x)*100:.1f}%"

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

# ============================================================
# 탭 UI
# ============================================================
tab_game, tab_player, tab_events = st.tabs(["📌 Game Report", "👤 Player Report", "🎯 Events"])

# ------------------------------------------------------------
# (1) Game Report
# ------------------------------------------------------------
with tab_game:
    st.subheader("Game Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Frames", safe_int(video_info.get("n_frames", 0)))
    c2.metric("Duration (s)", round(float(video_info.get("duration_s", 0.0)), 1))
    c3.metric("Total Shots", safe_int(shots_info.get("total_shots", 0)))
    c4.metric("Made / Miss", f"{safe_int(shots_info.get('made',0))} / {safe_int(shots_info.get('miss',0))}")

    st.markdown("### Team Shooting (FG)")
    if teams_df.empty:
        st.info("팀 요약 데이터가 없습니다.")
    else:
        # 보기 좋은 표시용 컬럼 추가
        teams_view = teams_df.copy()
        teams_view["FG"] = teams_view.apply(lambda r: f"{int(r.get('FGM',0))}-{int(r.get('FGA',0))}", axis=1)
        teams_view["FG%"] = teams_view["FG_pct"].apply(fmt_pct)
        show_cols = [c for c in ["team_name", "FG", "FG%", "FGM", "FGA"] if c in teams_view.columns]
        st.dataframe(teams_view[show_cols], use_container_width=True, hide_index=True)

    st.markdown("### Leaders")
    colA, colB = st.columns(2)

    with colA:
        st.markdown("**Top Movers**")
        movers = leaders.get("top_movers", [])
        if movers:
            mv = pd.DataFrame(movers)
            st.dataframe(mv, use_container_width=True, hide_index=True)
        else:
            st.write("데이터 없음")

    with colB:
        st.markdown("**Top Shooters (by FGM)**")
        shooters = leaders.get("top_shooters_by_FGM", [])
        if shooters:
            sh = pd.DataFrame(shooters)
            # FG% 보기 좋게
            if "FG_pct" in sh.columns:
                sh["FG%"] = sh["FG_pct"].apply(fmt_pct)
            st.dataframe(sh, use_container_width=True, hide_index=True)
        else:
            st.write("데이터 없음")

# ------------------------------------------------------------
# (2) Player Report
# ------------------------------------------------------------
with tab_player:
    if player_df.empty:
        st.warning("선수 리포트 데이터가 없습니다.")
    else:
        st.subheader("Select Player")

        # label 구성
        def label_row(r):
            team = r.get("team_name")
            jersey = r.get("jersey")
            name = r.get("player_name")
            tid = r.get("track_id")
            if isinstance(name, str) and len(name) > 0:
                return f"[{team}] #{jersey} {name} (tid={tid})"
            return f"[{team}] tid={tid}"

        player_df = player_df.copy()
        player_df["label"] = player_df.apply(label_row, axis=1)

        left, right = st.columns([1, 2])

        with left:
            sel = st.selectbox("선수 선택", player_df["label"].tolist())
            row = player_df[player_df["label"] == sel].iloc[0].to_dict()

            st.markdown("### Player Card")
            st.write(f"**Team**: {row.get('team_name')}")
            st.write(f"**Jersey**: {row.get('jersey')}")
            st.write(f"**Name**: {row.get('player_name') if row.get('player_name') else 'Unknown'}")
            st.divider()

            m1, m2 = st.columns(2)
            m1.metric("MIN (visible)", round(float(row.get("min_visible", 0.0)), 2))
            m2.metric("Distance (px)", safe_int(row.get("dist_px", 0)))

            m3, m4 = st.columns(2)
            m3.metric("FG", f"{safe_int(row.get('FGM',0))}-{safe_int(row.get('FGA',0))}")
            m4.metric("FG%", "-" if row.get("FG_pct") is None else f"{float(row['FG_pct'])*100:.1f}%")

            st.metric("Max Speed (px/s)", round(float(row.get("max_speed_px_s", 0.0)), 1))

        with right:
            st.markdown("### Player Table")
            view = player_df.drop(columns=["label"])
            # 보기 좋은 정렬
            sort_cols = [c for c in ["team_id", "jersey", "track_id"] if c in view.columns]
            if sort_cols:
                view = view.sort_values(sort_cols, na_position="last")
            st.dataframe(view, use_container_width=True)

            st.markdown("### This Player's Shot Events")
            tid = row.get("track_id")
            if events_df.empty:
                st.write("슛 이벤트 없음")
            else:
                ev = events_df.copy()
                if "shooter_track_id" in ev.columns:
                    ev_p = ev[ev["shooter_track_id"] == tid]
                    if len(ev_p) == 0:
                        st.write("이 선수의 슛 이벤트는 감지되지 않았습니다.")
                    else:
                        st.dataframe(ev_p, use_container_width=True, hide_index=True)

# ------------------------------------------------------------
# (3) Events
# ------------------------------------------------------------
with tab_events:
    st.subheader("Shot Events Timeline (MVP)")
    if events_df.empty:
        st.info("슛 이벤트가 감지되지 않았습니다.")
    else:
        # 시간(초)로 변환해서 보기 좋게
        ev = events_df.copy()
        if "start_frame" in ev.columns:
            fps = float(video_info.get("fps", 30.0)) if video_info else 30.0
            ev["start_s"] = ev["start_frame"] / fps
            ev["end_s"] = ev["end_frame"] / fps
        st.dataframe(ev, use_container_width=True, hide_index=True)

        # 간단 차트: made / miss
        if "made" in ev.columns:
            st.markdown("### Made vs Miss (Count)")
            counts = ev["made"].value_counts().rename(index={True:"Made", False:"Miss"}).reset_index()
            counts.columns = ["result", "count"]
            st.bar_chart(counts.set_index("result"))
