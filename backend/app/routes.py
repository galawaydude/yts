from flask import jsonify, request, session, redirect, url_for, send_file
from app import app, es, logger, celery # Import celery
from app.auth import get_auth_url, get_credentials, SCOPES, get_client_config
from app.youtube import get_user_playlists, build_youtube_client
from app.elastic import search_videos, create_metadata_index, get_indexed_playlists_metadata, get_channels_for_playlist, export_playlist_data
from app.tasks import index_playlist_task # Import our new task
from celery.result import AsyncResult # Import this to check task status
import os
from google_auth_oauthlib.flow import Flow
import json
from datetime import datetime
import tempfile
import traceback

# This global dict will now just store Task IDs
indexing_status = {}

# The index_playlist_task function is now REMOVED from this file
# The indexing_threads dictionary is REMOVED

try:
    create_metadata_index()
except Exception as e:
    logger.error(f"Failed to create metadata index on startup: {e}")

@app.route('/api/auth/login')
def login():
    # ... (no changes in this function)
    auth_url = get_auth_url()
    return jsonify({"auth_url": auth_url})

@app.route('/api/auth/callback')
def callback():
    # ... (no changes in this function)
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
    # ... (no changes in this function)
    session.clear()
    return jsonify({"message": "Logged out successfully"})

@app.route('/api/auth/status')
def auth_status():
    # ... (no changes in this function)
    if get_credentials():
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})

@app.route('/api/playlists')
def playlists():
    # ... (no changes in this function)
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    playlists = get_user_playlists()
    
    logger.info(f"Found {len(playlists)} playlists: {len([p for p in playlists if p.get('isOwn', False)])} owned, {len([p for p in playlists if not p.get('isOwn', False)])} saved")
    
    return jsonify({"playlists": playlists})

# NEW: This route is now re-written to use Celery
@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get the current indexing status from Celery."""
    playlist_id = request.args.get('playlist_id')
    if not playlist_id:
        return jsonify({"error": "Missing playlist_id parameter"}), 400
    
    # Check our local dict for a task ID
    status_info = indexing_status.get(playlist_id)
    if not status_info:
        return jsonify({ "status": "not_started", "progress": 0, "total": 0 })

    task_id = status_info['task_id']
    
    # Ask Celery for the task's result
    result = AsyncResult(task_id, app=celery)
    
    if result.state == 'PENDING':
        # The task is waiting in the queue
        return jsonify({
            "status": "in_progress", # Tell frontend it's "in_progress"
            "progress": 0,
            "total": 0,
            "title": status_info.get('title', playlist_id),
            "id": playlist_id
        })
    elif result.state == 'PROGRESS':
        # The task is actively running and sending progress
        return jsonify(result.info) # result.info is the 'meta' dict from our task
    elif result.state == 'SUCCESS':
        # The task is done
        # We can remove it from our local dict now
        if playlist_id in indexing_status:
            del indexing_status[playlist_id]
        return jsonify(result.info) # result.info is the final 'meta' dict
    elif result.state == 'FAILURE':
        # The task failed
        if playlist_id in indexing_status:
            del indexing_status[playlist_id]
        return jsonify(result.info) # result.info is the 'meta' dict with the error
    
    # Fallback for other states (REVOKED, RETRY, etc.)
    return jsonify({ "status": "not_started", "progress": 0, "total": 0 })


# NEW: This route is now re-written to use Celery
@app.route('/api/playlist/<playlist_id>/index', methods=['POST'])
def index_playlist(playlist_id):
    """Start indexing a playlist."""
    credentials = get_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Check if a task is already running or pending for this playlist
    if playlist_id in indexing_status:
        task_id = indexing_status[playlist_id]['task_id']
        result = AsyncResult(task_id, app=celery)
        if result.state in ['PENDING', 'PROGRESS']:
             return jsonify({"error": "Playlist is already being indexed"}), 409
        else:
            # Task finished or failed, safe to remove
            del indexing_status[playlist_id]
    
    try:
        data = request.get_json()
        incremental = data.get('incremental', False)
        playlist_title = data.get('title', playlist_id)
        
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # This is the change:
        # Instead of starting a thread, we call .delay() on our task
        task = index_playlist_task.delay(
            playlist_id, 
            playlist_title, 
            credentials_dict, 
            incremental
        )
        
        # Store the task ID so we can check its status later
        indexing_status[playlist_id] = {"task_id": task.id, "title": playlist_title, "id": playlist_id}
        
        return jsonify({
            "success": True, 
            "message": "Indexing added to queue"
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error starting indexing: {error_message}")
        traceback.print_exc()
        return jsonify({"error": error_message}), 500

@app.route('/api/playlist/<playlist_id>/search')
def search_playlist(playlist_id):
    # ... (no changes in this function)
    try:
        if not get_credentials():
            return jsonify({"error": "Not authenticated"}), 401
        
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
    # ... (no changes in this function)
    try:
        if not get_credentials():
            return jsonify({"error": "Not authenticated"}), 401
        
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
    # ... (no changes in this function)
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
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
        
        # Also remove from indexing status dict if it's there
        if playlist_id in indexing_status:
            del indexing_status[playlist_id]
        
        return jsonify({
            "success": True,
            "message": "Index and metadata deleted successfully"
        })
    except Exception as e:
        logger.error(f"Error deleting index: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/indexed-playlists')
def get_indexed_playlists():
    # ... (no changes in this function)
    try:
        indexed_playlists = get_indexed_playlists_metadata()
        return jsonify({"indexed_playlists": indexed_playlists})
    except Exception as e:
        logger.error(f"Error getting indexed playlists: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist/<playlist_id>/export', methods=['GET'])
def export_playlist(playlist_id):
    # ... (no changes in this function, just added encoding)
    try:
        if 'credentials' not in session:
            return jsonify({"error": "Not authenticated"}), 401
            
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
    # ... (no changes in this function)
    try:
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