import os
import json
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from flask import url_for, session, redirect, request
import googleapiclient.discovery
from app import app

logger = logging.getLogger(__name__)

# OAuth configuration
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.readonly'
]
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def get_client_config():
    """Get client configuration from environment variables or file."""
    # First try to get from environment variables (for Railway deployment)
    if app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'):
        logger.info("Using Google OAuth credentials from environment variables")
        return {
            "web": {
                "client_id": app.config.get('GOOGLE_CLIENT_ID'),
                "client_secret": app.config.get('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [app.config.get('OAUTH_REDIRECT_URI')]
            }
        }
    
    # Fallback to client_secret.json file (for local development)
    client_secrets_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secret.json")
    if os.path.exists(client_secrets_file):
        logger.info(f"Using Google OAuth credentials from {client_secrets_file}")
        with open(client_secrets_file, 'r') as f:
            return json.load(f)
    
    logger.error("No Google OAuth credentials found!")
    return None

def get_auth_url():
    """Generate the authorization URL for Google OAuth."""
    try:
        client_config = get_client_config()
        if not client_config:
            raise Exception("No client configuration available")
        
        # Use the redirect URI from config
        redirect_uri = app.config.get('OAUTH_REDIRECT_URI')
        logger.info(f"Using redirect URI: {redirect_uri}")
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        session['state'] = state
        logger.info(f"Generated authorization URL: {authorization_url}")
        return authorization_url
    except Exception as e:
        logger.error(f"Error in get_auth_url: {e}")
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