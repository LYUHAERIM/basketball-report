import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Basketball Report", layout="wide")

st.title("🏀 Basketball Player / Team Report")

# -----------------------------
# Utils
# -----------------------------
def _is_nan(x) -> bool:
    try:
        return x is None or (isinstance(x, float) and math.isnan(x))
    except Exception:
        return x is None

def _to_num(x):
    if _is_nan(x):
        return np.nan
    return x

def _safe_pct(x):
    # expects 0~1
    if _is_nan(x):
        return "-"
    try:
        return f"{float(x)*100:.1f}%"
    except Exception:
        return "-"

def _safe_int(x, default=0):
    if _is_nan(x):
        return default
    try:
        return int(x)
    except Exception:
        return default

def _safe_float(x, default=0.0):
    if _is_nan(x):
        return default
    try:
        return float(x)
    except Exception:
        return default

@st.cache_data(show_spinner=False)
def load_report(path_str: str) -> dict:
    p = Path(path_str)
    text = p.read_text(encoding="utf-8")
    # allow NaN tokens if they exist (some pipelines dump NaN barewords)
    # json.loads will fail on bare NaN, so we fallback to a tolerant replace.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Best-effort: replace bare NaN with null
        fixed = text.replace(": NaN", ": null").replace(": nan", ": null")
        return json.loads(fixed)

def df_or_empty(obj, cols_hint=None):
    if obj is None:
        return pd.DataFrame(columns=cols_hint or [])
    if isinstance(obj, list):
        return pd.DataFrame(obj)
    # dict -> one row
    return pd.DataFrame([obj])

# -----------------------------
# Data load (sidebar)
# -----------------------------
DEFAULT_PATH = Path("report_outputs/report.json")
report_path = st.sidebar.text_input("report.json 경로", str(DEFAULT_PATH))

if not Path(report_path).exists():
    st.error(f"report.json을 찾을 수 없습니다: {report_path}")
    st.stop()

report = load_report(report_path)

meta = report.get("meta", {})
team_summary_df = df_or_empty(report.get("team_summary", []))
player_df = df_or_empty(report.get("player_report", []))
team_ts_df = df_or_empty(report.get("team_frame_series", []))

# event_log is optional in new schema (some runs may not include it)
events_df = df_or_empty(report.get("event_log", []))

# normalize numeric columns where it helps
for c in [
    "team_visible_min", "team_total_dist", "team_avg_speed", "team_max_speed",
    "team_FGA", "team_FGM", "team_FG_pct",
    "avg_spacing", "avg_spread", "var_spread", "avg_visible_players",
]:
    if c in team_summary_df.columns:
        team_summary_df[c] = pd.to_numeric(team_summary_df[c], errors="coerce")

for c in [
    "visible_frames", "first_t", "last_t", "total_dist", "avg_speed", "max_speed",
    "avg_accel", "max_accel", "avg_jerk", "max_jerk",
    "visible_sec", "MIN_visible",
    "stop_go_transitions", "sprint_count", "turn_frames", "activity_score",
    "FGA", "FGM", "FG_pct",
]:
    if c in player_df.columns:
        player_df[c] = pd.to_numeric(player_df[c], errors="coerce")

for c in [
    "frame_idx", "time_s", "team_id",
    "n_players_visible", "centroid_x", "centroid_y",
    "spacing_nn_mean", "spread_pair_mean", "spread_pair_var",
]:
    if c in team_ts_df.columns:
        team_ts_df[c] = pd.to_numeric(team_ts_df[c], errors="coerce")

# -----------------------------
# Tabs
# -----------------------------
tab_overview, tab_teams, tab_players, tab_timeseries, tab_events, tab_raw = st.tabs(
    ["📌 Overview", "👥 Teams", "👤 Players", "📈 Team Time Series", "🎯 Events", "🧾 Raw"]
)

# -----------------------------
# Overview
# -----------------------------
with tab_overview:
    st.subheader("📌 Meta")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Source Video", str(meta.get("source_video", "-")))
    c2.metric("FPS", _safe_float(meta.get("fps", np.nan), 0.0))
    c3.metric("Frames Logged", _safe_int(meta.get("total_frames_logged", np.nan), 0))
    c4.metric("Approx Duration (s)", round(_safe_int(meta.get("total_frames_logged", np.nan), 0) / max(_safe_float(meta.get("fps", np.nan), 30.0), 1e-6), 2))

    note = meta.get("note")
    if isinstance(note, str) and note.strip():
        st.info(note)

    st.subheader("🏁 Quick Team Summary")
    if len(team_summary_df) == 0:
        st.warning("team_summary가 비어 있습니다.")
    else:
        # a compact metric row
        for _, tr in team_summary_df.sort_values("team_id").iterrows():
            cols = st.columns(6)
            cols[0].metric("Team", f'{tr.get("team_name","-")} (id={_safe_int(tr.get("team_id",0))})')
            cols[1].metric("Visible (min)", round(_safe_float(tr.get("team_visible_min", np.nan), 0.0), 2))
            cols[2].metric("FGA", _safe_int(tr.get("team_FGA", np.nan), 0))
            cols[3].metric("FGM", _safe_int(tr.get("team_FGM", np.nan), 0))
            cols[4].metric("FG%", _safe_pct(tr.get("team_FG_pct", np.nan)))
            cols[5].metric("Avg Spacing", round(_safe_float(tr.get("avg_spacing", np.nan), 0.0), 1))

        st.markdown("### team_summary 테이블")
        st.dataframe(team_summary_df, use_container_width=True)

# -----------------------------
# Teams
# -----------------------------
with tab_teams:
    st.subheader("👥 Teams")

    if len(team_summary_df) == 0:
        st.warning("team_summary가 비어 있습니다.")
    else:
        # sortable leaderboard
        sort_key = st.selectbox(
            "정렬 기준",
            options=[
                "team_total_dist",
                "team_avg_speed",
                "team_max_speed",
                "team_FG_pct",
                "avg_spacing",
                "avg_spread",
                "var_spread",
            ],
            index=0,
        )
        ascending = st.checkbox("오름차순", value=False)

        view = team_summary_df.copy()
        if sort_key in view.columns:
            view = view.sort_values(sort_key, ascending=ascending)

        st.dataframe(view, use_container_width=True)

# -----------------------------
# Players
# -----------------------------
with tab_players:
    st.subheader("👤 Players")

    if len(player_df) == 0:
        st.warning("player_report가 비어 있습니다.")
    else:
        # label for selectbox
        def _label_row(r):
            team = r.get("team_name", "-")
            tid = r.get("track_id", "-")
            jersey = r.get("jersey", None)
            name = r.get("player_name", None)

            jersey_txt = f"#{jersey}" if isinstance(jersey, str) and jersey.strip() else ""
            name_txt = f"{name}" if isinstance(name, str) and name.strip() else "Unknown"
            return f"[{team}] {jersey_txt} {name_txt} (tid={tid})".replace("  ", " ").strip()

        player_df = player_df.copy()
        if "label" not in player_df.columns:
            player_df["label"] = player_df.apply(_label_row, axis=1)

        # filters
        team_options = ["(All)"]
        if "team_name" in player_df.columns:
            team_options += sorted([x for x in player_df["team_name"].dropna().unique().tolist()])
        team_sel = st.selectbox("팀 필터", options=team_options, index=0)

        filtered = player_df
        if team_sel != "(All)" and "team_name" in player_df.columns:
            filtered = player_df[player_df["team_name"] == team_sel]

        # select player
        sel = st.selectbox("선수 선택", filtered["label"].tolist())
        row = filtered[filtered["label"] == sel].iloc[0].to_dict()

        # metrics
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("MIN_visible", round(_safe_float(row.get("MIN_visible", np.nan), 0.0), 3))
        m2.metric("Visible Frames", _safe_int(row.get("visible_frames", np.nan), 0))
        m3.metric("Distance (px)", round(_safe_float(row.get("total_dist", np.nan), 0.0), 1))
        m4.metric("Avg Speed (px/s)", round(_safe_float(row.get("avg_speed", np.nan), 0.0), 1))
        m5.metric("Max Speed (px/s)", round(_safe_float(row.get("max_speed", np.nan), 0.0), 1))
        m6.metric("Activity Score", round(_safe_float(row.get("activity_score", np.nan), 0.0), 1))

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Stop↔Go Transitions", _safe_int(row.get("stop_go_transitions", np.nan), 0))
        s2.metric("Sprint Count", _safe_int(row.get("sprint_count", np.nan), 0))
        s3.metric("Turn Frames", _safe_int(row.get("turn_frames", np.nan), 0))
        s4.metric("FG", f'{_safe_int(row.get("FGM", np.nan), 0)}-{_safe_int(row.get("FGA", np.nan), 0)} ({_safe_pct(row.get("FG_pct", np.nan))})')

        st.markdown("### 선택 선수 원본 row")
        st.json(row)

        st.markdown("### 전체 선수 테이블")
        show_cols = [c for c in player_df.columns if c != "label"]
        sort_cols = [c for c in ["team_id", "jersey", "track_id"] if c in player_df.columns]
        st.dataframe(
            player_df[show_cols].sort_values(sort_cols) if sort_cols else player_df[show_cols],
            use_container_width=True
        )

# -----------------------------
# Team Time Series
# -----------------------------
with tab_timeseries:
    st.subheader("📈 Team Time Series (per-frame)")

    if len(team_ts_df) == 0:
        st.warning("team_frame_series가 비어 있습니다.")
    else:
        # team selector
        teams = []
        if "team_name" in team_ts_df.columns:
            teams = sorted([x for x in team_ts_df["team_name"].dropna().unique().tolist()])
        if len(teams) == 0:
            teams = ["(unknown)"]

        team_pick = st.multiselect("표시할 팀", options=teams, default=teams[:2])

        ts = team_ts_df.copy()
        if "team_name" in ts.columns and team_pick:
            ts = ts[ts["team_name"].isin(team_pick)]

        # downsample option (large logs)
        max_rows = st.slider("표시 최대 행 수(다운샘플)", min_value=500, max_value=20000, value=5000, step=500)
        if len(ts) > max_rows and "frame_idx" in ts.columns:
            # uniform downsample by frame order
            ts = ts.sort_values(["team_id", "frame_idx"] if "team_id" in ts.columns else ["frame_idx"])
            stride = max(1, len(ts) // max_rows)
            ts = ts.iloc[::stride, :]

        # metric selector
        metric = st.selectbox(
            "지표",
            options=[
                "spacing_nn_mean",
                "spread_pair_mean",
                "spread_pair_var",
                "centroid_x",
                "centroid_y",
                "n_players_visible",
            ],
            index=0
        )

        if metric not in ts.columns:
            st.error(f"선택 지표 컬럼이 없습니다: {metric}")
        else:
            # pivot -> line chart
            x_col = "time_s" if "time_s" in ts.columns else "frame_idx"
            if x_col not in ts.columns:
                st.error("time_s/frame_idx 컬럼이 없어 시계열을 그릴 수 없습니다.")
            else:
                ts2 = ts[[x_col, "team_name", metric]].dropna(subset=[x_col, "team_name"])
                pivot = ts2.pivot_table(index=x_col, columns="team_name", values=metric, aggfunc="mean").sort_index()
                st.line_chart(pivot)

        st.markdown("### team_frame_series 테이블(필터/다운샘플 반영)")
        st.dataframe(ts, use_container_width=True)

# -----------------------------
# Events
# -----------------------------
with tab_events:
    st.subheader("🎯 Events")

    if len(events_df) == 0:
        st.info("event_log가 없거나 비어 있습니다. (파이프라인에서 선택적으로 생성되는 것으로 보입니다.)")
    else:
        st.dataframe(events_df, use_container_width=True)

# -----------------------------
# Raw
# -----------------------------
with tab_raw:
    st.subheader("🧾 Raw JSON")
    st.json(report)
