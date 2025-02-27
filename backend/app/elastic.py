from elasticsearch import Elasticsearch
import json

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
        if not transcript:
            print(f"No transcript for video {video_data['id']}")
            return False

        # Format transcript segments
        formatted_transcript = []
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

def search_videos(index_name, query, size=10, from_pos=0, search_in=None):
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
                        "size": 3,
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

        search_query = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            },
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
        hits = response.get('hits', {}).get('hits', [])

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
                'title': source.get('title', ''),
                'highlighted_title': highlights.get('title', [source.get('title', '')])[0] if 'title' in highlights else source.get('title', ''),
                'description': source.get('description', ''),
                'highlighted_description': highlights.get('description', [None])[0] if 'description' in highlights else None,
                'thumbnail': source.get('thumbnail', ''),
                'channel_title': source.get('channel', ''),
                'published_at': source.get('published_at', ''),
                'view_count': source.get('view_count', 0),
                'matching_segments': matching_segments
            }
            results.append(result)

        return {
            'total': response.get('hits', {}).get('total', {}).get('value', 0),
            'results': results
        }

    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total': 0,
            'results': []
        } 