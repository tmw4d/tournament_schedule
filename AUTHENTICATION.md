# Optional sign-in

Visitors can browse schedules and choose a favorite division and team without
signing in. Favorites are stored in the current browser session. The Admin page
appears in navigation only for signed-in addresses listed in `ADMIN_EMAILS`.

To enable Google sign-in, create `.streamlit/secrets.toml` for local development
and add the same values to your app host's secrets settings when deploying:

```toml
ADMIN_EMAILS = ["admin@example.com"]

[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "replace-with-a-long-random-secret"

[auth.google]
client_id = "your-google-oauth-client-id"
client_secret = "your-google-oauth-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Set `redirect_uri` to the deployed app's URL followed by `/oauth2callback`, and
register that URL with the Google OAuth client. Keep `secrets.toml` out of
version control. If an OAuth login is configured but the signed-in email is not
listed as an admin, that user still gets public access but does not see Admin.
