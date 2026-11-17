"""Schedule and pool standings backed by calculated database views."""
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
                       CASE WHEN f.field_id IS NULL THEN NULL ELSE v.name || ' · ' || f.name END venue,
                       g.game_time,g.status,g.winner_team_id,g.loser_team_id,
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
            rows=[]
            for g in games:
                def participant(team, kind, pool, rank, source, outcome):
                    if team: return team
                    if kind == "pool_position" and pool:
                        return f"{pool} · entry {rank}"
                    if kind == "pool_rank" and pool:
                        suffix = "th" if 10 <= rank % 100 <= 20 else {1:"st",2:"nd",3:"rd"}.get(rank % 10,"th")
                        return f"{pool} · {rank}{suffix}"
                    if kind == "game_result" and source:
                        return f"{outcome.title()} of {source}"
                    return "TBD"
                team_a=participant(g["team_a"],g["source_type_a"],g["pool_a"],g["source_rank_a"],g["source_code_a"],g["source_outcome_a"])
                team_b=participant(g["team_b"],g["source_type_b"],g["pool_b"],g["source_rank_b"],g["source_code_b"],g["source_outcome_b"])
                if favorite_team:
                    if g["team_a"] == favorite_team.get("name"): team_a=f"★ {team_a}"
                    if g["team_b"] == favorite_team.get("name"): team_b=f"★ {team_b}"
                rows.append({"Game":g["game_code"],"Stage":g["stage"],"Round":g["round_name"],
                    "Pool":g["pool_name"],"Team A":team_a,"Score A":g["score_a"],
                    "Team B":team_b,"Score B":g["score_b"],"Venue":g["venue"],
                    "Scheduled time":g["game_time"],"Status":g["status"]})
        return pd.DataFrame(rows)
    except sqlite3.Error:
        return pd.DataFrame()


def render_division(division_name):
    st.title(f"{division_name}: Schedule & Standings")
    favorite_division=st.session_state.get("favorite_division")
    favorite_team=st.session_state.get("favorite_team")
    if favorite_division:
        st.caption(f"Your favorite: {favorite_division}" + (f" · {favorite_team['name']}" if favorite_team else ""))
    schedule, standings=st.tabs(["Match schedule","Pool standings"])
    with schedule:
        matches=_load_matches(division_name,favorite_team if favorite_division==division_name else None)
        if matches.empty: st.info("No games are scheduled for this division yet.")
        else: st.dataframe(matches,hide_index=True,width="stretch",alt=f"{division_name} game schedule")
    with standings:
        with closing(sqlite3.connect("tournament.db")) as conn:
            df=pd.read_sql_query("""SELECT p.name pool, v.position, v.team_name team,
                v.wins,v.losses,v.goals_for,v.goals_against,v.goal_differential,v.final_rank
                FROM pool_members_vw v JOIN pools p ON p.pool_id=v.pool_id
                JOIN divisions d ON d.division_id=p.division_id
                WHERE lower(d.name)=lower(?) ORDER BY p.name,v.final_rank,v.position""",conn,params=(division_name,))
        if df.empty: st.info("No pool members have been assigned yet.")
        else: st.dataframe(df,hide_index=True,width="stretch",alt=f"{division_name} pool standings")
