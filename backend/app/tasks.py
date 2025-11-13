from app import celery, logger
from app.youtube import get_playlist_videos, get_video_transcript
from app.elastic import create_index, index_video, save_playlist_metadata, get_indexed_video_ids
from celery import group
from celery.exceptions import MaxRetriesExceededError
import time
from datetime import datetime

@celery.task(bind=True, max_retries=3)
def process_video_task(self, video_data, index_name):
    try:
        # 1. Try to get transcript
        transcript = get_video_transcript(video_data['id'])
        
        # 2. Index whatever we got
        if index_video(index_name, video_data, transcript):
            return (video_data['id'], True)
            
    except Exception as e:
        # 3. Handle Proxy/Network Errors -> RETRY
        logger.warning(f"Error/Proxy fail for {video_data['id']}: {e}. Retrying...")
        try:
            # Wait 1 second, then restart task (picking new proxy)
            raise self.retry(exc=e, countdown=1)
        except MaxRetriesExceededError:
            logger.error(f"Failed to fetch {video_data['id']} after 3 attempts. Skipping.")
            return (video_data['id'], False)
    
    return (video_data['id'], False)

@celery.task(bind=True)
def index_playlist_task(self, playlist_id, playlist_title, credentials_dict, incremental=False):
    status_meta = {
        "status": "starting", 
        "message": "Initializing...", 
        "progress": 0,
        "total": 0,
        "incremental": incremental,
        "title": playlist_title,
        "id": playlist_id
    }
    
    try:
        # --- UI STATUS UPDATE ---
        status_meta["message"] = "Fetching video list from YouTube (this may take a minute)..."
        self.update_state(state='PROGRESS', meta=status_meta)
        
        credentials = credentials_dict 

        videos = get_playlist_videos(playlist_id, credentials)
        
        if not videos:
            status_meta["total"] = 0
            status_meta["status"] = "completed"
            status_meta["message"] = "Playlist is empty or private."
            return status_meta
            
        total_videos = len(videos)
        status_meta["total"] = total_videos
        status_meta["message"] = f"Found {total_videos} videos. Preparing database..."
        self.update_state(state='PROGRESS', meta=status_meta)
        
        index_name = f"playlist_{playlist_id.lower()}"
        create_index(index_name, recreate=not incremental)
        
        already_indexed_ids = []
        if incremental:
            status_meta["message"] = "Checking existing videos..."
            self.update_state(state='PROGRESS', meta=status_meta)
            already_indexed_ids = get_indexed_video_ids(index_name)
            status_meta["already_indexed"] = len(already_indexed_ids)
        
        status_meta["message"] = "Queueing download tasks..."
        self.update_state(state='PROGRESS', meta=status_meta)
        
        tasks_to_run = []
        skipped_count = 0
        
        for video in videos:
            if incremental and video['id'] in already_indexed_ids:
                skipped_count += 1
            else:
                tasks_to_run.append(process_video_task.s(video, index_name))

        status_meta["skipped"] = skipped_count
        
        if not tasks_to_run:
            new_videos_count = 0
            total_success = skipped_count + len(already_indexed_ids)
            status_meta["message"] = "All videos already indexed."
        else:
            job_group = group(tasks_to_run)
            result_group = job_group.apply_async()
            
            status_meta["group_id"] = result_group.id
            status_meta["message"] = "Downloading transcripts..."
            status_meta["status"] = "in_progress"
            self.update_state(state='PROGRESS', meta=status_meta)
            
            while not result_group.ready():
                completed_count = result_group.completed_count()
                status_meta["progress"] = completed_count + skipped_count
                status_meta["new_videos_count"] = completed_count
                
                # Show percentage
                pct = int((status_meta["progress"] / total_videos) * 100)
                status_meta["message"] = f"Indexing: {pct}% ({status_meta['progress']}/{total_videos})"
                
                self.update_state(state='PROGRESS', meta=status_meta)
                time.sleep(2) 
            
            new_videos_count = result_group.completed_count()
            total_success = skipped_count + len(already_indexed_ids) + new_videos_count
            
            status_meta["progress"] = skipped_count + new_videos_count
            self.update_state(state='PROGRESS', meta=status_meta)
        
        status_meta["message"] = "Finalizing..."
        self.update_state(state='PROGRESS', meta=status_meta)
        
        playlist_data = {
            "id": playlist_id,
            "title": playlist_title,
            "videoCount": total_videos,
            "thumbnail": videos[0].get("thumbnail", "") if videos else ""
        }
        save_playlist_metadata(playlist_data, total_success)
        
        status_meta["status"] = "completed"
        status_meta["message"] = "Indexing complete!"
        status_meta["success_count"] = total_success
        
        status_meta["indexed_data"] = {
            "playlist_id": playlist_id,
            "title": playlist_title,
            "thumbnail": playlist_data["thumbnail"],
            "video_count": total_videos,
            "indexed_videos": total_success,
            "last_indexed": datetime.utcnow().isoformat()
        }
        
        return status_meta
        
    except Exception as e:
        logger.error(f"Error indexing playlist {playlist_id}: {e}")
        status_meta["status"] = "failed"
        status_meta["error"] = str(e)
        self.update_state(state='FAILURE', meta=status_meta)
        raise e