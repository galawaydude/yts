import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for development!

from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Ensure secret key is set
if not app.secret_key:
    app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'

# Update CORS configuration to handle all methods
CORS(
    app, 
    supports_credentials=True, 
    origins=["http://localhost:3000"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)

# Initialize Elasticsearch with more configuration options
es = Elasticsearch(
    [app.config['ELASTICSEARCH_URL']], 
    timeout=30,
    max_retries=10,
    retry_on_timeout=True
)

from app import routes 