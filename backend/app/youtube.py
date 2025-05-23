from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from app.auth import build_youtube_client, API_SERVICE_NAME, API_VERSION
from app import app # Import app for logger
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

logger = app.logger # Use app's logger

def get_user_playlists():
    """Get all playlists for the authenticated user, including Liked Videos and saved playlists."""
    youtube = build_youtube_client()
    if not youtube:
        return []
    
    playlists = []
    
    # Add Liked Videos special playlist
    try:
        # Get channel ID first
        channels_response = youtube.channels().list(
            part="contentDetails",
            mine=True
        ).execute()
        
        if channels_response['items']:
            channel = channels_response['items'][0]
            user_channel_id = channel['id']  # Store user's channel ID to check ownership
            liked_playlist_id = channel['contentDetails']['relatedPlaylists']['likes']
            
            # Get the liked videos playlist details
            liked_videos_response = youtube.playlists().list(
                part="snippet,contentDetails",
                id=liked_playlist_id
            ).execute()
            
            if liked_videos_response['items']:
                liked_playlist = liked_videos_response['items'][0]
                playlists.append({
                    'id': liked_playlist_id,
                    'title': "Liked Videos",
                    'thumbnail': liked_playlist['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                    'videoCount': liked_playlist['contentDetails']['itemCount'],
                    'isOwn': True
                })
    except HttpError as e:
        logger.error(f"HttpError fetching Liked Videos playlist: {e}")
    except Exception as e: # Catch other potential errors
        logger.error(f"Unexpected error fetching Liked Videos playlist: {e}")
    
    try:
        # Get all playlists in user's library (both owned and saved)
        request = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        
        for item in response.get('items', []):
            # Check if the playlist is owned by the user by comparing channel IDs
            is_own = item['snippet']['channelId'] == user_channel_id
            
            playlists.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                'videoCount': item['contentDetails']['itemCount'],
                'isOwn': is_own,
                'channelTitle': item['snippet']['channelTitle'] if not is_own else None
            })
            
        # Handle pagination if there are more playlists
        while 'nextPageToken' in response:
            request = youtube.playlists().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=50,
                pageToken=response['nextPageToken']
            )
            response = request.execute()
            
            for item in response.get('items', []):
                # Check if the playlist is owned by the user
                is_own = item['snippet']['channelId'] == user_channel_id
                
                playlists.append({
                    'id': item['id'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                    'videoCount': item['contentDetails']['itemCount'],
                    'isOwn': is_own,
                    'channelTitle': item['snippet']['channelTitle'] if not is_own else None
                })
                
    except HttpError as e:
        logger.error(f"HttpError fetching user playlists: {e}")
    except Exception as e: # Catch other potential errors
        logger.error(f"Unexpected error fetching user playlists: {e}")
    
    return playlists

def get_playlist_videos(playlist_id, credentials=None):
    """Get all videos in a playlist."""
    if credentials:
        youtube = googleapiclient.discovery.build(
            API_SERVICE_NAME,
            API_VERSION,
            credentials=Credentials(**credentials)
        )
    else:
        youtube = build_youtube_client()
        
    if not youtube:
        return []

    playlist_items_data = []
    video_ids = []
    next_page_token = None

    # Step 1: Fetch all playlist items (basic video info and video IDs)
    try:
        while True:
            request = youtube.playlistItems().list(
                part="snippet,contentDetails", # contentDetails for videoId, snippet for title, thumbnails, publishedAt, channelTitle of the video item
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                if item['snippet'].get('title') == 'Private video' or item['snippet'].get('title') == 'Deleted video':
                    logger.warning(f"Skipping private/deleted video: {item['snippet']['title']} (ID: {item['contentDetails']['videoId']}) in playlist {playlist_id}")
                    continue

                playlist_items_data.append({
                    'id': item['contentDetails']['videoId'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                    'publishedAt': item['snippet']['publishedAt'], 
                    'itemChannelTitle': item['snippet']['channelTitle'] # Channel that uploaded the video to the playlist
                })
                video_ids.append(item['contentDetails']['videoId'])
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
    except HttpError as e:
        logger.error(f"HttpError fetching playlist items for {playlist_id}: {e}")
        return [] # Return empty if initial fetch fails

    if not video_ids:
        logger.info(f"No video IDs found for playlist {playlist_id}.")
        return []

    # Step 2: Fetch video details (statistics, full description, actual video channel) in batches
    video_details_map = {}
    for i in range(0, len(video_ids), 50): # Process in batches of 50
        batch_ids = video_ids[i:i+50]
        try:
            video_request = youtube.videos().list(
                part="snippet,statistics,contentDetails", # snippet for description & actual channel, statistics for viewCount
                id=",".join(batch_ids)
            )
            video_response = video_request.execute()
            
            for video_info in video_response.get('items', []):
                video_details_map[video_info['id']] = {
                    'description': video_info['snippet'].get('description', ''),
                    'viewCount': video_info['statistics'].get('viewCount', '0'),
                    'videoChannelTitle': video_info['snippet']['channelTitle'], # The actual channel of the video
                    # 'duration': video_info['contentDetails'].get('duration') # Example if duration is needed
                }
        except HttpError as e:
            logger.error(f"HttpError fetching details for video batch in playlist {playlist_id}: {e}. IDs: {batch_ids}")
            # Continue processing other batches, these videos might lack some details

    # Step 3: Combine playlist item data with video details
    final_videos_list = []
    for item_data in playlist_items_data:
        details = video_details_map.get(item_data['id'], {})
        final_videos_list.append({
            'id': item_data['id'],
            'title': item_data['title'],
            'description': details.get('description', ''), # Use full description from video details
            'thumbnail': item_data['thumbnail'],
            # Prefer actual video's channel title if available, otherwise use playlist item's uploader title
            'channelTitle': details.get('videoChannelTitle', item_data['itemChannelTitle']), 
            'publishedAt': item_data['publishedAt'],
            'viewCount': details.get('viewCount', '0')
        })
        
    logger.info(f"Fetched {len(final_videos_list)} videos for playlist {playlist_id} using batched requests.")
    return final_videos_list

def get_video_transcript(video_id):
    """Get transcript for a video."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript_list
    except TranscriptsDisabled as e:
        logger.warning(f"Transcripts disabled for video {video_id}: {e}")
        return []
    except NoTranscriptFound as e:
        logger.warning(f"No transcript found for video {video_id}: {e}")
        return []
    except Exception as e: # Catch other potential youtube_transcript_api errors or general errors
        logger.error(f"Error getting transcript for video {video_id}: {e}")
        # Return empty list instead of None to avoid errors
        return [] 