"""Session-scoped favorite division and team controls."""

import sqlite3
from contextlib import closing

import streamlit as st
import database


def _teams_for_division(division_name):
    if not division_name or not database.DB_PATH.exists():
        return []

    try:
        with closing(sqlite3.connect(database.DB_PATH)) as conn:
            return conn.execute(
                """
                SELECT t.team_id, t.name
                FROM teams AS t
                JOIN divisions AS d ON d.division_id = t.division_id
                WHERE lower(d.name) = lower(?)
                ORDER BY t.name
                """,
                (division_name,),
            ).fetchall()
    except sqlite3.Error:
        return []


def render_favorite_controls(divisions):
    """Render favorite selectors in the shared sidebar and update session state."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("Your favorites")

    division_names = [division["name"] for division in divisions]
    st.sidebar.selectbox(
        "Favorite division",
        options=[None, *division_names],
        format_func=lambda value: value or "Choose a division",
        key="favorite_division",
    )
    favorite_division = st.session_state.get("favorite_division")

    teams = _teams_for_division(favorite_division)
    team_names = {team_id: name for team_id, name in teams}
    team_ids = list(team_names)

    if team_ids:
        if st.session_state.get("favorite_team_id") not in [None, *team_ids]:
            st.session_state["favorite_team_id"] = None
        st.sidebar.selectbox(
            "Favorite team",
            options=[None, *team_ids],
            format_func=lambda team_id: "Choose a team" if team_id is None else team_names[team_id],
            key="favorite_team_id",
        )
        selected_team_id = st.session_state.get("favorite_team_id")
        st.session_state["favorite_team"] = (
            {"team_id": selected_team_id, "name": team_names[selected_team_id]}
            if selected_team_id is not None
            else None
        )
    else:
        st.session_state["favorite_team_id"] = None
        if favorite_division:
            st.sidebar.caption("No roster is loaded for this division yet. You can enter a team name:")
            team_name = st.sidebar.text_input(
                "Favorite team name",
                key="favorite_team_name_input",
                placeholder="Enter team name",
            ).strip()
            st.session_state["favorite_team"] = (
                {"team_id": None, "name": team_name} if team_name else None
            )
        else:
            st.session_state["favorite_team"] = None
            st.sidebar.caption("Choose a division first to pick a team.")
