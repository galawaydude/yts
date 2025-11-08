import os
from dotenv import load_dotenv
import redis

load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Elasticsearch
    ELASTIC_ENDPOINT_URL = os.environ.get('ELASTIC_ENDPOINT_URL')
    ELASTIC_USER = os.environ.get('ELASTIC_USER')
    ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD')
    # Fallback for local
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    
    # YouTube API
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # URLs
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI') or 'http://localhost:5000/api/auth/callback'
    
    # --- SESSION CONFIGURATION (THE FIX) ---
    SESSION_TYPE = 'redis'
    # We need a dedicated Redis connection for sessions
    SESSION_REDIS = redis.from_url(os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0')
    
    # CRITICAL: If we are in production (FRONTEND_URL is set to something real),
    # we MUST force these settings for cross-domain cookies to work.
    if os.environ.get('FRONTEND_URL') and 'localhost' not in os.environ.get('FRONTEND_URL'):
        # Production Settings (Cloud Run -> Cloudflare Pages)
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_SAMESITE = 'None'
    else:
        # Local Development Settings
        SESSION_COOKIE_SECURE = False
        SESSION_COOKIE_SAMESITE = 'Lax'
        
    SESSION_COOKIE_HTTPONLY = True
    # ---------------------------------------
    
    # Other Configs
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND') or 'redis://localhost:6379/0'