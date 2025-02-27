from elasticsearch import Elasticsearch

# Connect to Elasticsearch
es = Elasticsearch(['http://localhost:9200'])

try:
    # Delete all indices that start with 'playlist_'
    es.indices.delete(index='playlist_*')
    print("✅ Successfully deleted all playlist indices")
except Exception as e:
    print(f"❌ Error deleting indices: {e}")