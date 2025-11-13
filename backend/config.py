import os
import redis
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # Google Auth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI')

    # Elastic & YouTube
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    ELASTIC_ENDPOINT_URL = os.environ.get('ELASTIC_ENDPOINT_URL')
    ELASTIC_USER = os.environ.get('ELASTIC_USER')
    ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

    # Webshare Proxies (Residential)
    # Note: WEBSHARE_FILTER_LOCATIONS has been removed
    WEBSHARE_PROXY_USERNAME = os.environ.get('WEBSHARE_PROXY_USERNAME')
    WEBSHARE_PROXY_PASSWORD = os.environ.get('WEBSHARE_PROXY_PASSWORD')

    # Frontend URL (for CORS)
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or "http://localhost:3000"

    # Redis & Sessions
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_REDIS = redis.from_url(REDIS_URL)
    SESSION_COOKIE_SECURE = os.environ.get('PRODUCTION', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    RESULT_BACKEND = REDIS_URL
    PRODUCTION = os.environ.get('PRODUCTION', 'False').lower() == 'true'