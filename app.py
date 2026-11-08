import streamlit as st
import yaml
from pathlib import Path
import sqlite3

# --- Page Configuration ---
st.set_page_config(
    page_title="Tournament Tracker",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Load Configuration ---
@st.cache_data
def load_config():
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {
        "tournament_name": "Default Tournament",
        "tagline": "Configure config.yaml to customize this app.",
        "description": "Please add a config.yaml file.",
        "contact": {"director_name": "Organizer", "email": "admin@example.com", "phone": "555-0199"},
        "locations": [],
        "divisions": []
    }

config = load_config()

# --- Custom Styling ---
st.markdown("""
    <style>
    .card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

import streamlit as st

# --- Sidebar login portal ---
st.sidebar.header("🔐 User Portal")

ADMIN_PIN = "9999"

with st.sidebar.expander("🔑 Log In / Enter PIN", expanded=not st.session_state.get("authenticated", False)):
    with st.form("login_form"):
        entered_pin = st.text_input("Enter PIN", type="password", max_chars=4)
        submit_login = st.form_submit_button("Verify")

    if submit_login:
        if entered_pin == ADMIN_PIN:
            st.session_state["authenticated"] = True
            st.session_state["user_role"] = "Admin"
            st.success("Logged in as Admin!")
            st.rerun()
        elif len(entered_pin) == 4:
            # Quick check against SQLite teams table
            import sqlite3
            conn = sqlite3.connect("tournament.db")
            cursor = conn.cursor()
            cursor.execute("SELECT team_id, name FROM teams WHERE access_pin = ?", (entered_pin,))
            team = cursor.fetchone()
            conn.close()
            
            if team:
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = "Team"
                st.session_state["team_id"] = team[0]
                st.session_state["team_name"] = team[1]
                st.success(f"Logged in: {team[1]}")
                st.rerun()
            else:
                st.error("Invalid PIN.")
        else:
            st.error("Enter a valid 4-digit PIN.")

if st.session_state.get("authenticated", False):
    role = st.session_state.get("user_role")
    if role == "Admin":
        st.sidebar.info("🛠️ Role: Administrator")
    else:
        st.sidebar.info(f"🛡️ Role: {st.session_state.get('team_name')}")
        
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

st.sidebar.markdown("---")

# --- Main Landing Page Content ---
st.title(config.get("tournament_name", "Tournament Tracker"))
st.markdown(f"### {config.get('tagline', '')}")
st.markdown(config.get("description", ""))

st.markdown("---")

# Layout columns for Divisions & Locations
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("### 🏆 Division Schedules")
    st.markdown("Select a division below to view matchups, game times, field locations, and live pool standings:")
    
    for div in config.get("divisions", []):
        # Using Streamlit query params or radio/tabs for navigation in multi-page setups
        if st.button(f"📅 View {div['name']} Schedule & Standings", use_container_width=True):
            st.session_state["selected_division"] = div["key"]
            st.info(f"Navigating to {div['name']}... (Link this to your division page router)")

with col2:
    st.markdown("### 📍 Tournament Venues & Locations")
    st.markdown("All matches are distributed across our primary host facilities:")
    
    for loc in config.get("locations", []):
        st.markdown(f"""
        <div class="card">
            <strong>{loc['name']}</strong><br>
            📍 {loc['address']}<br>
            <a href="{loc['map_link']}" target="_blank">Open in Google Maps ↗</a>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Contact Footer
st.markdown("### 📞 Contact & Support")
contact = config.get("contact", {})
st.markdown(f"""
Need assistance on-site? Reach out to tournament administration:
* **Director / HQ:** {contact.get('director_name')}
* **Email:** {contact.get('email')}
* **Phone:** {contact.get('phone')}
""")
