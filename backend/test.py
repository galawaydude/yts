# test_es_endpoint.py
from elasticsearch import Elasticsearch

# -----------------------------
# Elastic cluster details
# -----------------------------
ENDPOINT_URL = "https://my-deployment-41e52f.es.asia-south1.gcp.elastic-cloud.com:9243"
USERNAME = "elastic"
PASSWORD = "rI9tw6RcaPxMwgbeS8XBwOxi"

# Optional: disable cert verification for testing (not recommended in prod)
# verify_certs=True is recommended in production with proper CA certs
es_config = {
    "request_timeout": 30,
    "max_retries": 5,
    "retry_on_timeout": True,
    "verify_certs": True
}

# -----------------------------
# Connect using direct endpoint + basic_auth
# -----------------------------
try:
    es = Elasticsearch(
        [ENDPOINT_URL],
        basic_auth=(USERNAME, PASSWORD),
        **es_config
    )

    info = es.info()
    print("✅ Connected successfully!")
    print("Cluster name:", info.get("cluster_name"))
    print("Cluster UUID:", info.get("cluster_uuid"))
    print("Elasticsearch version:", info.get("version", {}).get("number"))

except Exception as e:
    print("❌ Connection failed:", type(e), e)
