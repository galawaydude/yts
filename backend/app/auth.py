import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from flask import url_for, session, redirect, request
import googleapiclient.discovery

# OAuth configuration
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secret.json")
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.readonly'
]
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def get_auth_url():
    """Generate the authorization URL for Google OAuth."""
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('callback', _external=True)
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        session['state'] = state
        return authorization_url
    except Exception as e:
        print(f"Error in get_auth_url: {e}")
        raise

def get_credentials():
    """Get credentials from session."""
    if 'credentials' not in session:
        return None
        
    credentials = Credentials(
        **session['credentials']
    )
    
    return credentials

def build_youtube_client():
    """Build and return a YouTube API client."""
    credentials = get_credentials()
    if not credentials:
        return None
        
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, 
        API_VERSION, 
        credentials=credentials
    ) 