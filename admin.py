from contextlib import closing
import sqlite3

import pandas as pd
import streamlit as st

import database


def _connection():
    conn = sqlite3.connect(database.DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _delete_button(conn, label, record_id, query, params, key):
    if st.button(f"Delete selected {label.lower()}", key=key):
        try:
            conn.execute(query, params)
            conn.commit()
            st.success(f"Deleted {label.lower()}.")
            st.rerun()
        except sqlite3.IntegrityError:
            conn.rollback()
            st.error(f"This {label.lower()} is still in use. Remove its dependent records or references first.")
        except sqlite3.Error as error:
            conn.rollback()
            st.error(f"Could not delete {label.lower()}: {error}")


def _editor(conn, table, key, order, label, columns=None):
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY {order}", conn)
    for column in df.columns:
        if column.endswith("_id"):
            df[column] = df[column].fillna(0)
        if column.startswith("source_outcome_"):
            df[column] = df[column].fillna("—")
    edited = st.data_editor(
        df, key=f"edit_{table}", num_rows="dynamic", width="stretch",
        column_config=columns or {}, alt=f"Edit {label}", hide_index=True,
    )
    if st.button(f"Save {label}", key=f"save_{table}", type="primary"):
        changes = st.session_state[f"edit_{table}"]
        try:
            with conn:
                for idx, updates in changes.get("edited_rows", {}).items():
                    record = df.iloc[int(idx)][key]
                    assignments = ", ".join(f"{col}=?" for col in updates)
                    values = [None if (col.endswith("_id") and value == 0) or (col.startswith("source_outcome_") and value == "—") else value for col,value in updates.items()]
                    conn.execute(f"UPDATE {table} SET {assignments} WHERE {key}=?", [*values, record])
                for idx in changes.get("deleted_rows", []):
                    conn.execute(f"DELETE FROM {table} WHERE {key}=?", (df.iloc[int(idx)][key],))
                for row in changes.get("added_rows", []):
                    row = {k: (None if (k.endswith("_id") and v == 0) or (k.startswith("source_outcome_") and v == "—") else v) for k, v in row.items() if pd.notna(v) and k != key}
                    if row:
                        fields = ", ".join(row)
                        conn.execute(f"INSERT INTO {table} ({fields}) VALUES ({','.join('?' for _ in row)})", list(row.values()))
            st.success(f"Saved {label}.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not save {label}: {error}")


def _render_divisions(conn):
    st.subheader("Divisions")
    divisions = conn.execute("""SELECT division_id,name,tournament,description,
        pool_game_length_minutes,playoff_game_length_minutes
        FROM divisions ORDER BY name""").fetchall()
    st.dataframe(
        pd.DataFrame([{
            "Division": row[1], "Tournament": row[2], "Description": row[3],
            "Pool length (min)": row[4], "Playoff length (min)": row[5],
        } for row in divisions]),
        hide_index=True,
        width="stretch",
        alt="Tournament divisions",
    )

    with st.form("new_division"):
        name = st.text_input("Division name")
        tournament = st.text_input("Tournament", value="Tournament")
        description = st.text_area("Division description")
        st.caption("Set a duration to 0 to leave it unset.")
        pool_length = st.number_input("Pool game length (minutes)", min_value=0, max_value=240, value=0, step=1)
        playoff_length = st.number_input("Playoff game length (minutes)", min_value=0, max_value=240, value=0, step=1)
        add = st.form_submit_button("Add division", type="primary")
    if add and name.strip():
        try:
            conn.execute("""INSERT INTO divisions
                (name,tournament,description,pool_game_length_minutes,playoff_game_length_minutes)
                VALUES (?,?,?,?,?)""", (
                    name.strip(), tournament.strip(), description.strip() or None,
                    pool_length or None, playoff_length or None,
                ))
            conn.commit()
            st.success("Division added.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not add division: {error}")

    divisions = conn.execute("""SELECT division_id,name,tournament,description,
        pool_game_length_minutes,playoff_game_length_minutes
        FROM divisions ORDER BY name""").fetchall()
    if not divisions:
        st.info("Add a division to begin.")
        return
    labels = {row[0]: f"{row[1]} · {row[2]}" for row in divisions}
    selected = st.selectbox("Edit division", list(labels), format_func=labels.get, key="division_to_edit")
    current = next(row for row in divisions if row[0] == selected)
    with st.form("edit_division"):
        new_name = st.text_input("Division name", value=current[1])
        new_tournament = st.text_input("Tournament", value=current[2])
        new_description = st.text_area("Division description", value=current[3] or "")
        st.caption("Set a duration to 0 to leave it unset.")
        new_pool_length = st.number_input(
            "Pool game length (minutes)", min_value=0, max_value=240,
            value=current[4] or 0, step=1,
        )
        new_playoff_length = st.number_input(
            "Playoff game length (minutes)", min_value=0, max_value=240,
            value=current[5] or 0, step=1,
        )
        save = st.form_submit_button("Save division")
    if save:
        try:
            conn.execute("""UPDATE divisions SET name=?,tournament=?,description=?,
                pool_game_length_minutes=?,playoff_game_length_minutes=? WHERE division_id=?""", (
                    new_name.strip(), new_tournament.strip(), new_description.strip() or None,
                    new_pool_length or None, new_playoff_length or None, selected,
                ))
            conn.commit()
            st.success("Division updated.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not update division: {error}")
    delete_id = st.selectbox("Division to delete", list(labels), format_func=labels.get, key="delete_division_choice")
    _delete_button(conn,"division",delete_id,"DELETE FROM divisions WHERE division_id=?",(delete_id,),"delete_division")


def _render_pools(conn, division_labels):
    st.subheader("Pools")
    if not division_labels:
        st.info("Create a division first.")
        return
    with st.form("new_pool"):
        division_id = st.selectbox("Division", list(division_labels), format_func=division_labels.get)
        name = st.text_input("Pool name")
        member_count = st.number_input("Number of members", min_value=1, max_value=64, value=4, step=1)
        add = st.form_submit_button("Create pool and slots", type="primary")
    if add and name.strip():
        try:
            with conn:
                cur = conn.execute("INSERT INTO pools(division_id,name,num_members) VALUES (?,?,?)", (division_id, name.strip(), member_count))
                conn.executemany("INSERT INTO pool_members(pool_id,division_id,position) VALUES (?,?,?)", [(cur.lastrowid, division_id, position) for position in range(1, member_count + 1)])
            st.success(f"Created {name.strip()} with {member_count} member slots.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not create pool: {error}")

    pools = conn.execute("SELECT p.pool_id,p.name,p.num_members,d.name,p.division_id FROM pools p JOIN divisions d USING(division_id) ORDER BY d.name,p.name").fetchall()
    if pools:
        st.dataframe(pd.DataFrame([{"Pool": r[1], "Division": r[3], "Member slots": r[2]} for r in pools]), hide_index=True, width="stretch", alt="Tournament pools")
        pool_options = {r[0]: f"{r[3]} · {r[1]}" for r in pools}
        selected_pool = st.selectbox("Edit pool", list(pool_options), format_func=pool_options.get)
        current = next(r for r in pools if r[0] == selected_pool)
        with st.form("edit_pool"):
            st.text_input("Division", value=current[3], disabled=True)
            updated_name = st.text_input("Pool name", value=current[1])
            updated_count = st.number_input("Number of member slots", min_value=1, max_value=64, value=max(1,current[2]), step=1)
            save_pool = st.form_submit_button("Save pool")
        if save_pool:
            try:
                with conn:
                    if updated_count < current[2]:
                        conn.execute("DELETE FROM pool_members WHERE pool_id=? AND position>? AND team_id IS NULL", (selected_pool, updated_count))
                        remaining = conn.execute("SELECT COUNT(*) FROM pool_members WHERE pool_id=? AND position>?", (selected_pool, updated_count)).fetchone()[0]
                        if remaining:
                            raise ValueError("Clear team assignments in the slots being removed before reducing the member count.")
                    elif updated_count > current[2]:
                        conn.executemany("INSERT INTO pool_members(pool_id,division_id,position) VALUES (?,?,?)", [(selected_pool,current[4],pos) for pos in range(current[2]+1,updated_count+1)])
                    conn.execute("UPDATE pools SET name=?,num_members=? WHERE pool_id=?", (updated_name.strip(),updated_count,selected_pool))
                st.success("Pool updated.")
                st.rerun()
            except (sqlite3.Error, ValueError) as error:
                st.error(f"Could not update pool: {error}")
        delete_pool = st.selectbox("Pool to delete", list(pool_options), format_func=pool_options.get, key="delete_pool_choice")
        _delete_button(conn,"pool",delete_pool,"DELETE FROM pools WHERE pool_id=?",(delete_pool,),"delete_pool")


def _render_pool_member_slots(conn, pool_rows):
    st.subheader("Pool member slots")
    st.caption("Pool creation makes numbered slots. Assign teams here; an unassigned slot remains available.")
    if not pool_rows:
        st.info("Create a pool first.")
        return
    division_names = {r[0]: r[1] for r in conn.execute("SELECT division_id,name FROM divisions ORDER BY name")}
    division_id = st.selectbox("Division", list(division_names), format_func=division_names.get, key="pool_member_division")
    available_pools = [r for r in pool_rows if r[3] == division_id]
    if not available_pools:
        st.info("Create a pool for this division first.")
        return
    labels = {r[0]: r[1] for r in available_pools}
    pool_id = st.selectbox("Pool", list(labels), format_func=labels.get, key=f"assign_pool_{division_id}")
    teams = conn.execute("SELECT team_id,name,city,state FROM teams WHERE division_id=? ORDER BY name,city,state,team_id", (division_id,)).fetchall()
    team_labels = {}
    label_to_team_id = {}
    for team_id, name, city, state in teams:
        label = name
        location = ", ".join(part for part in (city, state) if part)
        if location:
            label = f"{name} · {location}"
        base_label = label
        suffix = 2
        while label in label_to_team_id or label == "— Unassigned —":
            label = f"{base_label} ({suffix})"
            suffix += 1
        team_labels[team_id] = label
        label_to_team_id[label] = team_id
    slots = conn.execute("""SELECT pm.position,pm.team_id FROM pool_members pm
        WHERE pm.pool_id=? ORDER BY pm.position""", (pool_id,)).fetchall()
    frame = pd.DataFrame([{"Position": pos, "Team": team_labels.get(team_id, "— Unassigned —")} for pos,team_id in slots])
    edited = st.data_editor(frame, key=f"pool_slot_editor_{pool_id}", hide_index=True, num_rows="fixed", width="stretch",
        column_config={"Position": st.column_config.NumberColumn("Position",disabled=True),
                       "Team": st.column_config.SelectboxColumn("Team",options=["— Unassigned —",*label_to_team_id],required=True)},
        alt=f"Assign teams to {labels[pool_id]} slots")
    if st.button("Save pool assignments", key=f"save_pool_slots_{pool_id}", type="primary"):
        try:
            with conn:
                for _, row in edited.iterrows():
                    team_id = label_to_team_id.get(row["Team"])
                    conn.execute("UPDATE pool_members SET team_id=? WHERE pool_id=? AND position=?", (team_id,pool_id,int(row["Position"])))
            st.success("Pool assignments saved.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not save pool assignments: {error}")


def _render_teams(conn, division_labels):
    st.subheader("Teams")
    if not division_labels:
        st.info("Create a division before adding teams.")
        return
    division_id = st.selectbox("Division", list(division_labels), format_func=division_labels.get, key="teams_division")
    frame = pd.read_sql_query("""SELECT team_id,name,city,state,payment_received_date,
        payment_channel,payment_amount,access_pin FROM teams
        WHERE division_id=? ORDER BY name""", conn, params=(division_id,))
    frame["payment_channel"] = frame["payment_channel"].fillna("—")
    edited = st.data_editor(frame, key=f"teams_editor_{division_id}", num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "team_id":None,
            "name":st.column_config.TextColumn("Team name",required=True),
            "city":st.column_config.TextColumn("City"),
            "state":st.column_config.TextColumn("State",max_chars=2),
            "payment_received_date":st.column_config.DateColumn("Payment received"),
            "payment_channel":st.column_config.SelectboxColumn("Payment channel",options=["—","PayPal","Venmo","Zelle","Check"]),
            "payment_amount":st.column_config.NumberColumn("Payment amount",min_value=0,step=0.01,format="$%.2f"),
            "access_pin":st.column_config.TextColumn("Access PIN",max_chars=4),
        },
        alt=f"Teams in {division_labels[division_id]}")
    if st.button("Save teams", key=f"save_teams_{division_id}", type="primary"):
        changes=st.session_state[f"teams_editor_{division_id}"]
        try:
            with conn:
                for idx,updates in changes.get("edited_rows",{}).items():
                    team_id=frame.iloc[int(idx)]["team_id"]
                    assignments=", ".join(f"{column}=?" for column in updates)
                    values=[None if pd.isna(value) or (col=="payment_channel" and value=="—") else value for col,value in updates.items()]
                    conn.execute(f"UPDATE teams SET {assignments} WHERE team_id=? AND division_id=?",[*values,team_id,division_id])
                for idx in changes.get("deleted_rows",[]):
                    team_id=frame.iloc[int(idx)]["team_id"]
                    conn.execute("UPDATE pool_members SET team_id=NULL WHERE team_id=?",(team_id,))
                    conn.execute("DELETE FROM teams WHERE team_id=? AND division_id=?",(team_id,division_id))
                for row in changes.get("added_rows",[]):
                    if row.get("name"):
                        channel=row.get("payment_channel")
                        if pd.isna(channel) or channel=="—": channel=None
                        def clean(value):
                            return None if pd.isna(value) else value
                        conn.execute("""INSERT INTO teams
                            (name,division_id,city,state,payment_received_date,payment_channel,payment_amount,access_pin)
                            VALUES (?,?,?,?,?,?,?,?)""",
                            (row["name"],division_id,clean(row.get("city")),clean(row.get("state")),clean(row.get("payment_received_date")),channel,clean(row.get("payment_amount")),clean(row.get("access_pin"))))
            st.success("Teams saved.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not save teams: {error}")
    team_rows=conn.execute("SELECT team_id,name,city,state FROM teams WHERE division_id=? ORDER BY name",(division_id,)).fetchall()
    if team_rows:
        team_options={r[0]:r[1]+(f" · {', '.join(x for x in (r[2],r[3]) if x)}" if r[2] or r[3] else "") for r in team_rows}
        delete_team=st.selectbox("Team to delete",list(team_options),format_func=team_options.get,key=f"delete_team_choice_{division_id}")
        if st.button("Delete selected team",key=f"delete_team_{division_id}"):
            try:
                with conn:
                    conn.execute("UPDATE pool_members SET team_id=NULL WHERE team_id=?",(delete_team,))
                    conn.execute("DELETE FROM teams WHERE team_id=? AND division_id=?",(delete_team,division_id))
                st.success("Deleted team. Its pool slot is now unassigned.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("This team is referenced by a game. Update or remove those games before deleting the team.")


def _render_venue_fields(conn, venue_labels):
    st.subheader("Fields at each venue")
    if not venue_labels:
        st.info("Add a venue before defining its fields.")
        return
    venue_id = st.selectbox("Venue", list(venue_labels), format_func=venue_labels.get, key="fields_venue")
    fields=conn.execute("SELECT field_id,name FROM fields WHERE venue_id=? ORDER BY name",(venue_id,)).fetchall()
    st.dataframe(pd.DataFrame([{"Field":row[1]} for row in fields]),hide_index=True,width="stretch",alt=f"Fields at {venue_labels[venue_id]}")
    with st.form(f"add_field_{venue_id}"):
        field_name=st.text_input("New field name")
        add=st.form_submit_button("Add field")
    if add and field_name.strip():
        try:
            conn.execute("INSERT INTO fields(venue_id,name) VALUES (?,?)",(venue_id,field_name.strip()))
            conn.commit()
            st.success("Field added.")
            st.rerun()
        except sqlite3.Error as error:
            st.error(f"Could not add field: {error}")
    if fields:
        field_names={row[0]:row[1] for row in fields}
        field_id=st.selectbox("Field to edit",list(field_names),format_func=field_names.get,key=f"edit_field_choice_{venue_id}")
        with st.form(f"edit_field_{venue_id}"):
            updated_name=st.text_input("Field name",value=field_names[field_id])
            save=st.form_submit_button("Save field name",type="primary")
        if save:
            try:
                conn.execute("UPDATE fields SET name=? WHERE field_id=? AND venue_id=?",(updated_name.strip(),field_id,venue_id))
                conn.commit()
                st.success("Field name saved.")
                st.rerun()
            except sqlite3.Error as error:
                st.error(f"Could not rename field: {error}")
        _delete_button(conn,"field",field_id,"DELETE FROM fields WHERE field_id=? AND venue_id=?",(field_id,venue_id),f"delete_field_{venue_id}")


def _render_games(conn, division_labels, field_labels):
    st.subheader("Games")
    st.caption("Choose a division to enter its games. Teams, pools, and source games are limited to that division.")
    if not division_labels:
        st.info("Create a division before entering games.")
        return
    division_id = st.selectbox("Division", list(division_labels), format_func=division_labels.get, key="games_division")
    saved_message_key = f"games_saved_message_{division_id}"
    if st.session_state.pop(saved_message_key, False):
        st.success("Games saved and verified in the database.")
    frame = pd.read_sql_query("SELECT * FROM games WHERE division_id=? ORDER BY game_code", conn, params=(division_id,))
    source_labels = {
        "unresolved": "TBD",
        "team": "Fixed team",
        "pool_rank": "Final standings place",
        "pool_position": "Pool entry position",
        "game_result": "Winner/loser of another game",
    }
    source_values = {label: source for source,label in source_labels.items()}
    for column in frame.columns:
        if column.endswith("_id"):
            frame[column] = frame[column].fillna(0)
        if column.startswith("source_outcome_"):
            frame[column] = frame[column].fillna("—")
        if column in ("source_type_a", "source_type_b"):
            frame[column] = frame[column].map(lambda value: source_labels.get(value, value))

    teams = conn.execute("SELECT team_id,name,city,state FROM teams WHERE division_id=? ORDER BY name", (division_id,)).fetchall()
    team_labels = {r[0]: f"{r[1]}" + (f" · {', '.join(x for x in (r[2],r[3]) if x)}" if r[2] or r[3] else "") for r in teams}
    used_labels=set()
    for team_id,label in list(team_labels.items()):
        base=label; suffix=2
        while label in used_labels:
            label=f"{base} ({suffix})"; suffix+=1
        team_labels[team_id]=label; used_labels.add(label)
    pools = conn.execute("SELECT pool_id,name FROM pools WHERE division_id=? ORDER BY name", (division_id,)).fetchall()
    pool_labels = {r[0]: r[1] for r in pools}
    source_games = conn.execute("SELECT game_id,game_code FROM games WHERE division_id=? ORDER BY game_code", (division_id,)).fetchall()
    game_labels = {r[0]: r[1] for r in source_games}
    field_to_label = dict(field_labels)
    label_to_field = {label: field_id for field_id,label in field_to_label.items()}
    id_to_label = {
        "field_id": field_to_label,
        "pool_id": dict(pool_labels),
        "source_team_a_id": dict(team_labels), "source_team_b_id": dict(team_labels),
        "source_pool_a_id": dict(pool_labels), "source_pool_b_id": dict(pool_labels),
        "source_game_a_id": dict(game_labels), "source_game_b_id": dict(game_labels),
    }
    label_to_id = {column: {label: value for value,label in mapping.items()} for column,mapping in id_to_label.items()}
    for column,mapping in id_to_label.items():
        if column in frame.columns:
            frame[column] = frame[column].map(lambda value: mapping.get(value, "—") if value else "—")
    for column,mapping in label_to_id.items():
        mapping["—"] = None

    config = {
        "game_id": None,
        "division_id": None,
        "game_code": st.column_config.TextColumn("Game", pinned=True, required=True),
        "pool_id": st.column_config.SelectboxColumn("Pool context", options=["—",*pool_labels.values()]),
        "field_id": st.column_config.SelectboxColumn("Venue · Field", options=["—",*field_to_label.values()]),
        "stage": st.column_config.SelectboxColumn("Stage", options=["Pool","Playoff"]),
        "status": st.column_config.SelectboxColumn("Status", options=["Scheduled","In Progress","Final"]),
        "source_type_a": st.column_config.SelectboxColumn("Side A source", options=list(source_values)),
        "source_team_a_id": st.column_config.SelectboxColumn("Side A fixed team", options=["—",*team_labels.values()]),
        "source_pool_a_id": st.column_config.SelectboxColumn("Side A pool", options=["—",*pool_labels.values()]),
        "source_rank_a": st.column_config.NumberColumn("Side A place / position", min_value=1, step=1),
        "source_game_a_id": st.column_config.SelectboxColumn("Side A source game", options=["—",*game_labels.values()]),
        "source_outcome_a": st.column_config.SelectboxColumn("Side A result", options=["—","winner","loser"]),
        "source_type_b": st.column_config.SelectboxColumn("Side B source", options=list(source_values)),
        "source_team_b_id": st.column_config.SelectboxColumn("Side B fixed team", options=["—",*team_labels.values()]),
        "source_pool_b_id": st.column_config.SelectboxColumn("Side B pool", options=["—",*pool_labels.values()]),
        "source_rank_b": st.column_config.NumberColumn("Side B place / position", min_value=1, step=1),
        "source_game_b_id": st.column_config.SelectboxColumn("Side B source game", options=["—",*game_labels.values()]),
        "source_outcome_b": st.column_config.SelectboxColumn("Side B result", options=["—","winner","loser"]),
        "score_a": st.column_config.NumberColumn("Score A", min_value=0),
        "score_b": st.column_config.NumberColumn("Score B", min_value=0),
    }
    if "venue_id" in frame.columns:
        config["venue_id"] = None
    edited = st.data_editor(frame, key=f"games_editor_{division_id}", num_rows="dynamic", height=650, width="stretch", hide_index=True,
        column_config=config, alt=f"Games in {division_labels[division_id]}")
    if st.button("Save games", key=f"save_games_{division_id}", type="primary"):
        try:
            with conn:
                def database_value(column, value):
                    if pd.isna(value):
                        return None
                    if column in label_to_id:
                        return label_to_id[column].get(value)
                    if column in ("source_type_a", "source_type_b"):
                        return source_values.get(value, value)
                    if column.startswith("source_outcome_") and value == "—":
                        return None
                    return value

                def same_value(left, right):
                    left = database_value("", left)
                    right = database_value("", right)
                    if left is None or right is None:
                        return left is None and right is None
                    return left == right

                # Persist the editor's returned table by stable game_id rather than
                # relying on edited_rows indexes, which can shift with row changes.
                original_ids = set(frame["game_id"].dropna().astype(int))
                returned_ids = set()
                for _, row in edited.iterrows():
                    game_id = row.get("game_id")
                    is_existing = pd.notna(game_id)
                    if is_existing:
                        game_id = int(game_id)
                        returned_ids.add(game_id)
                        original = frame.loc[frame["game_id"] == game_id].iloc[0]
                        values = {
                            column: database_value(column, value)
                            for column, value in row.items()
                            if column not in ("game_id", "division_id")
                            and not same_value(value, original[column])
                        }
                        if values:
                            assignments = ", ".join(f"{column}=?" for column in values)
                            try:
                                cursor = conn.execute(
                                    f"UPDATE games SET {assignments} WHERE game_id=? AND division_id=?",
                                    [*values.values(), game_id, division_id],
                                )
                            except sqlite3.IntegrityError as error:
                                raise sqlite3.IntegrityError(
                                    f"{row['game_code']} ({', '.join(values)}): {error}"
                                ) from error
                            if cursor.rowcount != 1:
                                raise sqlite3.IntegrityError(f"Game {game_id} was not saved.")
                    else:
                        values = {
                            column: database_value(column, value)
                            for column, value in row.items()
                            if column not in ("game_id", "division_id")
                        }
                    if not is_existing and values.get("game_code") and values.get("stage"):
                        values["division_id"] = division_id
                        columns = ", ".join(values)
                        conn.execute(
                            f"INSERT INTO games ({columns}) VALUES ({','.join('?' for _ in values)})",
                            list(values.values()),
                        )

                for game_id in original_ids - returned_ids:
                    conn.execute("DELETE FROM games WHERE game_id=? AND division_id=?", (game_id, division_id))

                # Verify persisted values inside the same transaction before success.
                for _, row in edited.iterrows():
                    game_id = row.get("game_id")
                    if pd.isna(game_id):
                        continue
                    expected = (
                        database_value("source_type_a", row["source_type_a"]),
                        database_value("source_pool_a_id", row["source_pool_a_id"]),
                        database_value("source_rank_a", row["source_rank_a"]),
                    )
                    saved = conn.execute(
                        "SELECT source_type_a,source_pool_a_id,source_rank_a "
                        "FROM games WHERE game_id=? AND division_id=?",
                        (int(game_id), division_id),
                    ).fetchone()
                    if saved is None or tuple(saved) != expected:
                        raise sqlite3.IntegrityError(f"Game {int(game_id)} changes were not persisted.")
            st.session_state[saved_message_key] = True
            st.rerun()
        except (sqlite3.Error, ValueError) as error:
            st.error(f"Could not save games: {error}")
    if source_games:
        delete_game=st.selectbox("Game to delete",list(game_labels),format_func=game_labels.get,key=f"delete_game_choice_{division_id}")
        _delete_button(conn,"game",delete_game,"DELETE FROM games WHERE game_id=? AND division_id=?",(delete_game,division_id),f"delete_game_{division_id}")


def render_admin_dashboard():
    database.init_db()
    st.title("Tournament data manager")
    st.caption("IDs remain internal. Edit tournament facts here; calculated standings and resolved game details are read-only views.")
    tabs = st.tabs(["Divisions", "Pools", "Teams", "Pool members", "Games", "Venues", "Calculated views"])
    with closing(_connection()) as conn:
        division_rows = conn.execute("SELECT division_id,name,tournament FROM divisions ORDER BY name").fetchall()
        division_labels = {r[0]: f"{r[1]} · {r[2]}" for r in division_rows}
        pool_rows = conn.execute("SELECT p.pool_id,p.name,d.name,p.division_id FROM pools p JOIN divisions d USING(division_id) ORDER BY d.name,p.name").fetchall()
        venue_rows = conn.execute("SELECT venue_id,name FROM venues ORDER BY name").fetchall()
        venue_labels = {r[0]: r[1] for r in venue_rows}
        field_rows = conn.execute("SELECT f.field_id,f.name,v.name FROM fields f JOIN venues v USING(venue_id) ORDER BY v.name,f.name").fetchall()
        field_labels = {r[0]: f"{r[2]} · {r[1]}" for r in field_rows}

        with tabs[0]:
            _render_divisions(conn)
        with tabs[1]:
            _render_pools(conn, division_labels)
        with tabs[2]:
            _render_teams(conn, division_labels)
        with tabs[3]:
            _render_pool_member_slots(conn, pool_rows)
        with tabs[4]:
            _render_games(conn, division_labels, field_labels)
        with tabs[5]:
            st.subheader("Venues")
            _editor(conn, "venues", "venue_id", "name", "venues", {"venue_id": None})
            if venue_labels:
                delete_venue=st.selectbox("Venue to delete",list(venue_labels),format_func=venue_labels.get,key="delete_venue_choice")
                _delete_button(conn,"venue",delete_venue,"DELETE FROM venues WHERE venue_id=?",(delete_venue,),"delete_venue")
            _render_venue_fields(conn, venue_labels)
        with tabs[6]:
            st.subheader("Calculated views")
            if not division_labels:
                st.info("Create a division to view calculated standings and games.")
            else:
                calculated_division = st.selectbox(
                    "Division",
                    list(division_labels),
                    format_func=division_labels.get,
                    key="calculated_views_division",
                )
                st.subheader("Calculated pool standings")
                st.dataframe(pd.read_sql_query("""SELECT p.name AS pool,v.position,v.team_name AS team,
                v.wins,v.losses,v.goals_for,v.goals_against,v.goal_differential,v.final_rank
                FROM pool_members_vw v JOIN pools p ON p.pool_id=v.pool_id
                WHERE p.division_id=?
                ORDER BY p.name,v.final_rank,v.position""", conn, params=(calculated_division,)), hide_index=True, width="stretch", alt=f"Calculated pool standings for {division_labels[calculated_division]}")
                st.subheader("Resolved games")
                st.dataframe(pd.read_sql_query("""SELECT g.game_code,d.name AS division,
                a.name AS team_a,g.score_a,b.name AS team_b,g.score_b,
                w.name AS winner,l.name AS loser
                FROM games_vw g JOIN divisions d ON d.division_id=g.division_id
                LEFT JOIN teams a ON a.team_id=g.team_a_id
                LEFT JOIN teams b ON b.team_id=g.team_b_id
                LEFT JOIN teams w ON w.team_id=g.winner_team_id
                LEFT JOIN teams l ON l.team_id=g.loser_team_id
                WHERE g.division_id=?
                ORDER BY d.name,g.game_code""", conn, params=(calculated_division,)), hide_index=True, width="stretch", alt=f"Resolved games for {division_labels[calculated_division]}")
