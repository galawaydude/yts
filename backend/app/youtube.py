from youtube_transcript_api import YouTubeTranscriptApi
from app.auth import build_youtube_client, API_SERVICE_NAME, API_VERSION
import googleapiclient.discovery
from google.oauth2.credentials import Credentials

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
    except Exception as e:
        print(f"Error fetching Liked Videos playlist: {e}")
    
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
                
    except Exception as e:
        print(f"Error fetching user playlists: {e}")
    
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
    
    # --- START REFACTOR: BATCHING VIDEO DETAILS ---
    
    playlist_items_data = []
    next_page_token = None
    
    # Step 1: Get all playlist items and their video IDs
    while True:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        
        for item in response.get('items', []):
            playlist_items_data.append({
                'item': item,
                'video_id': item['contentDetails']['videoId']
            })
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    
    if not playlist_items_data:
        return [] # Playlist is empty

    # Step 2: Get all video details (stats, description) in batches of 50
    video_details_map = {}
    video_ids = [data['video_id'] for data in playlist_items_data]
    
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        
        video_request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(chunk)  # Batch request for 50 videos
        )
        video_response = video_request.execute()
        
        for video_info in video_response.get('items', []):
            video_details_map[video_info['id']] = video_info

    # Step 3: Combine playlist data with video details
    # This ensures the final data structure is identical to your original code
    videos = []
    for data in playlist_items_data:
        item = data['item']
        video_id = data['video_id']
        video_info = video_details_map.get(video_id) # Safely get details
        
        # Only add video if details were found (i.e., not private/deleted)
        if video_info:
            videos.append({
                'id': video_id,
                'title': item['snippet']['title'],
                'description': video_info['snippet'].get('description', ''),
                'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                'channelTitle': video_info['snippet']['channelTitle'],
                'publishedAt': item['snippet']['publishedAt'],
                'viewCount': video_info['statistics'].get('viewCount', '0')
            })
    
    # --- END REFACTOR ---
    
    return videos

def get_video_transcript(video_id):
    """Get transcript for a video."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript_list
    except Exception as e:
        print(f"Error getting transcript for video {video_id}: {e}")
        # Return empty list instead of None to avoid errors
        return []