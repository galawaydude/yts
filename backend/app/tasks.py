import logging
import time # <-- NEW IMPORT for progress polling
from celery import group # <-- NEW IMPORT for fanning out tasks
from app import celery, es, logger, app # <-- IMPORT 'app' FOR SECURITY FIX
from app.youtube import get_playlist_videos, get_video_transcript
from app.elastic import create_index, index_video, save_playlist_metadata, get_indexed_video_ids
import traceback
from datetime import datetime

# ==========================================================
# ================= PERFORMANCE FIX (PART 1) ===============
# ==========================================================
# This is a new, small task to process a single video.
# The main task will "fan out" to this one.
@celery.task
def process_video_task(video_data, index_name):
    """Task to process a single video."""
    try:
        # get_video_transcript handles errors and returns []
        transcript = get_video_transcript(video_data['id'])
        
        # index_video handles errors and returns True/False
        if index_video(index_name, video_data, transcript):
            return (video_data['id'], True) # (id, success)
    except Exception as e:
        logger.error(f"Error indexing video {video_data['id']}: {e}")
        return (video_data['id'], False) # (id, failure)
    
    # Succeeded but no transcript, or other non-exception failure
    return (video_data['id'], False)
# ==========================================================
# ================== END OF FIX (PART 1) ===================
# ==========================================================


@celery.task(bind=True)
def index_playlist_task(self, playlist_id, playlist_title, credentials_dict, incremental=False):
    """
    Background task to index a playlist.
    This task now delegates the work of processing individual videos
    to the `process_video_task`.
    """
    
    # This status_meta object is the contract with your frontend.
    # We will maintain it exactly.
    status_meta = {
        "status": "in_progress",
        "progress": 0,
        "total": 0,
        "incremental": incremental,
        "title": playlist_title,
        "id": playlist_id,
        "new_videos_count": 0,
        "skipped": 0,
        "already_indexed": 0,
        "group_id": None # <-- ADDED THIS
    }
    
    try:
        self.update_state(state='PROGRESS', meta=status_meta)
        
        # ==========================================================
        # ==================== SECURITY FIX HERE ===================
        # ==========================================================
        # Load app secrets from config, not the task arguments
        credentials = {
            'token': credentials_dict['token'],
            'refresh_token': credentials_dict.get('refresh_token'),
            'token_uri': credentials_dict['token_uri'],
            'client_id': app.config['GOOGLE_CLIENT_ID'], # <-- FIXED
            'client_secret': app.config['GOOGLE_CLIENT_SECRET'], # <-- FIXED
            'scopes': credentials_dict['scopes']
        }
        # ==========================================================
        # ================== END OF SECURITY FIX ===================
        # ==========================================================
        
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
        
        # ==========================================================
        # ================= PERFORMANCE FIX (PART 2) ===============
        # ==========================================================
        # We no longer loop and index here. We build a list of tasks.
        
        tasks_to_run = []
        skipped_count = 0
        
        if videos:
            for video in videos:
                if incremental and video['id'] in already_indexed_ids:
                    skipped_count += 1
                else:
                    # Create a task "signature" for each video
                    tasks_to_run.append(process_video_task.s(video, index_name))

        status_meta["skipped"] = skipped_count
        self.update_state(state='PROGRESS', meta=status_meta)

        # If there are no new videos, we can skip to the end
        if not tasks_to_run:
            logger.info(f"No new videos to index for {playlist_id}.")
            new_videos_count = 0
            total_success = skipped_count + len(already_indexed_ids)
        
        else:
            logger.info(f"Creating a group of {len(tasks_to_run)} tasks for playlist {playlist_id}")
            # Create a group of tasks to run in parallel
            job_group = group(tasks_to_run)
            
            # Run the group
            result_group = job_group.apply_async()
            
            # ==================================================
            # === CANCELLATION FEATURE: SAVE GROUP ID ========
            # ==================================================
            status_meta["group_id"] = result_group.id
            self.update_state(state='PROGRESS', meta=status_meta)
            # ==================================================

            # Wait for the group to finish, updating progress as we go
            # This keeps your frontend polling logic working perfectly.
            while not result_group.ready():
                # Update frontend with how many tasks are done
                completed_count = result_group.completed_count()
                status_meta["progress"] = completed_count + skipped_count
                status_meta["new_videos_count"] = completed_count
                self.update_state(state='PROGRESS', meta=status_meta)
                time.sleep(3) # Poll every 3 seconds
            
            # All tasks are done, collect the final results
            results = result_group.get()
            
            # Count how many of the new videos were successful
            successful_new_videos = sum(1 for res in results if res[1] is True)
            
            new_videos_count = successful_new_videos
            total_success = skipped_count + len(already_indexed_ids) + successful_new_videos
            
            # Final progress update
            status_meta["progress"] = skipped_count + len(results)
            status_meta["new_videos_count"] = new_videos_count
            self.update_state(state='PROGRESS', meta=status_meta)

        # ==========================================================
        # ================== END OF FIX (PART 2) ===================
        # ==========================================================
        
        # This metadata logic is the same as before
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
        
        # This is the final metadata object the frontend needs
        status_meta["indexed_data"] = {
            "playlist_id": playlist_id,
            "title": playlist_title,
            "thumbnail": playlist_data["thumbnail"],
            "video_count": total_videos,
            "indexed_videos": total_success,
            "last_indexed": datetime.utcnow().isoformat()
        }
        
        # Return the final status, which Celery stores
        return status_meta
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error indexing playlist {playlist_id}: {error_message}")
        traceback.print_exc()
        
        status_meta["status"] = "failed"
        status_meta["error"] = error_message
        self.update_state(state='FAILURE', meta=status_meta)
        
        raise e