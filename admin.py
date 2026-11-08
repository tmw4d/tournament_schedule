import streamlit as st
import sqlite3
import pandas as pd

DB_PATH = "tournament.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to execute updates safely
def apply_table_changes(table_name, primary_key, edited_df, original_df, changes):
    """
    Synchronizes st.data_editor changes back to SQLite.
    `changes` is a dict containing 'edited_rows', 'added_rows', and 'deleted_rows'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Handle Edited Rows
        for row_idx, updated_cols in changes.get("edited_rows", {}).items():
            record_id = original_df.iloc[row_idx][primary_key]
            set_clause = ", ".join([f"{col} = ?" for col in updated_cols.keys()])
            values = list(updated_cols.values()) + [record_id]
            
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key} = ?"
            cursor.execute(sql, values)

        # 2. Handle Newly Added Rows
        for new_row in changes.get("added_rows", []):
            # Filter out empty fields if primary key is autoincrement
            filtered_row = {k: v for k, v in new_row.items() if k != primary_key and v is not None}
            if filtered_row:
                columns = ", ".join(filtered_row.keys())
                placeholders = ", ".join(["?"] * len(filtered_row))
                values = list(filtered_row.values())
                
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)

        # 3. Handle Deleted Rows
        for row_idx in changes.get("deleted_rows", []):
            record_id = original_df.iloc[row_idx][primary_key]
            sql = f"DELETE FROM {table_name} WHERE {primary_key} = ?"
            cursor.execute(sql, [record_id])

        conn.commit()
        st.success(f"Successfully saved changes to {table_name}!")
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving changes: {e}")
    finally:
        conn.close()

# --- Main Admin View ---
def render_admin_dashboard():
    st.title("🛠️ Tournament Data Manager (Spreadsheet View)")
    st.markdown("Edit values directly in the cells below. Click **Save Changes** to sync edits, new rows, or deletions back to SQLite.")

    # Table selection tabs
    tab_matches, tab_teams, tab_venues, tab_divisions = st.tabs([
        "⚽ Matches", "🛡️ Teams", "📍 Venues", "🏆 Divisions"
    ])

    conn = get_db_connection()

    # --- 1. MATCHES EDITOR ---
    with tab_matches:
        st.subheader("Manage Match Schedules & Scores")
        df_matches = pd.read_sql("SELECT * FROM matches", conn)
        
        edited_matches = st.data_editor(
            df_matches,
            key="editor_matches",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "match_id": st.column_config.NumberColumn("ID", disabled=True),
                "stage": st.column_config.SelectboxColumn("Stage", options=["Pool", "Playoff"]),
                "status": st.column_config.SelectboxColumn("Status", options=["Scheduled", "In Progress", "Final"]),
                "home_score": st.column_config.NumberColumn("Home Score", min_value=0),
                "away_score": st.column_config.NumberColumn("Away Score", min_value=0),
            }
        )
        
        if st.button("Save Matches Table", type="primary"):
            changes = st.session_state["editor_matches"]
            apply_table_changes("matches", "match_id", edited_matches, df_matches, changes)

    # --- 2. TEAMS EDITOR ---
    with tab_teams:
        st.subheader("Manage Teams & Access PINs")
        df_teams = pd.read_sql("SELECT * FROM teams", conn)
        
        edited_teams = st.data_editor(
            df_teams,
            key="editor_teams",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "team_id": st.column_config.NumberColumn("ID", disabled=True),
                "access_pin": st.column_config.TextColumn("4-Digit PIN", max_chars=4),
            }
        )
        
        if st.button("Save Teams Table", type="primary"):
            changes = st.session_state["editor_teams"]
            apply_table_changes("teams", "team_id", edited_teams, df_teams, changes)

    # --- 3. VENUES EDITOR ---
    with tab_venues:
        st.subheader("Manage Locations & Fields")
        df_venues = pd.read_sql("SELECT * FROM venues", conn)
        
        edited_venues = st.data_editor(
            df_venues,
            key="editor_venues",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "venue_id": st.column_config.NumberColumn("ID", disabled=True),
            }
        )
        
        if st.button("Save Venues Table", type="primary"):
            changes = st.session_state["editor_venues"]
            apply_table_changes("venues", "venue_id", edited_venues, df_venues, changes)

    # --- 4. DIVISIONS EDITOR ---
    with tab_divisions:
        st.subheader("Manage Tournament Divisions")
        df_divisions = pd.read_sql("SELECT * FROM divisions", conn)
        
        edited_divisions = st.data_editor(
            df_divisions,
            key="editor_divisions",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "division_id": st.column_config.NumberColumn("ID", disabled=True),
            }
        )
        
        if st.button("Save Divisions Table", type="primary"):
            changes = st.session_state["editor_divisions"]
            apply_table_changes("divisions", "division_id", edited_divisions, df_divisions, changes)

    conn.close()
    