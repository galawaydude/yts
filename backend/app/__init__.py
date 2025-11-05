import os
import logging
from dotenv import load_dotenv # <-- IMPORT THIS

# --- THIS IS THE FIX ---
# Load environment variables at the absolute top.
# This ensures both Flask and Celery read the .env file.
load_dotenv()
# ---------------------

# import eventlet
# eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config
from celery import Celery
from celery.signals import after_setup_logger

# Configure logging (this is now done in run.py, so we just get the logger)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

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
es_endpoint = app.config.get('ELASTIC_ENDPOINT_URL') # Using the new Endpoint URL

es_config = {
    'request_timeout': 30, # Renamed from 'timeout'
    'max_retries': 10,
    'retry_on_timeout': True
}

# Check if cloud credentials are provided in the environment
# This will now work for Celery because we ran load_dotenv()
if es_endpoint and es_password and es_username:
    logger.info(f"Connecting to Elastic Cloud at {es_endpoint}...")
    try:
        # New connection method (from your test script)
        es = Elasticsearch(
            [es_endpoint],
            basic_auth=(es_username, es_password),
            verify_certs=True, # Enforce SSL verification
            **es_config
        )
        if es.ping():
            logger.info("Connected to Elastic Cloud successfully!")
        else:
            logger.error("Failed to ping Elastic Cloud!")
    except Exception as e:
        logger.critical(f"Error connecting to Elastic Cloud: {str(e)}")
        es = None # Set es to None to indicate failure
else:
    # Fallback to old localhost method (for local dev)
    logger.info("Cloud credentials not found. Attempting to connect to Elasticsearch at localhost:9200...")
    es_url = app.config.get('ELASTICSEARCH_URL') # Get old var as fallback
    try:
        es = Elasticsearch([es_url], **es_config) # This also uses the corrected es_config
        if es.ping():
            logger.info("Connected to localhost Elasticsearch successfully!")
        else:
            logger.error("Failed to connect to localhost Elasticsearch!")
    except Exception as e:
        logger.critical(f"Error connecting to localhost Elasticsearch: {str(e)}")
        es = None # Set es to None to indicate failure

# Final check to make sure 'es' is not None
if es is None:
    logger.critical("Elasticsearch client is NOT initialized. The app may not function.")
# ===================================================================
# ===================================================================


# Create and configure the Celery instance
celery = Celery(
    app.name, 
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['RESULT_BACKEND'] # Use the UPPERCASE config value
)
celery.conf.update(app.config)

# This log confirms Celery is configured
logger.info(f"Celery configured with broker at {app.config['CELERY_BROKER_URL']}")


# This configures logging for the Celery worker
@after_setup_logger.connect
def setup_celery_logging(logger, **kwargs):
    """Configure logging for Celery workers."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Celery worker logging configured.")

# Allow OAuth to run on HTTP (http://) for local development
if not app.config['PRODUCTION']:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    logger.info("OAuth insecure transport enabled for local development.")

# Import routes and tasks AFTER app and celery are defined
from app import routes
from app import tasks