from elasticsearch import Elasticsearch
import json
from datetime import datetime

es = Elasticsearch(['http://localhost:9200'])

def create_index(index_name):
    """Create an index with the proper mapping."""
    mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0
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

    # Delete index if it exists
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    
    # Create new index
    es.indices.create(index=index_name, body=mapping)
    print(f"Created index: {index_name}")

def index_video(index_name, video_data, transcript):
    """Index a video and its transcript."""
    try:
        # Format transcript segments if available
        formatted_transcript = []
        if transcript:
            for segment in transcript:
                formatted_transcript.append({
                    "text": segment.get("text", ""),
                    "start": float(segment.get("start", 0)),
                    "duration": float(segment.get("duration", 0))
                })

        # Prepare document
        document = {
            "video_id": video_data["id"],
            "title": video_data["title"],
            "description": video_data.get("description", ""),
            "channel": video_data["channelTitle"],
            "published_at": video_data["publishedAt"],
            "view_count": int(video_data["viewCount"]),
            "thumbnail": video_data["thumbnail"],
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
    """Search for videos in the index."""
    try:
        if not search_in:
            search_in = ['title', 'description', 'transcript']

        # Handle phrase queries
        is_phrase = False
        if query.startswith('"') and query.endswith('"'):
            is_phrase = True
            query = query[1:-1]

        should_clauses = []

        # Add search clauses for each field
        if 'title' in search_in:
            should_clauses.append({
                "match_phrase" if is_phrase else "match": {
                    "title": {
                        "query": query,
                        "boost": 3
                    }
                }
            })

        if 'description' in search_in:
            should_clauses.append({
                "match_phrase" if is_phrase else "match": {
                    "description": {
                        "query": query,
                        "boost": 2
                    }
                }
            })

        if 'transcript' in search_in:
            should_clauses.append({
                "nested": {
                    "path": "transcript_segments",
                    "query": {
                        "match_phrase" if is_phrase else "match": {
                            "transcript_segments.text": {
                                "query": query,
                                "boost": 1
                            }
                        }
                    },
                    "inner_hits": {
                        "size": 10,
                        "highlight": {
                            "pre_tags": ["<em>"],
                            "post_tags": ["</em>"],
                            "fields": {
                                "transcript_segments.text": {
                                    "number_of_fragments": 1,
                                    "fragment_size": 200
                                }
                            }
                        }
                    }
                }
            })

        # Create the main query
        bool_query = {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1
            }
        }

        # Add channel filter if specified
        if channel_filter:
            if isinstance(channel_filter, list):
                bool_query["bool"]["filter"] = {
                    "terms": {
                        "channel": channel_filter
                    }
                }
            else:
                bool_query["bool"]["filter"] = {
                    "term": {
                        "channel": channel_filter
                    }
                }

        # Add aggregation to get channels in search results
        aggs = {
            "channels_in_results": {
                "terms": {
                    "field": "channel",
                    "size": 100  # Get up to 100 channels
                }
            }
        }

        search_query = {
            "query": bool_query,
            "highlight": {
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "fields": {
                    "title": {
                        "number_of_fragments": 0
                    },
                    "description": {
                        "number_of_fragments": 2,
                        "fragment_size": 150
                    }
                }
            },
            "aggs": aggs,
            "size": size,
            "from": from_pos
        }

        print("Executing search query:", json.dumps(search_query, indent=2))

        # Execute search
        raw_response = es.search(index=index_name, body=search_query)
        
        # Convert response to dictionary
        if hasattr(raw_response, 'body'):
            response = raw_response.body
        else:
            response = dict(raw_response)

        print("Raw response type:", type(response))
        print("Raw response:", json.dumps(response, indent=2))

        results = []
        hits = response.get('hits', {})
        total_hits = hits.get('total', {})
        total_count = total_hits.get('value', 0) if isinstance(total_hits, dict) else total_hits
        hits = hits.get('hits', [])

        # Extract channels from aggregation
        channels_in_results = []
        if 'aggregations' in response and 'channels_in_results' in response['aggregations']:
            channels_buckets = response['aggregations']['channels_in_results']['buckets']
            channels_in_results = [
                {
                    'name': bucket['key'],
                    'count': bucket['doc_count']
                } for bucket in channels_buckets
            ]

        for hit in hits:
            source = hit.get('_source', {})
            highlights = hit.get('highlight', {})
            
            # Process transcript matches
            matching_segments = []
            inner_hits = hit.get('inner_hits', {}).get('transcript_segments', {}).get('hits', {}).get('hits', [])
            
            for inner_hit in inner_hits:
                inner_source = inner_hit.get('_source', {})
                inner_highlight = inner_hit.get('highlight', {})
                
                if 'transcript_segments.text' in inner_highlight:
                    matching_segments.append({
                        'text': inner_source.get('text', ''),
                        'highlighted_text': inner_highlight['transcript_segments.text'][0],
                        'start': inner_source.get('start', 0)
                    })

            result = {
                'id': source.get('video_id'),
                'title': source.get('title'),
                'description': source.get('description'),
                'channel_title': source.get('channel'),
                'published_at': source.get('published_at'),
                'view_count': source.get('view_count'),
                'thumbnail': source.get('thumbnail'),
                'matching_segments': matching_segments,
                'highlighted_title': highlights.get('title', [source.get('title')])[0] if highlights.get('title') else source.get('title'),
                'highlighted_description': highlights.get('description', [''])[0] if highlights.get('description') else ''
            }
            results.append(result)

        return {
            'total': total_count,
            'results': results,
            'channels': channels_in_results
        }

    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'results': [],
            'channels': []
        }

def export_playlist_data(index_name, max_size=10000):
    """Export all data from a playlist index as JSON."""
    try:
        # Check if index exists
        if not es.indices.exists(index=index_name):
            return {"error": f"Index {index_name} does not exist"}, False

        # Query to get all documents in the index
        query = {
            "query": {
                "match_all": {}
            },
            "size": max_size  # Set a reasonable limit
        }

        # Execute the search
        response = es.search(index=index_name, body=query)
        
        # Extract hits
        hits = response.get('hits', {}).get('hits', [])
        
        # Format the data
        playlist_data = []
        for hit in hits:
            source = hit.get('_source', {})
            playlist_data.append(source)
        
        # Get metadata about the playlist if the metadata index exists
        metadata = {}
        if es.indices.exists(index="playlists_metadata"):
            try:
                metadata_query = {
                    "query": {
                        "term": {
                            "index_name.keyword": index_name
                        }
                    }
                }
                
                metadata_response = es.search(index="playlists_metadata", body=metadata_query)
                metadata_hits = metadata_response.get('hits', {}).get('hits', [])
                
                if metadata_hits:
                    metadata = metadata_hits[0].get('_source', {})
            except Exception as e:
                print(f"Error retrieving metadata (continuing without it): {e}")
        
        # Combine metadata and video data
        export_data = {
            "metadata": metadata,
            "videos": playlist_data,
            "exported_at": datetime.now().isoformat(),
            "total_videos": len(playlist_data)
        }
        
        return export_data, True
        
    except Exception as e:
        print(f"Error exporting playlist data: {e}")
        return {"error": str(e)}, False

def get_channels_for_playlist(index_name):
    """Get all unique channels in a playlist."""
    try:
        agg_query = {
            "size": 0,
            "aggs": {
                "unique_channels": {
                    "terms": {
                        "field": "channel",
                        "size": 1000  # Get up to 1000 unique channels
                    }
                }
            }
        }
        
        response = es.search(index=index_name, body=agg_query)
        
        # Extract channel buckets
        if hasattr(response, 'body'):
            response = response.body
        else:
            response = dict(response)
            
        buckets = response.get('aggregations', {}).get('unique_channels', {}).get('buckets', [])
        channels = [bucket.get('key') for bucket in buckets]
        
        return channels
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
        
        es.index(
            index="yts_metadata",
            id=playlist_data["id"],
            body=metadata,
            refresh=True
        )
        print(f"Saved metadata for playlist {playlist_data['id']}")
    except Exception as e:
        print(f"Error saving playlist metadata: {e}")

def get_indexed_playlists_metadata():
    """Get metadata for all indexed playlists."""
    try:
        result = es.search(
            index="yts_metadata",
            body={
                "size": 1000,
                "query": {"match_all": {}},
                "sort": [{"last_indexed": "desc"}]
            }
        )
        
        playlists = []
        for hit in result["hits"]["hits"]:
            playlists.append(hit["_source"])
        return playlists
    except Exception as e:
        print(f"Error getting indexed playlists metadata: {e}")
        return []