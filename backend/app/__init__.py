import os
# Only enable this for local development
if not os.environ.get('PRODUCTION', 'False').lower() == 'true':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for development!

from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Ensure secret key is set
if not app.secret_key:
    app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'

# Update CORS configuration to handle all methods and dynamic origins
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

# Initialize Elasticsearch with authentication if provided
es_url = app.config['ELASTICSEARCH_URL']
es_username = app.config.get('ELASTICSEARCH_USERNAME')
es_password = app.config.get('ELASTICSEARCH_PASSWORD')

es_config = {
    'timeout': 30,
    'max_retries': 10,
    'retry_on_timeout': True
}

# Add authentication if credentials are provided (for Bonsai)
if es_username and es_password:
    logger.info(f"Connecting to Elasticsearch with authentication at {es_url}")
    es_config['http_auth'] = (es_username, es_password)
else:
    logger.info(f"Connecting to Elasticsearch without authentication at {es_url}")

# Initialize Elasticsearch client
es = Elasticsearch([es_url], **es_config)

# Test Elasticsearch connection
try:
    if es.ping():
        logger.info("Connected to Elasticsearch successfully!")
    else:
        logger.error("Failed to connect to Elasticsearch!")
except Exception as e:
    logger.error(f"Error connecting to Elasticsearch: {str(e)}")

from app import routes