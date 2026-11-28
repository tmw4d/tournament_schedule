from pathlib import Path

import streamlit as st
import yaml

import preferences
import database
import tournament_auth
import tournament_s3


st.set_page_config(
    page_title="Tournament Tracker",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_config():
    config_path = Path("config.yaml")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}
    return {
        "tournament_name": "Tournament Tracker",
        "tagline": "Configure config.yaml to customize this app.",
        "description": "Please add a config.yaml file.",
        "contact": {},
        "locations": [],
        "divisions": [],
    }


config = load_config()


@st.cache_resource(show_spinner="Loading tournament database")
def initialize_tournament_database():
    return tournament_s3.initialize_primary_database(st.secrets)


database_storage_status = initialize_tournament_database()
st.session_state.setdefault("database_storage_status", database_storage_status)
database.init_db()
divisions = config.get("divisions", [])
tournament_auth.resolve_optional_auth()


def render_home():
    st.title(config.get("tournament_name", "Tournament Tracker"))
    st.markdown(f"### {config.get('tagline', '')}")
    st.markdown(config.get("description", ""))

    favorite_division = st.session_state.get("favorite_division")
    favorite_team = st.session_state.get("favorite_team")
    if favorite_division or favorite_team:
        with st.container(border=True):
            st.subheader("Your favorites")
            if favorite_division:
                st.write(f"Division: **{favorite_division}**")
            if favorite_team:
                st.write(f"Team: **{favorite_team['name']}**")

    st.divider()
    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Division schedules")
        st.write("Choose a division to see its schedule and standings.")
        for division in divisions:
            page_path = f"app_pages/{division['key']}.py"
            if Path(page_path).exists():
                st.page_link(
                    page_path,
                    label=f"{division['name']} schedule and standings",
                    icon=":material/calendar_month:",
                )

        if tournament_auth.is_admin():
            st.divider()
            st.subheader("Admin tools")
            st.write("Manage tournament setup or enter game scores.")
            st.page_link(
                "app_pages/admin-portal.py",
                label="Open admin data manager",
                icon=":material/admin_panel_settings:",
            )
            st.page_link(
                "app_pages/scores.py",
                label="Open score entry",
                icon=":material/edit_note:",
            )

    with right:
        st.subheader("Tournament venues")
        for location in config.get("locations", []):
            with st.container(border=True):
                st.markdown(f"**{location['name']}**")
                st.write(location.get("address", ""))
                if location.get("map_link"):
                    st.link_button("Open in Google Maps", location["map_link"])

    st.divider()
    contact = config.get("contact", {})
    st.subheader("Contact and support")
    st.markdown(
        "Need assistance on-site? Reach out to tournament administration:\n"
        f"\n- **Director / HQ:** {contact.get('director_name', '')}"
        f"\n- **Email:** {contact.get('email', '')}"
        f"\n- **Phone:** {contact.get('phone', '')}"
    )


page_by_key = {
    "div_a": "app_pages/div_a.py",
    "div_b": "app_pages/div_b.py",
    "div_c": "app_pages/div_c.py",
}
pages = [
    st.Page(
        render_home,
        title="Home",
        icon=":material/home:",
        help="Tournament overview, division schedules, venues, and contact details.",
        url_path="home",
        default=True,
    )
]
top_navigation = [(pages[0], "Home", ":material/home:")]

for division in divisions:
    page_path = page_by_key.get(division.get("key"))
    if page_path and Path(page_path).exists():
        pages.append(
            st.Page(
                page_path,
                title=division["name"],
                icon=":material/sports:",
                help=f"View the {division['name']} schedule and pool standings.",
                url_path=division["key"],
            )
        )
        top_navigation.append((pages[-1], division["name"], ":material/sports:"))

if tournament_auth.is_admin():
    score_page = st.Page(
        "app_pages/scores.py",
        title="Score entry",
        icon=":material/edit_note:",
        help="Enter scores and update game status by division.",
        url_path="scores",
    )
    pages.append(score_page)
    top_navigation.append((score_page, "Score entry", ":material/edit_note:"))
    data_page = st.Page(
            "app_pages/admin-portal.py",
            title="Admin",
            icon=":material/admin_panel_settings:",
            help="Administrator tools for tournament data.",
            url_path="admin",
    )
    pages.append(data_page)
    top_navigation.append((data_page, "Data manager", ":material/admin_panel_settings:"))

navigation = st.navigation(pages, position="sidebar")
with st.container():
    nav_columns = st.columns(len(top_navigation), vertical_alignment="center")
    for column, (page, label, icon) in zip(nav_columns, top_navigation):
        with column:
            st.page_link(page, label=label, icon=icon, width="stretch")
st.divider()
tournament_auth.render_account_sidebar()
preferences.render_favorite_controls(divisions)
navigation.run()
