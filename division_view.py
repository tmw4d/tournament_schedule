"""Division pool play and playoff views."""
import sqlite3
from contextlib import closing

import pandas as pd
import streamlit as st


def _load_matches(division_name, favorite_team=None):
    try:
        with closing(sqlite3.connect("tournament.db")) as conn:
            conn.row_factory = sqlite3.Row
            games = conn.execute("""
                SELECT g.game_code,g.stage,g.round_name,p.name pool_name,
                       ta.name team_a,tb.name team_b,g.score_a,g.score_b,
                       CASE WHEN f.field_id IS NULL THEN 'Location TBD'
                            ELSE v.name || ' · ' || f.name END venue,
                       g.game_time,g.status,
                       g.source_type_a,g.source_pool_a_id,g.source_rank_a,g.source_game_a_id,g.source_outcome_a,
                       g.source_type_b,g.source_pool_b_id,g.source_rank_b,g.source_game_b_id,g.source_outcome_b,
                       pa.name pool_a,pb.name pool_b,sa.game_code source_code_a,sb.game_code source_code_b
                FROM games_vw g JOIN divisions d ON d.division_id=g.division_id
                LEFT JOIN pools p ON p.pool_id=g.pool_id
                LEFT JOIN teams ta ON ta.team_id=g.team_a_id
                LEFT JOIN teams tb ON tb.team_id=g.team_b_id
                LEFT JOIN fields f ON f.field_id=g.field_id
                LEFT JOIN venues v ON v.venue_id=f.venue_id
                LEFT JOIN pools pa ON pa.pool_id=g.source_pool_a_id
                LEFT JOIN pools pb ON pb.pool_id=g.source_pool_b_id
                LEFT JOIN games sa ON sa.game_id=g.source_game_a_id
                LEFT JOIN games sb ON sb.game_id=g.source_game_b_id
                WHERE lower(d.name)=lower(?) ORDER BY g.game_time,g.game_code
            """, (division_name,)).fetchall()

        rows = []
        for g in games:
            def participant(team, kind, pool, rank, source, outcome):
                if team:
                    return team
                if kind == "pool_position" and pool:
                    return f"{pool} · entry {rank}"
                if kind == "pool_rank" and pool:
                    suffix = "th" if 10 <= rank % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
                    return f"{pool} · {rank}{suffix}"
                if kind == "game_result" and source:
                    return f"{outcome.title()} of {source}"
                return "TBD"

            team_a = participant(g["team_a"], g["source_type_a"], g["pool_a"], g["source_rank_a"], g["source_code_a"], g["source_outcome_a"])
            team_b = participant(g["team_b"], g["source_type_b"], g["pool_b"], g["source_rank_b"], g["source_code_b"], g["source_outcome_b"])
            if favorite_team:
                if g["team_a"] == favorite_team.get("name"):
                    team_a = f"★ {team_a}"
                if g["team_b"] == favorite_team.get("name"):
                    team_b = f"★ {team_b}"
            score = "—"
            if g["score_a"] is not None and g["score_b"] is not None:
                score = f"{g['score_a']}–{g['score_b']}"
            rows.append({
                "Stage": g["stage"], "Location": g["venue"], "Time": g["game_time"] or "Time TBD",
                "Game": g["game_code"], "Matchup": f"{team_a} vs {team_b}", "Score": score,
                "Status": g["status"],
                "Favorite": bool(favorite_team and favorite_team.get("name") in (g["team_a"], g["team_b"])),
            })
        return pd.DataFrame(rows)
    except sqlite3.Error:
        return pd.DataFrame()


def _render_games(matches, stage, division_name):
    games = matches[matches["Stage"].str.casefold() == stage.casefold()].copy() if not matches.empty else matches
    if games.empty:
        label = "pool games" if stage == "Pool" else "playoff games"
        st.info(f"No {label} are scheduled for this division yet.")
        return

    games["_sort_time"] = pd.to_datetime(games["Time"], errors="coerce")
    games = games.sort_values(["_sort_time", "Time", "Game"], na_position="last")
    for location, location_games in games.groupby("Location", sort=False, dropna=False):
        st.subheader(location)
        display_columns = ["Time", "Game", "Matchup", "Score", "Status"]
        table = location_games[display_columns]
        favorite_indices = set(location_games.index[location_games["Favorite"]])

        def highlight_favorite(row):
            if row.name in favorite_indices:
                return ["background-color: #fff2cc; color: #1b1b1b; font-weight: 600"] * len(row)
            return [""] * len(row)

        st.dataframe(
            table.style.apply(highlight_favorite, axis=1),
            hide_index=True,
            width="stretch",
            alt=f"{division_name} {stage.lower()} schedule at {location}",
        )


def _render_pool_tables(division_name, favorite_team=None):
    with closing(sqlite3.connect("tournament.db")) as conn:
        standings = pd.read_sql_query("""
            SELECT p.name AS pool, v.position, v.team_name AS team,
                   v.wins, v.losses, v.goal_differential, v.final_rank
            FROM pool_members_vw v JOIN pools p ON p.pool_id=v.pool_id
            JOIN divisions d ON d.division_id=p.division_id
            WHERE lower(d.name)=lower(?) ORDER BY p.name,v.position
        """, conn, params=(division_name,))

    if standings.empty:
        st.info("No pool members have been assigned yet.")
        return
    pools = list(standings.groupby("pool", sort=False))
    for start in range(0, len(pools), 4):
        pool_row = pools[start:start + 4]
        columns = st.columns(len(pool_row))
        for column, (pool, rows) in zip(columns, pool_row):
            with column:
                st.subheader(pool)
                favorite_rows = [
                    bool(favorite_team and row.team == favorite_team.get("name"))
                    for row in rows.itertuples()
                ]
                table = pd.DataFrame({
                    "Position · Team": [
                        f"{'★ ' if is_favorite else ''}{row.position}. {row.team or 'TBD'}"
                        for row, is_favorite in zip(rows.itertuples(), favorite_rows)
                    ],
                    "Record (W–L, GD)": [f"{row.wins}–{row.losses} ({row.goal_differential:+d})" for row in rows.itertuples()],
                    "Pool rank": [row.final_rank if pd.notna(row.final_rank) else "—" for row in rows.itertuples()],
                })
                favorite_indices = {index for index, is_favorite in enumerate(favorite_rows) if is_favorite}

                def highlight_favorite(row):
                    if row.name in favorite_indices:
                        return ["background-color: #fff2cc; color: #1b1b1b; font-weight: 600"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    table.style.apply(highlight_favorite, axis=1),
                    hide_index=True,
                    width="stretch",
                    alt=f"{pool} standings",
                )


def render_division(division_name):
    st.title(division_name)
    favorite_division = st.session_state.get("favorite_division")
    favorite_team = st.session_state.get("favorite_team")
    if favorite_division:
        st.caption(f"Your favorite: {favorite_division}" + (f" · {favorite_team['name']}" if favorite_team else ""))

    active_favorite = favorite_team if favorite_division == division_name else None
    matches = _load_matches(division_name, active_favorite)
    pool_play, playoffs = st.tabs(["Pool play", "Playoffs"])
    with pool_play:
        _render_pool_tables(division_name, active_favorite)
        st.divider()
        st.subheader("Pool play schedule")
        _render_games(matches, "Pool", division_name)
    with playoffs:
        st.subheader("Playoff schedule")
        _render_games(matches, "Playoff", division_name)
