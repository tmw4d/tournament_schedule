"""Administrator worksheet for entering game scores and statuses."""

import sqlite3
from contextlib import closing

import pandas as pd
import streamlit as st

import database
import tournament_auth


def _score_sheet(conn, division_id, status_filter, stage_filter, division_label):
    where = ["g.division_id=?"]
    params = [division_id]
    if status_filter != "All statuses":
        where.append("g.status=?")
        params.append(status_filter)
    if stage_filter != "All stages":
        where.append("g.stage=?")
        params.append(stage_filter)

    query = f"""
        SELECT g.game_id, g.game_code, g.game_time, g.stage, g.round_name,
               p.name AS pool, ta.name AS team_a, g.score_a,
               tb.name AS team_b, g.score_b, g.status
        FROM games_vw g
        LEFT JOIN pools p ON p.pool_id=g.pool_id
        LEFT JOIN teams ta ON ta.team_id=g.team_a_id
        LEFT JOIN teams tb ON tb.team_id=g.team_b_id
        WHERE {' AND '.join(where)}
        ORDER BY CASE WHEN g.game_time IS NULL THEN 1 ELSE 0 END,
                 g.game_time ASC, g.game_code ASC
    """
    frame = pd.read_sql_query(query, conn, params=params)
    if frame.empty:
        st.info("No games match these filters.")
        return

    display = frame.rename(columns={
        "game_code": "Game",
        "game_time": "Date / time",
        "stage": "Stage",
        "round_name": "Round",
        "pool": "Pool",
        "team_a": "Team A",
        "score_a": "Score A",
        "team_b": "Team B",
        "score_b": "Score B",
        "status": "Status",
    })
    editor_key = f"score_sheet_{division_id}_{status_filter}_{stage_filter}"
    edited = st.data_editor(
        display,
        key=editor_key,
        num_rows="fixed",
        hide_index=True,
        width="stretch",
        height=650,
        column_config={
            "game_id": None,
            "Game": st.column_config.TextColumn("Game", disabled=True, pinned=True),
            "Date / time": st.column_config.TextColumn("Date / time", disabled=True),
            "Stage": st.column_config.TextColumn("Stage", disabled=True),
            "Round": st.column_config.TextColumn("Round", disabled=True),
            "Pool": st.column_config.TextColumn("Pool", disabled=True),
            "Team A": st.column_config.TextColumn("Team A", disabled=True),
            "Score A": st.column_config.NumberColumn("Score A", min_value=0, step=1),
            "Team B": st.column_config.TextColumn("Team B", disabled=True),
            "Score B": st.column_config.NumberColumn("Score B", min_value=0, step=1),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["Scheduled", "In Progress", "Final"]
            ),
        },
        alt=f"Score entry worksheet for {division_label}",
    )
    if st.button("Save scores and statuses", key=f"save_{editor_key}", type="primary"):
        original = frame.set_index("game_id")
        try:
            with conn:
                for _, row in edited.iterrows():
                    game_id = int(row["game_id"])
                    before = original.loc[game_id]
                    changes = {}
                    for display_col, db_col in (("Score A", "score_a"), ("Score B", "score_b"), ("Status", "status")):
                        value = row[display_col]
                        if pd.isna(value):
                            value = None
                        old_value = before[db_col]
                        if pd.isna(old_value):
                            old_value = None
                        if value != old_value:
                            changes[db_col] = value
                    if changes:
                        assignments = ", ".join(f"{column}=?" for column in changes)
                        conn.execute(
                            f"UPDATE games SET {assignments} WHERE game_id=? AND division_id=?",
                            [*changes.values(), game_id, division_id],
                        )
            st.success("Scores and statuses saved.")
            st.rerun()
        except (sqlite3.Error, ValueError) as error:
            st.error(f"Could not save game results: {error}")


def render_score_entry():
    if not tournament_auth.is_admin():
        st.error("Administrator access is required for score entry.")
        st.stop()

    st.title("Score entry")
    st.caption("Update one game or enter results for a batch of games in the worksheet below.")
    with closing(sqlite3.connect(database.DB_PATH)) as conn:
        divisions = conn.execute(
            "SELECT division_id,name,tournament FROM divisions ORDER BY name"
        ).fetchall()
        if not divisions:
            st.info("Add a division in the Data Manager before entering scores.")
            return
        division_labels = {row[0]: f"{row[1]} · {row[2]}" for row in divisions}
        filters = st.columns(3)
        with filters[0]:
            division_id = st.selectbox(
                "Division", list(division_labels), format_func=division_labels.get,
                key="score_entry_division",
            )
        with filters[1]:
            status_filter = st.selectbox(
                "Game status", ["All statuses", "Scheduled", "In Progress", "Final"],
                key="score_entry_status",
            )
        with filters[2]:
            stage_filter = st.selectbox(
                "Stage", ["All stages", "Pool", "Playoff"], key="score_entry_stage"
            )
        _score_sheet(conn, division_id, status_filter, stage_filter, division_labels[division_id])


render_score_entry()
