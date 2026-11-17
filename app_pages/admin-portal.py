import streamlit as st
import tournament_auth
import admin as admin_dashboard

if not tournament_auth.is_admin():
    st.error("Administrator access is required for this page.")
    st.stop()

admin_dashboard.render_admin_dashboard()
