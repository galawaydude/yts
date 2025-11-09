import os
from dotenv import load_dotenv
import redis

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI')
    
    # Elastic & YouTube
    ELASTIC_ENDPOINT_URL = os.environ.get('ELASTIC_ENDPOINT_URL')
    ELASTIC_USER = os.environ.get('ELASTIC_USER')
    ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD')
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # Frontend
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'

    # --- SIMPLIFIED SESSION CONFIG ---
    SESSION_TYPE = 'redis'
    SESSION_REDIS = redis.from_url(os.environ.get('CELERY_BROKER_URL'))
    
    # Standard secure settings for same-domain (Firebase) hosting
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'  # 'Lax' is much more reliable than 'None' when on the same domain
    # IMPORTANT: Do NOT set SESSION_COOKIE_DOMAIN. Let Flask figure it out.
    # ---------------------------------

    # Other
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND')