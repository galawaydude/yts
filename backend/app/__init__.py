import os
import logging
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config
from celery import Celery
from celery.signals import after_setup_logger
import redis
from flask_session import Session # <-- Make sure this import is here

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# ==========================================================
# ==================== THE STABLE FIX ======================
# ==========================================================

# 1. Create ONE Redis connection, correctly configured.
#    This will be used for BOTH Sessions and Celery.
try:
    redis_conn = redis.from_url(
        app.config['CELERY_BROKER_URL'],
        decode_responses=True # <-- THIS IS THE CRITICAL LINE
    )
    redis_conn.ping()
    logger.info(f"Connected to Redis for Sessions/Celery at {app.config['CELERY_BROKER_URL']}")
except Exception as e:
    logger.critical(f"Failed to connect to Redis: {e}")
    redis_conn = None
    # If Redis is down, we must stop the app
    raise e

# 2. Tell Flask-Session to use THIS connection
app.config['SESSION_REDIS'] = redis_conn

# 3. NOW initialize Flask-Session
Session(app)

# ==========================================================
# ================== END OF FIX ============================
# ==========================================================


# We NO LONGER need the old, redundant connection block.
# The `redis_conn` object is already created.

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
# ===== ELASTICSEARCH CONNECTION LOGIC (MODIFIED) =====
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
            # --- FIX: FAIL FAST ---
            raise Exception("Failed to ping Elastic Cloud")
            # --------------------
    except Exception as e:
        logger.critical(f"Error connecting to Elastic Cloud: {str(e)}")
        # --- FIX: FAIL FAST ---
        raise e # Re-raise exception to stop the app
        # --------------------
else:
    logger.info("Cloud credentials not found. Attempting to connect to Elasticsearch at localhost:9200...")
    es_url = app.config.get('ELASTICSEARCH_URL')
    try:
        es = Elasticsearch([es_url], **es_config)
        if es.ping():
            logger.info("Connected to localhost Elasticsearch successfully!")
        else:
            logger.error("Failed to connect to localhost Elasticsearch!")
            # --- FIX: FAIL FAST ---
            raise Exception("Failed to ping localhost Elasticsearch")
            # --------------------
    except Exception as e:
        logger.critical(f"Error connecting to localhost Elasticsearch: {str(e)}")
        # --- FIX: FAIL FAST ---
        raise e # Re-raise exception to stop the app
        # --------------------

# ===================================================================
# ===================================================================


# Create and configure the Celery instance
celery = Celery(
    app.name, 
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['RESULT_BACKEND']
)
celery.conf.update(app.config)

# The prefetch_multiplier line has been removed.

logger.info(f"Celery configured with broker at {app.config['CELERY_BROKER_URL']}")

@after_setup_logger.connect
def setup_celery_logging(logger, **kwargs):
    logging.basicConfig(level=logging.INFO)
    logger.info("Celery worker logging configured.")

if not app.config['PRODUCTION']:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    logger.info("OAuth insecure transport enabled for local development.")

# Import routes and tasks AFTER app and celery are defined
from app import routes
from app import tasks