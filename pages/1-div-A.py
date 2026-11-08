import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Division A", page_icon="🏆", layout="wide")

st.title("🏆 Division A: Schedule & Standings")

# Database query helper
def load_data(query, params=()):
    conn = sqlite3.connect("tournament.db")
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

tab_schedule, tab_standings = st.tabs(["📅 Match Schedule", "📊 Pool Standings"])

with tab_schedule:
    st.subheader("Upcoming & Final Matches")
    df_matches = load_data("""
        SELECT m.match_id, m.stage, m.round_name, 
               t1.name AS home_team, m.home_score, 
               t2.name AS away_team, m.away_score, 
               v.name AS venue, m.scheduled_time, m.status
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.team_id
        JOIN teams t2 ON m.away_team_id = t2.team_id
        JOIN venues v ON m.venue_id = v.venue_id
    """)
    st.dataframe(df_matches, use_container_width=True)

with tab_standings:
    st.subheader("Pool Standings")
    st.markdown("Calculated dynamically from final match results.")
    # Add your Pandas standings groupby/aggregation logic here