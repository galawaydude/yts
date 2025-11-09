import os
import logging
from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config
from celery import Celery
from celery.signals import after_setup_logger
import redis
from werkzeug.middleware.proxy_fix import ProxyFix

logger = logging.getLogger(__name__)

# ============================================================
# FLASK APP INITIALIZATION
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

# --- CRITICAL FIX FOR CLOUD RUN ---
# Trust HTTPS headers from Google's load balancer
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# ----------------------------------

# ============================================================
# REDIS CONNECTION
# ============================================================
try:
    redis_conn = redis.from_url(
        app.config['CELERY_BROKER_URL'],
        decode_responses=True
    )
    redis_conn.ping()
    logger.info(f"✅ Connected to Redis at {app.config['CELERY_BROKER_URL']}")
except Exception as e:
    logger.critical(f"❌ Failed to connect to Redis: {e}")
    redis_conn = None

# ============================================================
# SECRET KEY
# ============================================================
if not app.secret_key:
    app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'

# ============================================================
# CORS CONFIGURATION (🔥 hardcoded for production frontend)
# ============================================================
allowed_origins = [
    "https://transcriptsearch-451918.web.app",  # Firebase frontend (prod)
    "http://localhost:3000"                     # local dev
]

logger.info(f"🌍 CORS allowed origins: {allowed_origins}")

CORS(
    app,
    supports_credentials=True,
    origins=allowed_origins,
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)

# ============================================================
# ELASTICSEARCH CONNECTION
# ============================================================
es_username = app.config.get('ELASTIC_USER')
es_password = app.config.get('ELASTIC_PASSWORD')
es_endpoint = app.config.get('ELASTIC_ENDPOINT_URL')

es_config = {
    'request_timeout': 30,
    'max_retries': 10,
    'retry_on_timeout': True
}

if es_endpoint and es_password and es_username:
    logger.info(f"🔗 Connecting to Elastic Cloud at {es_endpoint}...")
    try:
        es = Elasticsearch(
            [es_endpoint],
            basic_auth=(es_username, es_password),
            verify_certs=True,
            **es_config
        )
        if es.ping():
            logger.info("✅ Connected to Elastic Cloud successfully!")
        else:
            raise Exception("Failed to ping Elastic Cloud")
    except Exception as e:
        logger.critical(f"❌ Error connecting to Elastic Cloud: {str(e)}")
        raise e
else:
    logger.info("ℹ️ Using local Elasticsearch at localhost:9200...")
    es_url = app.config.get('ELASTICSEARCH_URL')
    try:
        es = Elasticsearch([es_url], **es_config)
        if es.ping():
            logger.info("✅ Connected to local Elasticsearch successfully!")
        else:
            raise Exception("Failed to ping local Elasticsearch")
    except Exception as e:
        logger.critical(f"❌ Error connecting to local Elasticsearch: {str(e)}")
        raise e

# ============================================================
# CELERY CONFIGURATION
# ============================================================
celery = Celery(
    app.name,
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['RESULT_BACKEND']
)
celery.conf.update(app.config)

logger.info(f"⚙️ Celery broker: {app.config['CELERY_BROKER_URL']}")

@after_setup_logger.connect
def setup_celery_logging(logger, **kwargs):
    logging.basicConfig(level=logging.INFO)
    logger.info("📜 Celery worker logging configured.")

# ============================================================
# LOCAL DEVELOPMENT SETTINGS
# ============================================================
if not app.config['PRODUCTION']:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    logger.info("🔧 OAuth insecure transport enabled (local dev)")

# ============================================================
# IMPORT ROUTES AND TASKS
# ============================================================
from app import routes, tasks
