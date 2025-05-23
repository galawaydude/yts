from app import app, es as elasticsearch_client # Import app for logger, and es client
from elasticsearch import ElasticsearchException # Import specific exception
import json
from datetime import datetime

# Use es client imported from app and logger from app
es = elasticsearch_client # Use the imported es client
logger = app.logger 

def create_index(index_name, recreate=False):
    """Create an index with the proper mapping if it doesn't exist or if recreate is True."""
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

    # Check if index exists
    index_exists = es.indices.exists(index=index_name)
    
    # Delete index if it exists and recreate is True
    if index_exists and recreate:
        es.indices.delete(index=index_name)
        es.indices.create(index=index_name, body=mapping)
        logger.info(f"Recreated index: {index_name}")
        return True, 0  # Return True for created, 0 for existing docs count
    
    # Create new index if it doesn't exist
    elif not index_exists:
        es.indices.create(index=index_name, body=mapping)
        logger.info(f"Created new index: {index_name}")
        return True, 0  # Return True for created, 0 for existing docs count
    
    # Index exists and we're not recreating it
    else:
        # Count existing documents
        count_query = {"query": {"match_all": {}}}
        count_result = es.count(index=index_name, body=count_query)
        existing_count = count_result.get('count', 0)
        logger.info(f"Using existing index: {index_name} with {existing_count} documents")
        return False, existing_count  # Return False for not created, count of existing docs

def get_indexed_video_ids(index_name):
    """Get a list of all video IDs already indexed."""
    try:
        # Check if index exists
        if not es.indices.exists(index=index_name):
            return []
            
        # Query to get all video IDs
        query = {
            "_source": ["video_id"],
            "query": {"match_all": {}},
            "size": 10000  # Set a reasonable limit
        }
        
        # Execute the search
        response = es.search(index=index_name, body=query)
        
        # Extract video IDs
        hits = response.get('hits', {}).get('hits', [])
        video_ids = [hit.get('_source', {}).get('video_id') for hit in hits if hit.get('_source', {}).get('video_id')]
        
        return video_ids
        
    except ElasticsearchException as e:
        logger.error(f"Error getting indexed video IDs for {index_name}: {e}")
        return []

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
        logger.info(f"Indexing video {video_data['id']} in index {index_name}")
        es.index(index=index_name, id=video_data["id"], body=document)
        es.indices.refresh(index=index_name) # Consider removing for bulk operations
        logger.info(f"Successfully indexed video {video_data['id']}")
        return True

    except ElasticsearchException as e:
        logger.error(f"Error indexing video {video_data['id']} in index {index_name}: {e}")
        return False

def search_videos(index_name, query, size=10, from_pos=0, search_in=None, channel_filter=None):
    """Search for videos in the index."""
    try:
        if not search_in:
            search_in = ['title', 'description', 'transcript']
            
        logger.info(f"Search request: index={index_name}, query='{query}', fields={search_in}, size={size}, from={from_pos}, channels={channel_filter}")
        
        # Check if this is a phrase query (enclosed in quotes)
        is_phrase_query = False
        if query.startswith('"') and query.endswith('"'):
            is_phrase_query = True
            query = query[1:-1]  # Remove the quotes
            logger.info(f"Detected phrase query: '{query}'")
        
        # Define which fields to search in
        fields_to_search = []
        if 'title' in search_in:
            fields_to_search.append("title^3")  # Boost title matches
        if 'description' in search_in:
            fields_to_search.append("description^2")  # Boost description matches
        if 'transcript' in search_in:
            fields_to_search.append("transcript_segments.text")
            
        logger.debug(f"Fields to search in Elasticsearch: {fields_to_search}")
        
        # Build the appropriate query based on whether it's a phrase query or not
        if is_phrase_query:
            # For phrase queries, use match_phrase
            should_clauses = []
            
            if 'title' in search_in:
                should_clauses.append({
                    "match_phrase": {
                        "title": {
                            "query": query,
                            "boost": 3
                        }
                    }
                })
                
            if 'description' in search_in:
                should_clauses.append({
                    "match_phrase": {
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
                            "match_phrase": {
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
                
            main_query = {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            }
        else:
            # For regular queries, use query_string with AND operator
            main_query = {
                "query_string": {
                    "query": query,
                    "fields": fields_to_search,
                    "default_operator": "AND"  # This ensures all terms must match
                }
            }
        
        # Add channel filter if specified
        if channel_filter:
            bool_query = {
                "bool": {
                    "must": [main_query]
                }
            }
            
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
                
            final_query = bool_query
        else:
            final_query = main_query

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
            "query": final_query,
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
                    },
                    "transcript_segments.text": {
                        "number_of_fragments": 3,
                        "fragment_size": 200
                    }
                }
            },
            "aggs": aggs,
            "size": size,
            "from": from_pos
        }

        logger.debug(f"Executing search query: {json.dumps(search_query, indent=2)}")

        # Execute search
        raw_response = es.search(index=index_name, body=search_query)
        
        # Convert response to dictionary
        if hasattr(raw_response, 'body'):
            response = raw_response.body
        else:
            response = dict(raw_response)
            
        logger.info(f"Search results: found {len(response.get('hits', {}).get('hits', []))} hits for query '{query}' in index {index_name}")
        
        # Extract hits
        hits = response.get('hits', {}).get('hits', [])
        total = response.get('hits', {}).get('total', {})
        if isinstance(total, dict):
            total_count = total.get('value', 0)
        else:
            total_count = total or 0
            
        # Extract channel aggregation
        channels = []
        if 'aggregations' in response and 'channels_in_results' in response['aggregations']:
            for bucket in response['aggregations']['channels_in_results']['buckets']:
                channels.append({
                    'name': bucket['key'],
                    'count': bucket['doc_count']
                })

        # Format results
        results = []
        for hit in hits:
            source = hit['_source']
            
            # Extract transcript matches if available
            transcript_matches = []
            if 'inner_hits' in hit and 'transcript_segments' in hit['inner_hits']:
                for inner_hit in hit['inner_hits']['transcript_segments']['hits']['hits']:
                    segment = inner_hit['_source']
                    highlighted_text = inner_hit.get('highlight', {}).get('transcript_segments.text', [None])[0]
                    transcript_matches.append({
                        'text': segment['text'],
                        'highlighted_text': highlighted_text or segment['text'],
                        'start': segment['start'],
                        'duration': segment['duration']
                    })
            
            # Get highlights
            highlights = hit.get('highlight', {})
            highlighted_title = highlights.get('title', [None])[0] if 'title' in highlights else None
            highlighted_description = highlights.get('description', []) if 'description' in highlights else []
            
            # If we have transcript matches from nested query
            if not transcript_matches and 'transcript_segments.text' in highlights:
                # This is for the query_string approach which doesn't use nested queries
                # We need to extract the transcript segments from the source
                for segment in source.get('transcript_segments', []):
                    for highlight in highlights.get('transcript_segments.text', []):
                        if segment['text'] in highlight or highlight in segment['text']:
                            transcript_matches.append({
                                'text': segment['text'],
                                'highlighted_text': highlight,
                                'start': segment['start'],
                                'duration': segment['duration']
                            })
                            break
            
            # Format the result
            result = {
                'id': source['video_id'],
                'title': source.get('title', ''),
                'highlighted_title': highlighted_title or source.get('title', ''),
                'description': source.get('description', ''),
                'highlighted_description': highlighted_description,
                'channel_title': source.get('channel', ''),
                'published_at': source.get('published_at', ''),
                'view_count': source.get('view_count', '0'),
                'thumbnail': source.get('thumbnail', ''),
                'matching_segments': transcript_matches
            }
            
            results.append(result)
            
        return {
            'results': results,
            'total': total_count,
            'channels': channels
        }
        
    except ElasticsearchException as e:
        import traceback
        logger.error(f"Error in search_videos for index {index_name}, query '{query}': {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'results': [],
            'total': 0,
            'channels': [],
            'error': str(e)
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
            except ElasticsearchException as e:
                logger.warning(f"Error retrieving metadata for index {index_name} (continuing without it): {e}")
        
        # Combine metadata and video data
        export_data = {
            "metadata": metadata,
            "videos": playlist_data,
            "exported_at": datetime.now().isoformat(),
            "total_videos": len(playlist_data)
        }
        
        return export_data, True
        
    except ElasticsearchException as e:
        logger.error(f"Error exporting playlist data for index {index_name}: {e}")
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
    except ElasticsearchException as e:
        logger.error(f"Error getting channels for playlist {index_name}: {e}")
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
        logger.info(f"Created metadata index: {metadata_index}")

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
        logger.info(f"Saved metadata for playlist {playlist_data['id']}")
    except ElasticsearchException as e:
        logger.error(f"Error saving playlist metadata for playlist {playlist_data['id']}: {e}")

def bulk_index_videos(index_name, video_actions):
    """
    Indexes multiple video documents in bulk.
    video_actions should be a list of dictionaries, conforming to ES bulk helper format.
    Example action:
    {
        "_op_type": "index",  # Or "create", "update", "delete"
        "_index": index_name,
        "_id": video_data["id"],
        "_source": document # The document body
    }
    """
    from elasticsearch.helpers import bulk
    successes = 0
    errors = []

    try:
        # Attempt to execute the bulk operation
        successes, errors = bulk(es, video_actions, index=index_name, raise_on_error=False, raise_on_exception=False)
        
        if errors:
            logger.error(f"Bulk indexing to {index_name} encountered errors. Successes: {successes}. Errors: {len(errors)}")
            for error_info in errors[:5]: # Log first 5 errors
                logger.error(f"Bulk error detail: {error_info}")
        else:
            logger.info(f"Bulk indexing to {index_name} completed. Successes: {successes}.")
            
        if successes > 0:
            es.indices.refresh(index=index_name)
            logger.info(f"Refreshed index {index_name} after bulk operation.")
            
    except ElasticsearchException as e:
        logger.error(f"ElasticsearchException during bulk indexing to {index_name}: {e}")
        # Depending on the exception, all actions might have failed.
        # The `bulk` helper with raise_on_error=False should catch individual doc errors.
        # This block would catch more general ES issues (e.g. connection).
        return 0, [str(e)] # Return 0 successes and the exception as an error
    except Exception as e:
        logger.error(f"Unexpected error during bulk indexing to {index_name}: {e}", exc_info=True)
        return 0, [str(e)]

    return successes, errors # errors here are specific document errors from the bulk helper

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
    except ElasticsearchException as e:
        logger.error(f"Error getting indexed playlists metadata: {e}")
        return []