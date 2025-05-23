from flask import jsonify, request, session, redirect, url_for, send_file
from flask import jsonify, request, session, redirect, url_for, send_file
from flask import jsonify, request, session, redirect, url_for, send_file
from app import app, es
from app.auth import get_auth_url, get_credentials, SCOPES, get_client_config
from app.youtube import get_user_playlists, get_playlist_videos, get_video_transcript, build_youtube_client
# Import bulk_index_videos, remove index_video if no longer needed elsewhere after this refactor
from app.elastic import create_index, bulk_index_videos, search_videos, create_metadata_index, save_playlist_metadata, get_indexed_playlists_metadata, get_channels_for_playlist, export_playlist_data, get_indexed_video_ids 
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
from elasticsearch import ElasticsearchException
import os
import threading
import json
from datetime import datetime
import tempfile

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secret.json")

# Global variables
indexing_status = {}
indexing_threads = {}
status_lock = threading.Lock() # Lock for indexing_status
threads_lock = threading.Lock() # Lock for indexing_threads

# Add this after app initialization
create_metadata_index() # This should ideally be called once at app startup if not already idempotent

# Logger instance
logger = app.logger

def index_playlist_task(playlist_id, credentials_dict, playlist_title_from_api, playlist_thumbnail_from_api, incremental=False):
    """Background task to index a playlist."""
    try:
        # Create credentials object from dictionary
        credentials = {
            'token': credentials_dict['token'],
            'refresh_token': credentials_dict.get('refresh_token'),
            'token_uri': credentials_dict['token_uri'],
            'client_id': credentials_dict['client_id'],
            'client_secret': credentials_dict['client_secret'],
            'scopes': credentials_dict['scopes']
        }
        
        # Get playlist videos using the credentials directly
        videos = get_playlist_videos(playlist_id, credentials)
        if not videos:
            logger.warning(f"No videos found in playlist {playlist_id}")
            raise Exception("No videos found in playlist") # Or a custom exception
            
        total_videos = len(videos)
        with status_lock:
            indexing_status[playlist_id]["total"] = total_videos
        
        # Create or get index
        index_name = f"playlist_{playlist_id.lower()}"
        
        # If incremental, don't recreate the index, otherwise create a new one
        index_created, existing_count = create_index(index_name, recreate=not incremental)
        
        # Get list of already indexed video IDs if doing incremental indexing
        already_indexed_ids = []
        if incremental:
            already_indexed_ids = get_indexed_video_ids(index_name)
            logger.info(f"Incremental indexing for {playlist_id}: Found {len(already_indexed_ids)} already indexed videos")
            
            # Update status with info about incremental indexing
            with status_lock:
                indexing_status[playlist_id]["incremental"] = True
                indexing_status[playlist_id]["already_indexed"] = len(already_indexed_ids)
        
        # Index each video
        success_count = 0
        new_videos_count = 0
        skipped_count = 0
        video_actions = [] # For bulk indexing
        
        for i, video_data in enumerate(videos):
            try:
                with status_lock:
                    current_status = indexing_status.get(playlist_id, {})
                    if current_status.get("cancelled"):
                        logger.info(f"Indexing cancelled for playlist {playlist_id} during video processing.")
                        raise Exception("Indexing cancelled") # Or a custom exception
                    # Update progress for frontend
                    current_status["progress"] = i + 1
                    indexing_status[playlist_id] = current_status

                # Skip if video is already indexed and we're doing incremental indexing
                if incremental and video_data['id'] in already_indexed_ids:
                    skipped_count += 1
                    with status_lock: # Update skipped count in status
                        current_status = indexing_status.get(playlist_id, {})
                        current_status["skipped"] = skipped_count
                        indexing_status[playlist_id] = current_status
                    continue
                
                transcript = get_video_transcript(video_data['id']) # This now returns [] on error and logs it
                
                # Prepare document for bulk indexing
                formatted_transcript = []
                if transcript:
                    for segment in transcript:
                        formatted_transcript.append({
                            "text": segment.get("text", ""),
                            "start": float(segment.get("start", 0)),
                            "duration": float(segment.get("duration", 0))
                        })
                
                document_body = {
                    "video_id": video_data["id"],
                    "title": video_data["title"],
                    "description": video_data.get("description", ""),
                    "channel": video_data["channelTitle"],
                    "published_at": video_data["publishedAt"],
                    "view_count": int(video_data["viewCount"]),
                    "thumbnail": video_data["thumbnail"],
                    "transcript_segments": formatted_transcript
                }
                
                action = {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": video_data["id"],
                    "_source": document_body
                }
                video_actions.append(action)
                new_videos_count += 1 # Count videos intended for new indexing/re-indexing
            
            except Exception as e: # Catching general exceptions during single video preparation
                logger.error(f"Error preparing video {video_data.get('id', 'unknown')} for playlist {playlist_id}: {e}")
                # Optionally, update status with this specific video error if needed
                continue # Continue to next video
        
        # Perform bulk indexing if there are actions
        if video_actions:
            logger.info(f"Attempting to bulk index {len(video_actions)} videos for playlist {playlist_id} to index {index_name}.")
            # bulk_index_videos returns (number_of_successes, list_of_errors)
            # Errors in list_of_errors are dicts if from ES bulk helper, or string if general exception from our function
            num_bulk_successes, bulk_errors = bulk_index_videos(index_name, video_actions)
            success_count += num_bulk_successes
            
            if bulk_errors:
                logger.error(f"Encountered {len(bulk_errors)} errors during bulk indexing for {playlist_id}.")
                # Adjust new_videos_count if some bulk actions failed.
                # new_videos_count was incremented for each action prepared.
                # success_count reflects actual successes from bulk operation.
                # So, if new_videos_count was based on preparation, and num_bulk_successes is lower,
                # the difference represents failures within the bulk operation for newly processed videos.
        
        with status_lock: # Update final new_videos count based on bulk successes
            current_status = indexing_status.get(playlist_id, {})
            current_status["new_videos"] = success_count # Reflects actual new videos indexed in this run
            indexing_status[playlist_id] = current_status

        # For incremental indexing, count already indexed videos as successes
        if incremental:
            total_success = success_count + len(already_indexed_ids)
            if success_count == 0 and len(already_indexed_ids) == 0:
                raise Exception("No videos could be indexed")
        else:
            total_success = success_count
            if success_count == 0:
                raise Exception("No videos could be indexed")
        
        # Save playlist metadata
        # Use the title and thumbnail fetched from the YouTube API directly for the playlist
        
        playlist_metadata_to_save = {
            "id": playlist_id,
            "title": playlist_title_from_api, # Use title passed from the route
            "videoCount": total_videos, # Total videos in the YouTube playlist
            "thumbnail": playlist_thumbnail_from_api # Use thumbnail passed from the route
        }
        # total_success here should be the sum of newly indexed and already_indexed (if incremental)
        save_playlist_metadata(playlist_metadata_to_save, total_success)
        
        # Mark as complete
        with status_lock:
            final_status = indexing_status.get(playlist_id, {})
            final_status["status"] = "completed"
            final_status["success_count"] = total_success # Total successfully in ES (new + existing)
            # "new_videos" (actually indexed in this run) is already updated above based on bulk_successes
            # "new_videos_count" for the summary log should be success_count from this run
            final_status["new_videos_count"] = success_count # Videos processed and indexed in this run
            indexing_status[playlist_id] = final_status
            
        logger.info(f"Playlist {playlist_id} indexing task completed. Total in ES: {total_success}, Newly indexed/re-indexed in this run: {success_count}, Videos skipped (already indexed): {skipped_count}.")
        
    except HttpError as e: # Errors fetching playlist videos, etc.
        error_message = f"YouTube API error during indexing task for {playlist_id}: {str(e)}"
        logger.error(error_message)
        with status_lock:
            indexing_status[playlist_id] = {"status": "failed", "error": error_message}
    except ElasticsearchException as e: # Errors from create_index, get_indexed_video_ids, or bulk_index_videos if it re-raises
        error_message = f"Elasticsearch error during indexing task for {playlist_id}: {str(e)}"
        logger.error(error_message)
        with status_lock:
            indexing_status[playlist_id] = {"status": "failed", "error": error_message}
    except Exception as e: # Catch-all for other unexpected errors within the task
        error_message = f"Unexpected error during indexing task for {playlist_id}: {str(e)}"
        logger.error(error_message, exc_info=True) # Log with stack trace
        with status_lock:
            indexing_status[playlist_id] = {"status": "failed", "error": error_message}
    finally:
        # Clean up thread reference
        with threads_lock:
            if playlist_id in indexing_threads:
                del indexing_threads[playlist_id]

@app.route('/api/auth/login')
def login():
    """Redirect to Google OAuth."""
    auth_url = get_auth_url()
    return jsonify({"auth_url": auth_url})

@app.route('/api/auth/callback')
def callback():
    """Handle OAuth callback."""
    state = session['state']
    
    try:
        # Get client config from auth module
        client_config = get_client_config()
        if not client_config:
            return jsonify({"error": "No client configuration available"}), 500
        
        # Use the redirect URI from config
        redirect_uri = app.config.get('OAUTH_REDIRECT_URI')
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            state=state,
            redirect_uri=redirect_uri
        )
        
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Redirect to the frontend URL from config
        return redirect(app.config.get('FRONTEND_URL'))
    except Exception as e:
        app.logger.error(f"Error in OAuth callback: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout')
def logout():
    """Log out by clearing session."""
    session.clear()
    return jsonify({"message": "Logged out successfully"})

@app.route('/api/auth/status')
def auth_status():
    """Check if user is authenticated."""
    if get_credentials():
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})

@app.route('/api/playlists')
def playlists():
    """Get user's playlists, including owned and saved playlists."""
    if not get_credentials():
        logger.warning("Playlists endpoint called without authentication.")
        return jsonify({"error": "Not authenticated"}), 401
    
    playlists = get_user_playlists() # This now logs errors internally
    
    # Log the number of playlists found
    logger.info(f"Found {len(playlists)} playlists: {len([p for p in playlists if p.get('isOwn', False)])} owned, {len([p for p in playlists if not p.get('isOwn', False)])} saved for current user.")
    
    return jsonify({"playlists": playlists})

@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get the current indexing status."""
    playlist_id = request.args.get('playlist_id')
    if not playlist_id:
        logger.warning("Indexing status request missing playlist_id.")
        return jsonify({"error": "Missing playlist_id parameter"}), 400
    
    # Get status
    with status_lock:
        status = indexing_status.get(playlist_id, {
            "status": "not_started",
            "progress": 0,
            "total": 0
        }).copy() # Use .copy() to avoid modifying shared dict outside lock if needed later
    
    # Check if thread is still alive
    with threads_lock:
        thread = indexing_threads.get(playlist_id)

    if thread and not thread.is_alive() and status.get("status") == "in_progress":
        logger.warning(f"Indexing thread for {playlist_id} found dead. Marking as failed.")
        status["status"] = "failed"
        status["error"] = "Indexing process died unexpectedly"
        # Persist this change to global status
        with status_lock:
            indexing_status[playlist_id] = status
    
    logger.debug(f"Indexing status for {playlist_id}: {status}")
    return jsonify(status)

@app.route('/api/playlist/<playlist_id>/index', methods=['POST'])
def index_playlist(playlist_id):
    """Start indexing a playlist."""
    credentials = get_credentials()
    if not credentials:
        logger.warning(f"Index playlist {playlist_id} called without authentication.")
        return jsonify({"error": "Not authenticated"}), 401
    
    with threads_lock:
        if playlist_id in indexing_threads and indexing_threads[playlist_id].is_alive():
            logger.info(f"Playlist {playlist_id} is already being indexed.")
            return jsonify({"error": "Playlist is already being indexed"}), 409
    
    try:
        # Check if this is an incremental reindex
        incremental = request.json.get('incremental', False) if request.is_json else False

        # Fetch playlist title and thumbnail from YouTube API
        youtube_client = build_youtube_client(credentials)
        api_playlist_title = f"Playlist: {playlist_id}" # Default title
        api_playlist_thumbnail = "" # Default thumbnail
        if youtube_client:
            try:
                pl_request = youtube_client.playlists().list(part="snippet", id=playlist_id)
                pl_response = pl_request.execute()
                if pl_response and pl_response.get("items"):
                    item_snippet = pl_response["items"][0].get("snippet", {})
                    api_playlist_title = item_snippet.get("title", api_playlist_title)
                    api_playlist_thumbnail = item_snippet.get("thumbnails", {}).get("default", {}).get("url", "")
                else:
                    logger.warning(f"Could not fetch title for playlist {playlist_id} from YouTube API. Using default.")
            except HttpError as e:
                logger.error(f"HttpError fetching playlist details for {playlist_id}: {e}. Using default title/thumbnail.")
            except Exception as e_gen:
                logger.error(f"Generic error fetching playlist details for {playlist_id}: {e_gen}. Using default title/thumbnail.")
        else:
            logger.warning(f"No YouTube client available to fetch playlist details for {playlist_id}. Using default title/thumbnail.")

        with status_lock:
            indexing_status[playlist_id] = {
                "status": "in_progress",
                "progress": 0,
                "total": 0,
                "incremental": incremental,
                "new_videos": 0, 
                "skipped": 0 
            }
        
        # Get credentials as dictionary (already available as 'credentials' object)
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Start indexing in background thread
        thread = threading.Thread(
            target=index_playlist_task,
            args=(playlist_id, credentials_dict, api_playlist_title, api_playlist_thumbnail, incremental)
        )
        with threads_lock:
            indexing_threads[playlist_id] = thread
        thread.start()
        
        logger.info(f"Started {'incremental' if incremental else 'full'} indexing for playlist {playlist_id}")
        return jsonify({
            "success": True, 
            "message": "Incremental indexing started" if incremental else "Full indexing started"
        })
        
    except Exception as e: # Generic exception for errors before thread starts
        error_message = str(e)
        logger.error(f"Error starting indexing for playlist {playlist_id}: {error_message}")
        with status_lock: # Clear status if thread didn't start
            if playlist_id in indexing_status: # Should exist from above
                 indexing_status[playlist_id] = {"status": "failed", "error": error_message}
        return jsonify({"error": error_message}), 500

@app.route('/api/playlist/<playlist_id>/search')
def search_playlist(playlist_id):
    """Search for videos in a playlist."""
    try:
        if not get_credentials():
            logger.warning(f"Search on playlist {playlist_id} called without authentication.")
            return jsonify({"error": "Not authenticated"}), 401
        
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        search_in = request.args.getlist('search_in')
        channels = request.args.getlist('channel')
        
        if not query:
            logger.warning(f"Search on playlist {playlist_id} called with empty query.")
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            logger.warning(f"Search on playlist {playlist_id}: index {index_name} does not exist.")
            return jsonify({"error": "Playlist not indexed yet"}), 404
        
        from_pos = (page - 1) * size
        
        # Use the channel filter if channels are specified
        channel_filter = channels if channels else None
        
        results = search_videos(index_name, query, size, from_pos, search_in, channel_filter) # This now logs errors
        
        return jsonify(results)
        
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error during search on playlist {playlist_id} with query '{query}': {e}")
        return jsonify({'total': 0, 'results': [], 'error': f"Search backend error: {str(e)}"}), 500
    except ValueError as e: # For int conversion errors
        logger.error(f"Invalid parameter type during search on playlist {playlist_id}: {e}")
        return jsonify({'error': f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Generic error during search on playlist {playlist_id} with query '{query}': {e}", exc_info=True)
        return jsonify({'total': 0, 'results': [], 'error': 'An unexpected error occurred during search.'}), 500

@app.route('/api/playlist/<playlist_id>/channels')
def get_playlist_channels(playlist_id):
    """Get all unique channels in a playlist."""
    try:
        if not get_credentials():
            logger.warning(f"Get channels for playlist {playlist_id} called without authentication.")
            return jsonify({"error": "Not authenticated"}), 401
        
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            logger.warning(f"Get channels for playlist {playlist_id}: index {index_name} does not exist.")
            return jsonify({"error": "Playlist not indexed yet"}), 404
        
        channels = get_channels_for_playlist(index_name) # This now logs errors
        
        return jsonify({
            "channels": channels
        })
        
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error getting channels for playlist {playlist_id}: {e}")
        return jsonify({"error": f"Backend error getting channels: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Generic error getting channels for playlist {playlist_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/api/playlist/<playlist_id>/delete-index', methods=['DELETE'])
def delete_playlist_index(playlist_id):
    """Delete the index for a playlist."""
    if not get_credentials():
        logger.warning(f"Delete index for playlist {playlist_id} called without authentication.")
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            logger.warning(f"Delete index for playlist {playlist_id}: index {index_name} does not exist.")
            return jsonify({"error": "Playlist not indexed"}), 404
        
        # Delete the index
        es.indices.delete(index=index_name)
        logger.info(f"Successfully deleted Elasticsearch index: {index_name}")
        
        # Delete the metadata
        es.delete(
            index="yts_metadata", # Make sure this index name is consistent
            id=playlist_id, # This should be the original playlist_id
            ignore=[404] # Ignore if metadata doc not found
        )
        logger.info(f"Successfully deleted metadata for playlist: {playlist_id}")
        
        return jsonify({
            "success": True,
            "message": "Index and metadata deleted successfully"
        })
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error deleting index/metadata for playlist {playlist_id}: {e}")
        return jsonify({"error": f"Backend error deleting index: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Generic error deleting index for playlist {playlist_id}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/api/indexed-playlists')
def get_indexed_playlists():
    """Get a list of all indexed playlists with metadata."""
    try:
        indexed_playlists = get_indexed_playlists_metadata() # This now logs errors
        
        # For each indexed playlist, check if it needs updating
        credentials = get_credentials() # Get credentials once
        youtube = build_youtube_client(credentials) if credentials else None

        if youtube: # Only proceed if we have a YouTube client
            for playlist_meta in indexed_playlists:
                try:
                    yt_request = youtube.playlists().list(
                        part="snippet,contentDetails",
                        id=playlist_meta['playlist_id']
                    )
                    response = yt_request.execute()
                    
                    if response['items']:
                        current_count = response['items'][0]['contentDetails']['itemCount']
                        # 'indexed_videos' is the field from save_playlist_metadata
                        indexed_count = playlist_meta.get('indexed_videos', 0) 
                        
                        playlist_meta['needs_update'] = current_count > indexed_count
                        playlist_meta['current_video_count'] = current_count
                        playlist_meta['behind_by'] = max(0, current_count - indexed_count)
                    else:
                        playlist_meta['needs_update'] = False # Could not fetch from YouTube
                        logger.warning(f"Could not fetch details for playlist {playlist_meta['playlist_id']} from YouTube.")

                except HttpError as e:
                    logger.error(f"YouTube API error checking update status for playlist {playlist_meta['playlist_id']}: {e}")
                    playlist_meta['needs_update'] = False # Error, assume no update needed or info unavailable
                except Exception as e:
                    logger.error(f"Unexpected error checking update status for playlist {playlist_meta['playlist_id']}: {e}", exc_info=True)
                    playlist_meta['needs_update'] = False
        else:
            logger.warning("Cannot check playlist update status without authentication/YouTube client.")
            # Optionally mark all as not updatable or skip this enrichment
            for playlist_meta in indexed_playlists:
                playlist_meta['needs_update'] = False # Or some other indicator
                
        return jsonify({"indexed_playlists": indexed_playlists})
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error getting indexed playlists: {e}")
        return jsonify({"error": f"Backend error retrieving playlists: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Generic error getting indexed playlists: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/api/playlist/<playlist_id>/export', methods=['GET'])
def export_playlist(playlist_id):
    """Export the indexed playlist data as a downloadable JSON file."""
    try:
        # Check if user is authenticated
        if 'credentials' not in session:
            logger.warning(f"Export playlist {playlist_id} called without authentication.")
            return jsonify({"error": "Not authenticated"}), 401
            
        # Format index name
        index_name = f"playlist_{playlist_id.lower()}"
        
        # Get playlist data
        data, success = export_playlist_data(index_name) # This now logs errors
        if not success:
            # export_playlist_data now returns dict with "error" key
            return jsonify(data), 404 
            
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json', encoding='utf-8') as temp_file:
            json.dump(data, temp_file, indent=2)
            temp_path = temp_file.name
            
        # Send the file as an attachment
        # Ensure the temp file is closed before sending, send_file might need exclusive access or handle this.
        # tempfile.NamedTemporaryFile(delete=False) means we need to manually delete it after sending.
        # A better approach might be to use io.BytesIO if data is not excessively large or use a try/finally to delete.
        
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=f"playlist_{playlist_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mimetype='application/json'
        )
        # Clean up the temporary file after sending
        # This might be better handled by a background task or ensuring the OS cleans temp dirs.
        # For now, simple deletion. If send_file is asynchronous, this could be problematic.
        # However, send_file in Flask typically completes before returning the response object for WSGI.
        # os.remove(temp_path) # This can be added if sure about file handle closure.
        return response
        
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error exporting playlist {playlist_id}: {e}")
        return jsonify({"error": f"Backend error exporting data: {str(e)}"}), 500
    except Exception as e:
        error_message = str(e)
        logger.error(f"Generic error in export_playlist endpoint for {playlist_id}: {error_message}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {error_message}"}), 500
    finally:
        # Ensure temp_path is defined and try to clean up if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Successfully deleted temporary export file: {temp_path}")
            except OSError as e:
                logger.error(f"Error deleting temporary export file {temp_path}: {e}")


@app.route('/api/debug/index/<index_name>')
def debug_index(index_name):
    """Debug endpoint to check index contents."""
    # This endpoint should be protected or disabled in production
    if app.config.get("PRODUCTION", False):
        logger.warning(f"Debug endpoint /api/debug/index/{index_name} accessed in production. Denying.")
        return jsonify({"error": "Debug endpoint not available in production"}), 403
        
    try:
        # Check if index exists
        if not es.indices.exists(index=index_name):
            logger.info(f"Debug: Index {index_name} does not exist.")
            return jsonify({"error": "Index does not exist"}), 404

        # Get index mapping
        mapping = es.indices.get_mapping(index=index_name)
        
        # Get a sample of documents
        sample_doc_body = {"size": 1, "query": {"match_all": {}}}
        sample = es.search(index=index_name, body=sample_doc_body)
        doc_count = es.count(index=index_name)['count']
        
        logger.debug(f"Debug info for index {index_name}: mapping={mapping}, count={doc_count}, sample={sample}")
        return jsonify({
            "exists": True,
            "mapping": mapping,
            "doc_count": doc_count,
            "sample_doc": sample['hits']['hits'][0] if sample['hits']['hits'] else None
        })

    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error in debug_index for {index_name}: {e}")
        return jsonify({"error": f"Elasticsearch error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Generic error in debug_index for {index_name}: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    # This will only run if the script is executed directly, not with Flask CLI or Gunicorn
    logger.info("Starting Flask development server directly from run.py (likely for local testing)")
    app.run(debug=True, host='0.0.0.0', port=app.config.get('PORT', 5000))