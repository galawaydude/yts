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
        "status": "ok, shit is fixed i guess",
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
        return jsonify({
            "status": "in_progress", 
            "progress": 0,
            "total": 0,
            "id": playlist_id
        })
    elif result.state == 'PROGRESS':
        return jsonify(result.info)
    elif result.state == 'SUCCESS':
        redis_conn.delete(task_id_key)
        return jsonify(result.info) 
    elif result.state == 'FAILURE':
        redis_conn.delete(task_id_key)
        return jsonify(result.info)
    
    return jsonify({ "status": "not_started", "progress": 0, "total": 0 })

@app.route('/api/playlist/<playlist_id>/index', methods=['POST'])
def index_playlist(playlist_id):
    """Start indexing a playlist."""
    credentials = get_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    if redis_conn is None:
        return jsonify({"error": "Task server is disconnected"}), 503
    
    data = request.get_json() or {}
    incremental = data.get('incremental', False)
    playlist_title = data.get('title', playlist_id)
    force_restart = data.get('force', False) 

    task_id_key = f"{TASK_KEY_PREFIX}{playlist_id}"
    existing_task_id = redis_conn.get(task_id_key)
    
    # Only block if we are NOT forcing a restart
    if existing_task_id and not force_restart:
        result = AsyncResult(existing_task_id, app=celery)
        if result.state in ['PENDING', 'PROGRESS']:
             return jsonify({"error": "Playlist is already being indexed"}), 409
    
    # If forcing, kill the old task first
    if existing_task_id and force_restart:
        logger.info(f"Force restarting indexing for {playlist_id}")
        celery.control.revoke(existing_task_id, terminate=True)
        redis_conn.delete(task_id_key)
    
    try:
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
        result = AsyncResult(task_id, app=celery)
        
        if result.state not in ['PENDING', 'PROGRESS']:
            return jsonify({"error": "Task is not in a cancellable state"}), 400

        group_id = None
        if result.info and isinstance(result.info, dict):
            group_id = result.info.get("group_id")

        logger.info(f"Revoking main task: {task_id}")
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')
        
        if group_id:
            logger.info(f"Revoking task group: {group_id}")
            group_result = GroupResult.restore(group_id, app=celery)
            if group_result:
                group_result.revoke(terminate=True, signal='SIGTERM')
            
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

        # Handle ES 8.x Object vs Dict
        mapping_resp = es.indices.get_mapping(index=index_name)
        mapping = mapping_resp.body if hasattr(mapping_resp, 'body') else dict(mapping_resp)
        
        sample_resp = es.search(
            index=index_name,
            body={ "size": 1, "query": {"match_all": {}} }
        )
        sample = sample_resp.body if hasattr(sample_resp, 'body') else dict(sample_resp)
        
        count_resp = es.count(index=index_name)
        doc_count = count_resp.get('count', 0)

        return jsonify({
            "exists": True,
            "mapping": mapping,
            "doc_count": doc_count,
            "sample_doc": sample.get('hits', {}).get('hits', [None])[0]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/transcript/<video_id>')
def debug_transcript(video_id):
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_obj = ytt_api.fetch(video_id)
        transcript = transcript_obj.to_raw_data()
        
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

@app.route('/api/debug/set-session')
def debug_set_session():
    try:
        session['test_key'] = 'it_works!'
        return jsonify({"status": "session data set", "session_id": session.sid if hasattr(session, 'sid') else "unknown"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/get-session')
def debug_get_session():
    try:
        val = session.get('test_key', 'NOT_FOUND')
        return jsonify({"status": "read attempt", "value": val, "session_data": dict(session)}), 200
    except Exception as e:
         return jsonify({"error": str(e)}), 500