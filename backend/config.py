import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ==============================
    # Core Flask Configuration
    # ==============================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    # Defaults to False in production, useful for local debugging
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # ==============================
    # Authentication (Google OAuth)
    # ==============================
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    # In production (VM), this will likely be https://your-new-domain.com/api/auth/callback
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI') or 'http://localhost:5000/api/auth/callback'
    
    # ==============================
    # External Services (Elastic & YouTube)
    # ==============================
    # Option 1: Cloud Elastic (if you still use it)
    ELASTIC_ENDPOINT_URL = os.environ.get('ELASTIC_ENDPOINT_URL')
    ELASTIC_USER = os.environ.get('ELASTIC_USER')
    ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD')
    
    # Option 2: Local/Docker Elastic (preferred for your new VM setup)
    # In docker-compose, this will be 'http://elasticsearch:9200'
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # ==============================
    # Connectivity & CORS
    # ==============================
    # Provides a default, but allows overriding via ENV.
    # For the unified VM setup, this might just be your domain.
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or "http://localhost:3000"

    # ==============================
    # Session & Cookie Configuration
    # ==============================
    # We use 'Lax' now because on the VM, frontend and backend will share the same domain.
    # secure=True ensures it only works over HTTPS (which we will set up with Let's Encrypt).
    SESSION_COOKIE_SECURE = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax' 
    # SESSION_COOKIE_DOMAIN is intentionally omitted so Flask handles it automatically.

    # ==============================
    # Background Tasks (Celery)
    # ==============================
    # In docker-compose, this will be 'redis://redis:6379/0'
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND') or 'redis://localhost:6379/0'

    # ==============================
    # Miscellaneous
    # ==============================
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))