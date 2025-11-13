from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan  # <--- Added this import
import json
from datetime import datetime
import traceback

from app import es

def create_index(index_name, recreate=False):
    """Create an index with the proper mapping and increased limits."""
    mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "mapping": {
                    "nested_objects": {
                        "limit": 100000
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "video_id": {"type": "keyword"},
                "title": {"type": "text"},
                "description": {"type": "text"},
                "channel": {"type": "keyword"},
                "published_at": {"type": "date"},
                "view_count": {"type": "long"},
                "thumbnail": {"type": "keyword"},
                "transcript_full_text": {"type": "text"},
                "transcript_segments": {
                    "type": "nested",
                    "properties": {
                        "text": {"type": "text"},
                        "start": {"type": "float"},
                        "duration": {"type": "float"}
                    }
                }
            }
        }
    }

    # Check if index exists
    index_exists = es.indices.exists(index=index_name)
    
    # Delete index if it exists and recreate is True
    if index_exists and recreate:
        es.indices.delete(index=index_name)
        es.indices.create(index=index_name, body=mapping)
        print(f"Recreated index: {index_name}")
        return True, 0
    
    # Create new index if it doesn't exist
    elif not index_exists:
        es.indices.create(index=index_name, body=mapping)
        print(f"Created new index: {index_name}")
        return True, 0
    
    # Index exists and we're not recreating it
    else:
        # Update settings for existing index dynamically
        try:
            es.indices.put_settings(index=index_name, body={
                "index.mapping.nested_objects.limit": 100000
            })
            print(f"Updated settings for existing index: {index_name}")
        except Exception as e:
            print(f"Could not update settings: {e}")

        count_query = {"query": {"match_all": {}}}
        count_result = es.count(index=index_name, body=count_query)
        existing_count = count_result.get('count', 0)
        print(f"Using existing index: {index_name} with {existing_count} documents")
        return False, existing_count

def get_indexed_video_ids(index_name):
    """Get a list of all video IDs already indexed using the Scan API (safe for large datasets)."""
    try:
        # Check if index exists
        if not es.indices.exists(index=index_name):
            return []
            
        # Use the Scan helper to fetch ALL IDs efficiently
        # This handles millions of results without the "Result window too large" error
        scanner = scan(
            es,
            index=index_name,
            query={"query": {"match_all": {}}},
            _source=["video_id"],
            size=1000  # Fetch in batches of 1000
        )

        video_ids = []
        for hit in scanner:
            vid = hit.get('_source', {}).get('video_id')
            if vid:
                video_ids.append(vid)
        
        return video_ids
        
    except Exception as e:
        print(f"Error getting indexed video IDs: {e}")
        return []

def index_video(index_name, video_data, transcript):
    """Index a video and its transcript."""
    try:
        # Format transcript segments if available
        formatted_transcript = []
        all_text_parts = []
        
        if transcript:
            for segment in transcript:
                text = segment.get("text", "")
                formatted_transcript.append({
                    "text": text,
                    "start": float(segment.get("start", 0)),
                    "duration": float(segment.get("duration", 0))
                })
                all_text_parts.append(text)

        # Prepare document
        document = {
            "video_id": video_data["id"],
            "title": video_data["title"],
            "description": video_data.get("description", ""),
            "channel": video_data["channelTitle"],
            "published_at": video_data["publishedAt"],
            "view_count": int(video_data["viewCount"]),
            "thumbnail": video_data["thumbnail"],
            "transcript_full_text": " ".join(all_text_parts),
            "transcript_segments": formatted_transcript
        }

        # Index document
        print(f"Indexing video {video_data['id']}")
        es.index(index=index_name, id=video_data["id"], body=document)
        es.indices.refresh(index=index_name)
        print(f"Successfully indexed video {video_data['id']}")
        return True

    except Exception as e:
        print(f"Error indexing video {video_data['id']}: {e}")
        return False

def search_videos(index_name, query, size=10, from_pos=0, search_in=None, channel_filter=None):
    """Search for videos in the index with advanced boolean and phrase support."""
    try:
        if not search_in:
            search_in = ['title', 'description', 'transcript']
            
        print(f"Boolean search request: index={index_name}, query='{query}', fields={search_in}")
        
        query_config = {
            "query": query,
            "default_operator": "AND",
            "analyze_wildcard": True,
            "phrase_slop": 1,
            "lenient": True
        }

        main_should_clauses = []
        
        # --- 1. Root Level Fields ---
        top_level_fields = []
        if 'title' in search_in:
            top_level_fields.append("title^3")
        if 'description' in search_in:
            top_level_fields.append("description^2")
        if 'transcript' in search_in:
            top_level_fields.append("transcript_full_text")
            
        if top_level_fields:
            main_should_clauses.append({
                "query_string": {
                    **query_config,
                    "fields": top_level_fields
                }
            })
            
        # --- 2. Transcript Segments (Nested Level) ---
        if 'transcript' in search_in:
            main_should_clauses.append({
                "nested": {
                    "path": "transcript_segments",
                    "query": {
                        "query_string": {
                            **query_config,
                            "fields": ["transcript_segments.text"]
                        }
                    },
                    "inner_hits": {
                        "size": 100, 
                        "highlight": {
                            "fields": {
                                "transcript_segments.text": {
                                    "number_of_fragments": 0
                                }
                            },
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"]
                        }
                    }
                }
            })

        if not main_should_clauses:
            return {'results': [], 'total': 0, 'channels': [], 'error': 'No fields selected for search'}

        main_query = {
            "bool": {
                "should": main_should_clauses,
                "minimum_should_match": 1
            }
        }

        # --- 3. Apply Filters (Channels) ---
        if channel_filter:
            final_query = {
                "bool": {
                    "must": [main_query],
                    "filter": {
                        "terms": {"channel": channel_filter}
                    }
                }
            }
        else:
            final_query = main_query

        # --- 4. Aggregations & Search Body ---
        search_body = {
            "query": final_query,
            "highlight": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fields": {
                    "title": {"number_of_fragments": 0},
                    "description": {"number_of_fragments": 2, "fragment_size": 150}
                }
            },
            "aggs": {
                "channels_in_results": {
                    "terms": {"field": "channel", "size": 100}
                }
            },
            "size": size,
            "from": from_pos
        }

        # Execute search
        raw_response = es.search(index=index_name, body=search_body)
        
        # Handle ES 8.x object vs dict
        if hasattr(raw_response, 'body'):
            response = raw_response.body
        else:
            response = dict(raw_response)
            
        # --- 5. Process Results ---
        hits = response.get('hits', {}).get('hits', [])
        total_val = response.get('hits', {}).get('total', 0)
        total_count = total_val.get('value', 0) if isinstance(total_val, dict) else total_val

        channels = []
        if 'aggregations' in response and 'channels_in_results' in response['aggregations']:
             for bucket in response['aggregations']['channels_in_results']['buckets']:
                channels.append({'name': bucket['key'], 'count': bucket['doc_count']})

        formatted_results = []
        for hit in hits:
            source = hit['_source']
            highlights = hit.get('highlight', {})
            
            transcript_matches = []
            if 'inner_hits' in hit and 'transcript_segments' in hit['inner_hits']:
                for inner_hit in hit['inner_hits']['transcript_segments']['hits']['hits']:
                    seg_source = inner_hit['_source']
                    h_text = inner_hit.get('highlight', {}).get('transcript_segments.text', [seg_source['text']])[0]
                    transcript_matches.append({
                        'text': seg_source['text'],
                        'highlighted_text': h_text,
                        'start': seg_source['start'],
                        'duration': seg_source['duration']
                    })
            
            formatted_results.append({
                'id': source.get('video_id'),
                'title': source.get('title'),
                'highlighted_title': highlights.get('title', [source.get('title')])[0],
                'description': source.get('description'),
                'highlighted_description': highlights.get('description', []),
                'channel_title': source.get('channel'),
                'published_at': source.get('published_at'),
                'view_count': source.get('view_count', 0),
                'thumbnail': source.get('thumbnail'),
                'matching_segments': transcript_matches
            })

        return {'results': formatted_results, 'total': total_count, 'channels': channels}
        
    except Exception as e:
        print(f"Error in search_videos: {str(e)}")
        traceback.print_exc()
        return {'results': [], 'total': 0, 'channels': [], 'error': str(e)}

def export_playlist_data(index_name, max_size=10000):
    """Export all data from a playlist index as JSON."""
    try:
        if not es.indices.exists(index=index_name):
            return {"error": f"Index {index_name} does not exist"}, False

        query = {"query": {"match_all": {}}, "size": max_size}
        response = es.search(index=index_name, body=query)
        
        # Handle ES 8.x object vs dict
        if hasattr(response, 'body'):
            hits = response.body['hits']['hits']
        else:
            hits = response['hits']['hits']
            
        playlist_data = [hit.get('_source', {}) for hit in hits]
        
        metadata = {}
        if es.indices.exists(index="yts_metadata"):
             try:
                playlist_id_guess = index_name.replace("playlist_", "").upper()
                meta_doc = es.get(index="yts_metadata", id=playlist_id_guess, ignore=[404])
                if meta_doc.get('found'):
                    metadata = meta_doc['_source']
             except Exception as e:
                print(f"Error retrieving metadata: {e}")
        
        return {
            "metadata": metadata,
            "videos": playlist_data,
            "exported_at": datetime.now().isoformat(),
            "total_videos": len(playlist_data)
        }, True
    except Exception as e:
        print(f"Error exporting playlist data: {e}")
        return {"error": str(e)}, False

def get_channels_for_playlist(index_name):
    """Get all unique channels in a playlist."""
    try:
        agg_query = {
            "size": 0,
            "aggs": {"unique_channels": {"terms": {"field": "channel", "size": 1000}}}
        }
        response = es.search(index=index_name, body=agg_query)
        
        if hasattr(response, 'body'): response = response.body
        else: response = dict(response)
        
        buckets = response.get('aggregations', {}).get('unique_channels', {}).get('buckets', [])
        return [bucket.get('key') for bucket in buckets]
    except Exception as e:
        print(f"Error getting channels: {e}")
        return []

def create_metadata_index():
    """Create or update the metadata index."""
    metadata_index = "yts_metadata"
    if not es.indices.exists(index=metadata_index):
        mapping = {
            "mappings": {
                "properties": {
                    "playlist_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "thumbnail": {"type": "keyword"},
                    "video_count": {"type": "integer"},
                    "last_indexed": {"type": "date"},
                    "indexed_videos": {"type": "integer"}
                }
            }
        }
        es.indices.create(index=metadata_index, body=mapping)
        print(f"Created metadata index: {metadata_index}")

def save_playlist_metadata(playlist_data, indexed_count):
    """Save playlist metadata after indexing."""
    try:
        metadata = {
            "playlist_id": playlist_data["id"],
            "title": playlist_data["title"],
            "thumbnail": playlist_data.get("thumbnail", ""),
            "video_count": playlist_data["videoCount"],
            "last_indexed": datetime.utcnow().isoformat(),
            "indexed_videos": indexed_count
        }
        es.index(index="yts_metadata", id=playlist_data["id"], body=metadata, refresh=True)
        print(f"Saved metadata for playlist {playlist_data['id']}")
    except Exception as e:
        print(f"Error saving playlist metadata: {e}")

def get_indexed_playlists_metadata():
    """Get metadata for all indexed playlists."""
    try:
        result = es.search(
            index="yts_metadata",
            body={"size": 1000, "query": {"match_all": {}}, "sort": [{"last_indexed": "desc"}]}
        )
        # Handle ES 8.x object vs dict
        if hasattr(result, 'body'):
            hits = result.body['hits']['hits']
        else:
            hits = result['hits']['hits']
            
        return [hit["_source"] for hit in hits]
    except Exception as e:
        print(f"Error getting indexed playlists metadata: {e}")
        return []