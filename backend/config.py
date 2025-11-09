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
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # ==============================
    # Connectivity & CORS
    # ==============================
    # 🔒 Hardcoded for production frontend
    FRONTEND_URL = "https://transcriptsearch-451918.web.app"

    # ==============================
    # Session & Cookie Configuration (Client-Side)
    # ==============================
    # These are hardcoded to guarantee stable cross-site OAuth cookie behavior.
    SESSION_COOKIE_SECURE = True             # required for HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "None"         # allows cross-site cookies (Firebase → Cloud Run)
    # -----------------------------

    # ==============================
    # Background Tasks (Celery uses Redis)
    # ==============================
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND') or 'redis://localhost:6379/0'

    # ==============================
    # Miscellaneous
    # ==============================
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
