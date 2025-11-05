import logging
from app import celery, es, logger
from app.youtube import get_playlist_videos, get_video_transcript
from app.elastic import create_index, index_video, save_playlist_metadata, get_indexed_video_ids
import traceback

# This is the new decorator that turns our function into a Celery task
@celery.task(bind=True)
def index_playlist_task(self, playlist_id, playlist_title, credentials_dict, incremental=False):
    """Background task to index a playlist."""
    
    # This is the 'meta' object our frontend will read
    status_meta = {
        "status": "in_progress",
        "progress": 0,
        "total": 0,
        "incremental": incremental,
        "title": playlist_title,
        "id": playlist_id,
        "new_videos_count": 0,
        "skipped": 0,
        "already_indexed": 0
    }
    
    try:
        # Update the task state so the frontend knows we've started
        self.update_state(state='PROGRESS', meta=status_meta)
        
        credentials = {
            'token': credentials_dict['token'],
            'refresh_token': credentials_dict.get('refresh_token'),
            'token_uri': credentials_dict['token_uri'],
            'client_id': credentials_dict['client_id'],
            'client_secret': credentials_dict['client_secret'],
            'scopes': credentials_dict['scopes']
        }
        
        videos = get_playlist_videos(playlist_id, credentials)
        if not videos:
            logger.warning(f"No videos found in playlist {playlist_id}")
            total_videos = 0
            success_count = 0
        else:
            total_videos = len(videos)
            success_count = 0
            
        status_meta["total"] = total_videos
        self.update_state(state='PROGRESS', meta=status_meta)
        
        index_name = f"playlist_{playlist_id.lower()}"
        index_created, existing_count = create_index(index_name, recreate=not incremental)
        
        already_indexed_ids = []
        if incremental:
            already_indexed_ids = get_indexed_video_ids(index_name)
            logger.info(f"Found {len(already_indexed_ids)} already indexed videos")
            status_meta["already_indexed"] = len(already_indexed_ids)
            self.update_state(state='PROGRESS', meta=status_meta)
        
        new_videos_count = 0
        skipped_count = 0
        
        if videos:
            for i, video in enumerate(videos):
                # We don't need a 'cancelled' check anymore, Celery handles this
                
                if incremental and video['id'] in already_indexed_ids:
                    skipped_count += 1
                    status_meta["skipped"] = skipped_count
                else:
                    try:
                        transcript = get_video_transcript(video['id'])
                        if index_video(index_name, video, transcript):
                            success_count += 1
                            new_videos_count += 1
                        status_meta["new_videos"] = new_videos_count
                    except Exception as e:
                        logger.error(f"Error indexing video {video['id']}: {e}")
                        continue
                
                # Update progress for every video
                status_meta["progress"] = i + 1
                self.update_state(state='PROGRESS', meta=status_meta)
        
        if incremental:
            total_success = success_count + len(already_indexed_ids)
        else:
            total_success = success_count
        
        playlist_data = {
            "id": playlist_id,
            "title": playlist_title,
            "videoCount": total_videos,
            "thumbnail": videos[0].get("thumbnail", "") if videos else ""
        }
        save_playlist_metadata(playlist_data, total_success)
        
        # Mark as complete
        status_meta["status"] = "completed"
        status_meta["success_count"] = total_success
        status_meta["new_videos_count"] = new_videos_count
        
        # Return the final status, which Celery stores
        return status_meta
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error indexing playlist {playlist_id}: {error_message}")
        traceback.print_exc()
        
        # On failure, update state with the error
        status_meta["status"] = "failed"
        status_meta["error"] = error_message
        self.update_state(state='FAILURE', meta=status_meta)
        
        # Re-raise the exception so Celery marks it as failed
        raise e