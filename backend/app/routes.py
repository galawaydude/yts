from flask import jsonify, request, session, redirect, url_for
from app import app, es
from app.auth import get_auth_url, get_credentials, SCOPES
from app.youtube import get_user_playlists, get_playlist_videos, get_video_transcript
from app.elastic import create_index, index_video, search_videos, create_metadata_index, save_playlist_metadata, get_indexed_playlists_metadata
from google_auth_oauthlib.flow import Flow
import os
import threading
import json
from datetime import datetime

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secret.json")

# Global variables
indexing_status = {}
indexing_threads = {}

# Add this after app initialization
create_metadata_index()

def index_playlist_task(playlist_id, credentials_dict):
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
            raise Exception("No videos found in playlist")
            
        total_videos = len(videos)
        indexing_status[playlist_id]["total"] = total_videos
        
        # Create index
        index_name = f"playlist_{playlist_id.lower()}"
        create_index(index_name)
        
        # Index each video
        success_count = 0
        for i, video in enumerate(videos):
            try:
                if indexing_status[playlist_id].get("cancelled"):
                    raise Exception("Indexing cancelled")
                    
                transcript = get_video_transcript(video['id'])
                # Index video regardless of transcript availability
                if index_video(index_name, video, transcript):
                    success_count += 1
                indexing_status[playlist_id]["progress"] = i + 1
            except Exception as e:
                print(f"Error indexing video {video['id']}: {e}")
                continue
        
        if success_count == 0:
            raise Exception("No videos could be indexed")
        
        # Save playlist metadata
        playlist_data = {
            "id": playlist_id,
            "title": videos[0]["channelTitle"],  # Use first video's channel as playlist title
            "videoCount": total_videos,
            "thumbnail": videos[0].get("thumbnail", "")
        }
        save_playlist_metadata(playlist_data, success_count)
        
        # Mark as complete
        indexing_status[playlist_id]["status"] = "completed"
        indexing_status[playlist_id]["success_count"] = success_count
        
    except Exception as e:
        error_message = str(e)
        print(f"Error indexing playlist: {error_message}")
        indexing_status[playlist_id] = {
            "status": "failed",
            "error": error_message
        }
    finally:
        # Clean up thread reference
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
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('callback', _external=True)
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
    
    return redirect(app.config.get('FRONTEND_URL', 'http://localhost:3000'))

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
    """Get user's playlists."""
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    playlists = get_user_playlists()
    return jsonify({"playlists": playlists})

@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get the current indexing status."""
    playlist_id = request.args.get('playlist_id')
    if not playlist_id:
        return jsonify({"error": "Missing playlist_id parameter"}), 400
    
    # Get status
    status = indexing_status.get(playlist_id, {
        "status": "not_started",
        "progress": 0,
        "total": 0
    })
    
    # Check if thread is still alive
    thread = indexing_threads.get(playlist_id)
    if thread and not thread.is_alive() and status["status"] == "in_progress":
        status["status"] = "failed"
        status["error"] = "Indexing process died unexpectedly"
    
    print(f"Indexing status for {playlist_id}: {status}")
    return jsonify(status)

@app.route('/api/playlist/<playlist_id>/index', methods=['POST'])
def index_playlist(playlist_id):
    """Start indexing a playlist."""
    credentials = get_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Use original case for playlist ID
    if playlist_id in indexing_threads and indexing_threads[playlist_id].is_alive():
        return jsonify({"error": "Playlist is already being indexed"}), 409
    
    try:
        indexing_status[playlist_id] = {
            "status": "in_progress",
            "progress": 0,
            "total": 0
        }
        
        # Create index with lowercase name for consistency
        index_name = f"playlist_{playlist_id.lower()}"
        
        # Get credentials as dictionary
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
            args=(playlist_id, credentials_dict)
        )
        indexing_threads[playlist_id] = thread
        thread.start()
        
        return jsonify({"success": True, "message": "Indexing started"})
        
    except Exception as e:
        error_message = str(e)
        print(f"Error starting indexing: {error_message}")
        return jsonify({"error": error_message}), 500

@app.route('/api/playlist/<playlist_id>/search')
def search_playlist(playlist_id):
    """Search for videos in a playlist."""
    try:
        if not get_credentials():
            return jsonify({"error": "Not authenticated"}), 401
        
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        search_in = request.args.getlist('search_in')
        
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Playlist not indexed yet"}), 404
        
        from_pos = (page - 1) * size
        results = search_videos(index_name, query, size, from_pos, search_in)
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'total': 0,
            'results': []
        })

@app.route('/api/playlist/<playlist_id>/delete-index', methods=['DELETE'])
def delete_playlist_index(playlist_id):
    """Delete the index for a playlist."""
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        index_name = f"playlist_{playlist_id.lower()}"
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Playlist not indexed"}), 404
        
        # Delete the index
        es.indices.delete(index=index_name)
        
        # Delete the metadata
        es.delete(
            index="yts_metadata",
            id=playlist_id,
            ignore=[404]
        )
        
        return jsonify({
            "success": True,
            "message": "Index and metadata deleted successfully"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/indexed-playlists')
def get_indexed_playlists():
    """Get a list of all indexed playlists with metadata."""
    if not get_credentials():
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        metadata = get_indexed_playlists_metadata()
        return jsonify({
            "indexed_playlists": metadata
        })
    except Exception as e:
        print(f"Error getting indexed playlists: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/index/<index_name>')
def debug_index(index_name):
    """Debug endpoint to check index contents."""
    try:
        # Check if index exists
        if not es.indices.exists(index=index_name):
            return jsonify({"error": "Index does not exist"}), 404

        # Get index mapping
        mapping = es.indices.get_mapping(index=index_name)
        
        # Get a sample of documents
        sample = es.search(
            index=index_name,
            body={
                "size": 1,
                "query": {"match_all": {}}
            }
        )

        return jsonify({
            "exists": True,
            "mapping": mapping,
            "doc_count": es.count(index=index_name)['count'],
            "sample_doc": sample['hits']['hits'][0] if sample['hits']['hits'] else None
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 