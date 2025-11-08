from flask import jsonify, request, session, redirect, url_for, send_file
from app import app, es, logger, celery, redis_conn
from app.auth import get_auth_url, get_credentials, SCOPES, get_client_config
from app.youtube import get_user_playlists, build_youtube_client
from app.elastic import search_videos, create_metadata_index, get_indexed_playlists_metadata, get_channels_for_playlist, export_playlist_data
from app.tasks import index_playlist_task
from celery.result import AsyncResult, GroupResult
import os
from google_auth_oauthlib.flow import Flow
import json
from datetime import datetime
import tempfile
import traceback
from youtube_transcript_api import YouTubeTranscriptApi

# Define a key prefix for Redis
TASK_KEY_PREFIX = "yts_task:"

try:
    create_metadata_index()
except Exception as e:
    logger.error(f"Failed to create metadata index on startup: {e}")





@app.route('/health')
def health_check():
    """
    Health check endpoint to verify the service and its dependencies are up.
    """
    status = {
        "status": "ok",
        "service": "youtube-transcript-search-api",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "elasticsearch": False,
            "redis": False
        }
    }
    
    # Check Elasticsearch
    try:
        if es and es.ping():
            status["dependencies"]["elasticsearch"] = True
        else:
            status["status"] = "degraded"
    except Exception:
        status["status"] = "degraded"

    # Check Redis
    try:
        if redis_conn and redis_conn.ping():
            status["dependencies"]["redis"] = True
        else:
            status["status"] = "degraded"
    except Exception:
        status["status"] = "degraded"

    # Return 200 OK even if degraded, as the HTTP server itself is working.
    # Some load balancers prefer 503 if degraded, but for simple monitoring 200 is usually fine.
    return jsonify(status), 200

@app.route('/api/auth/login')
def login():
    auth_url = get_auth_url()
    return jsonify({"auth_url": auth_url})

@app.route('/api/auth/callback')
def callback():
    state = session.get('state') 
    if not state:
        return jsonify({"error": "No state in session"}), 400
    
    try:
        client_config = get_client_config()
        if not client_config:
            return jsonify({"error": "No client configuration available"}), 500
        
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
        
        frontend_url = app.config.get('FRONTEND_URL', '/')
        return redirect(frontend_url)
    except Exception as e:
        app.logger.error(f"Error in OAuth callback: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout')
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})

@app.route('/api/auth/status')
def auth_status():
    if get_credentials():
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})

@app.route('/api/playlists')
def playlists():
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    playlists = get_user_playlists()
    
    logger.info(f"Found {len(playlists)} playlists: {len([p for p in playlists if p.get('isOwn', False)])} owned, {len([p for p in playlists if not p.get('isOwn', False)])} saved")
    
    return jsonify({"playlists": playlists})

@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get the current indexing status from Redis."""
    playlist_id = request.args.get('playlist_id')
    if not playlist_id:
        return jsonify({"error": "Missing playlist_id parameter"}), 400
    
    # Check for Redis connection
    if redis_conn is None:
        logger.error("Redis is not connected. Cannot check task status.")
        return jsonify({"status": "failed", "error": "Task server is disconnected"}), 503

    # Check Redis for a task ID
    task_id_key = f"{TASK_KEY_PREFIX}{playlist_id}"
    task_id = redis_conn.get(task_id_key)
    
    if not task_id:
        # Key not found, so it's not started (or it's finished and been cleaned up)
        return jsonify({ "status": "not_started", "progress": 0, "total": 0 })
    
    # Ask Celery for the task's result
    result = AsyncResult(task_id, app=celery)
    
    if result.state == 'PENDING':
        # Task is waiting in the queue
        return jsonify({
            "status": "in_progress", # Tell frontend it's "in_progress"
            "progress": 0,
            "total": 0,
            "id": playlist_id
        })
    elif result.state == 'PROGRESS':
        # Task is actively running
        return jsonify(result.info)
    elif result.state == 'SUCCESS':
        # Task is done, clean up the Redis key
        redis_conn.delete(task_id_key)
        return jsonify(result.info) # Return the final status
    elif result.state == 'FAILURE':
        # Task failed, clean up the Redis key
        redis_conn.delete(task_id_key)
        return jsonify(result.info) # Return the failure status
    
    # Fallback for other states (REVOKED, RETRY, etc.)
    return jsonify({ "status": "not_started", "progress": 0, "total": 0 })

@app.route('/api/playlist/<playlist_id>/index', methods=['POST'])
def index_playlist(playlist_id):
    """Start indexing a playlist."""
    credentials = get_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Check for Redis connection
    if redis_conn is None:
        logger.error("Redis is not connected. Cannot start new task.")
        return jsonify({"error": "Task server is disconnected"}), 503
    
    # Check if a task is already running
    task_id_key = f"{TASK_KEY_PREFIX}{playlist_id}"
    existing_task_id = redis_conn.get(task_id_key)
    
    if existing_task_id:
        result = AsyncResult(existing_task_id, app=celery)
        if result.state in ['PENDING', 'PROGRESS']:
             return jsonify({"error": "Playlist is already being indexed"}), 409
        else:
            # Task finished or failed, safe to overwrite
            logger.info(f"Overwriting stale task key for {playlist_id}")
            pass
    
    try:
        data = request.get_json()
        incremental = data.get('incremental', False)
        playlist_title = data.get('title', playlist_id)
        
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'scopes': credentials.scopes
        }
        
        # Start the task
        task = index_playlist_task.delay(
            playlist_id, 
            playlist_title, 
            credentials_dict, 
            incremental
        )
        
        # Store the task ID in Redis with a 2-hour expiration
        redis_conn.set(task_id_key, task.id, ex=7200) 
        
        return jsonify({
            "success": True, 
            "message": "Indexing added to queue"
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error starting indexing: {error_message}")
        traceback.print_exc()
        return jsonify({"error": error_message}), 500

@app.route('/api/playlist/<playlist_id>/cancel-index', methods=['POST'])
def cancel_indexing(playlist_id):
    """Cancel a running indexing task."""
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    if redis_conn is None:
        return jsonify({"error": "Task server is disconnected"}), 503

    task_id_key = f"{TASK_KEY_PREFIX}{playlist_id}"
    task_id = redis_conn.get(task_id_key)
    
    if not task_id:
        return jsonify({"error": "No running task found for this playlist"}), 404
        
    try:
        # Get the task result object
        result = AsyncResult(task_id, app=celery)
        
        if result.state not in ['PENDING', 'PROGRESS']:
            return jsonify({"error": "Task is not in a cancellable state"}), 400

        # Find the group_id from the task's metadata
        group_id = None
        if result.info and isinstance(result.info, dict):
            group_id = result.info.get("group_id")

        # 1. Revoke the main "manager" task
        logger.info(f"Revoking main task: {task_id}")
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')
        
        # 2. Revoke all the "child" tasks in the group
        if group_id:
            logger.info(f"Revoking task group: {group_id}")
            group_result = GroupResult.restore(group_id, app=celery)
            if group_result:
                group_result.revoke(terminate=True, signal='SIGTERM')
            
        # 3. Clean up the Redis key so a new task can be started
        redis_conn.delete(task_id_key)
        
        logger.info(f"Indexing cancelled for playlist {playlist_id}")
        
        return jsonify({"success": True, "message": "Indexing task cancelled"})

    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist/<playlist_id>/search')
def search_playlist(playlist_id):
    try:
        if not get_credentials():
            return jsonify({"error": "Not authenticated"}), 401
        
        if es is None:
            return jsonify({'total': 0, 'results': [], 'error': 'Search service is temporarily unavailable.'}), 503

        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        search_in = request.args.getlist('search_in')
        channels = request.args.getlist('channel')
        
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Playlist not indexed yet"}), 404
        
        from_pos = (page - 1) * size
        channel_filter = channels if channels else None
        results = search_videos(index_name, query, size, from_pos, search_in, channel_filter)
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        traceback.print_exc()
        return jsonify({'total': 0, 'results': [], 'error': str(e)}), 500

@app.route('/api/playlist/<playlist_id>/channels')
def get_playlist_channels(playlist_id):
    try:
        if not get_credentials():
            return jsonify({"error": "Not authenticated"}), 401
        
        if es is None:
            return jsonify({"error": "Search service is temporarily unavailable."}), 503

        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Playlist not indexed yet"}), 404
        
        channels = get_channels_for_playlist(index_name)
        return jsonify({"channels": channels})
        
    except Exception as e:
        logger.error(f"Error getting channels: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist/<playlist_id>/delete-index', methods=['DELETE'])
def delete_playlist_index(playlist_id):
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    if es is None:
        return jsonify({"error": "Search service is temporarily unavailable."}), 503

    try:
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Playlist not indexed"}), 404
        
        es.indices.delete(index=index_name)
        
        es.delete(
            index="yts_metadata",
            id=playlist_id,
            refresh=True,
            ignore=[404]
        )
        
        # Also remove from task tracking in case it's stuck
        if redis_conn:
            redis_conn.delete(f"{TASK_KEY_PREFIX}{playlist_id}")
        
        return jsonify({
            "success": True,
            "message": "Index and metadata deleted successfully"
        })
    except Exception as e:
        logger.error(f"Error deleting index: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/indexed-playlists')
def get_indexed_playlists():
    try:
        if es is None:
            return jsonify({"indexed_playlists": [], "error": "Search service is temporarily unavailable."}), 503
            
        indexed_playlists = get_indexed_playlists_metadata()
        return jsonify({"indexed_playlists": indexed_playlists})
    except Exception as e:
        logger.error(f"Error getting indexed playlists: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist/<playlist_id>/export', methods=['GET'])
def export_playlist(playlist_id):
    try:
        if 'credentials' not in session:
            return jsonify({"error": "Not authenticated"}), 401
            
        if es is None:
            return jsonify({"error": "Search service is temporarily unavailable."}), 503
            
        index_name = f"playlist_{playlist_id.lower()}"
        
        data, success = export_playlist_data(index_name)
        if not success:
            return jsonify(data), 404
            
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json', encoding='utf-8') as temp_file:
            json.dump(data, temp_file, indent=2)
            temp_path = temp_file.name
            
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=f"playlist_{playlist_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mimetype='application/json'
        )
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in export_playlist endpoint: {error_message}")
        traceback.print_exc()
        return jsonify({"error": error_message}), 500
    finally:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/debug/index/<index_name>')
def debug_index(index_name):
    try:
        if es is None:
            return jsonify({"error": "Search service is temporarily unavailable."}), 503
            
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Index does not exist"}), 404

        mapping = es.indices.get_mapping(index=index_name)
        
        sample = es.search(
            index=index_name,
            body={ "size": 1, "query": {"match_all": {}} }
        )

        return jsonify({
            "exists": True,
            "mapping": mapping,
            "doc_count": es.count(index=index_name)['count'],
            "sample_doc": sample['hits']['hits'][0] if sample['hits']['hits'] else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/transcript/<video_id>')
def debug_transcript(video_id):
    try:
        # --- NEW 1.2.x USAGE ---
        ytt_api = YouTubeTranscriptApi()
        transcript_obj = ytt_api.fetch(video_id)
        # Convert the fancy object back to a standard list of dicts
        transcript = transcript_obj.to_raw_data()
        # -----------------------
        
        return jsonify({
            "success": True,
            "video_id": video_id,
            "segment_count": len(transcript),
            "first_segment": transcript[0] if transcript else None,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }), 400