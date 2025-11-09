import os
import logging
from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config
from celery import Celery
from celery.signals import after_setup_logger
import redis
# NOTE: flask_session is REMOVED. Flask uses native secure cookies now.
from werkzeug.middleware.proxy_fix import ProxyFix

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# --- CRITICAL FIX FOR CLOUD RUN ---
# Tells Flask to trust HTTPS headers from Google's load balancer
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# ----------------------------------

# Redis connection for manual task tracking (Optional but good to keep)
try:
    redis_conn = redis.from_url(
        app.config['CELERY_BROKER_URL'],
        decode_responses=True 
    )
    redis_conn.ping()
    logger.info(f"Connected to Redis for task tracking at {app.config['CELERY_BROKER_URL']}")
except Exception as e:
    logger.critical(f"Failed to connect to Redis: {e}")
    redis_conn = None

# Ensure secret key is set
if not app.secret_key:
    app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'

# Update CORS configuration
allowed_origins = [app.config['FRONTEND_URL']]
if 'http://localhost:3000' not in allowed_origins:
    allowed_origins.append('http://localhost:3000')

logger.info(f"CORS allowed origins: {allowed_origins}")

CORS(
    app, 
    supports_credentials=True, 
    origins=allowed_origins,
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)

# ===================================================================
# ===== ELASTICSEARCH CONNECTION LOGIC =====
# ===================================================================
es_username = app.config.get('ELASTIC_USER')
es_password = app.config.get('ELASTIC_PASSWORD')
es_endpoint = app.config.get('ELASTIC_ENDPOINT_URL')

es_config = {
    'request_timeout': 30,
    'max_retries': 10,
    'retry_on_timeout': True
}

if es_endpoint and es_password and es_username:
    logger.info(f"Connecting to Elastic Cloud at {es_endpoint}...")
    try:
        es = Elasticsearch(
            [es_endpoint],
            basic_auth=(es_username, es_password),
            verify_certs=True,
            **es_config
        )
        if es.ping():
            logger.info("Connected to Elastic Cloud successfully!")
        else:
            logger.error("Failed to ping Elastic Cloud!")
            raise Exception("Failed to ping Elastic Cloud")
    except Exception as e:
        logger.critical(f"Error connecting to Elastic Cloud: {str(e)}")
        raise e
else:
    logger.info("Cloud credentials not found. Attempting to connect to Elasticsearch at localhost:9200...")
    es_url = app.config.get('ELASTICSEARCH_URL')
    try:
        es = Elasticsearch([es_url], **es_config)
        if es.ping():
            logger.info("Connected to localhost Elasticsearch successfully!")
        else:
            logger.error("Failed to connect to localhost Elasticsearch!")
            raise Exception("Failed to ping localhost Elasticsearch")
    except Exception as e:
        logger.critical(f"Error connecting to localhost Elasticsearch: {str(e)}")
        raise e
# ===================================================================

# Create and configure Celery
celery = Celery(
    app.name, 
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['RESULT_BACKEND']
)
celery.conf.update(app.config)

logger.info(f"Celery configured with broker at {app.config['CELERY_BROKER_URL']}")

@after_setup_logger.connect
def setup_celery_logging(logger, **kwargs):
    logging.basicConfig(level=logging.INFO)
    logger.info("Celery worker logging configured.")

if not app.config['PRODUCTION']:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    logger.info("OAuth insecure-transport enabled for local development.")

# Import routes and tasks AFTER app and celery are defined
from app import routes
from app import tasks