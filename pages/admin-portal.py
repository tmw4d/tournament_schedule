import streamlit as st

st.set_page_config(page_title="Admin Portal", page_icon="🛠️", layout="wide")

# Check authentication state
if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") != "Admin":
    st.error("🚫 Access Denied. Please log in as an Administrator using the sidebar PIN portal.")
    st.stop() # Halts execution of the rest of the page

st.title("🛠️ Tournament Data Manager (Admin)")
st.markdown("Welcome to the admin dashboard. Edit tables below and click save.")

# Render your st.data_editor tabs here...