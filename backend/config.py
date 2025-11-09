import os
from dotenv import load_dotenv
import redis

load_dotenv()

class Config:
    # ==============================
    # Core Flask Configuration
    # ==============================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    
    # ==============================
    # Authentication (Google OAuth)
    # ==============================
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI') or 'http://localhost:5000/api/auth/callback'
    
    # ==============================
    # External Services (Elastic & YouTube)
    # ==============================
    ELASTIC_ENDPOINT_URL = os.environ.get('ELASTIC_ENDPOINT_URL')
    ELASTIC_USER = os.environ.get('ELASTIC_USER')
    ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD')
    # Fallback for local development if needed
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # ==============================
    # Connectivity & CORS
    # ==============================
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:3000'

    # ==============================
    # Session & Cookie Configuration (CRITICAL FIX)
    # ==============================
    SESSION_TYPE = 'redis'
    # Use the same Redis URL as Celery for simplicity, or a dedicated one if you have it.
    # Ensure your .env has ?ssl_cert_reqs=none at the end of this URL for cloud.
    SESSION_REDIS = redis.from_url(os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0')

    # "Nuclear Option" for Cookies:
    # If we are running in production (not localhost), FORCE the most permissive secure settings.
    # This overcomes issues where browsers block cookies due to complex proxy hops (Firebase -> Cloud Run).
    if os.environ.get('FRONTEND_URL') and 'localhost' not in os.environ.get('FRONTEND_URL'):
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_SAMESITE = 'None'
        SESSION_COOKIE_HTTPONLY = True
        # Optional: helps sometimes if paths get confused by proxies
        SESSION_COOKIE_PATH = '/' 
    else:
        # Local development defaults (safe for http://localhost)
        SESSION_COOKIE_SECURE = False
        SESSION_COOKIE_SAMESITE = 'Lax'
        SESSION_COOKIE_HTTPONLY = True

    # ==============================
    # Background Tasks (Celery/Redis)
    # ==============================
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND') or 'redis://localhost:6379/0'

    # ==============================
    # Miscellaneous
    # ==============================
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))