from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.proxies import WebshareProxyConfig
from app.auth import build_youtube_client, API_SERVICE_NAME, API_VERSION
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from app import app 

def get_user_playlists():
    """Get all playlists for the authenticated user."""
    youtube = build_youtube_client()
    if not youtube:
        return []
    
    playlists = []
    
    # Add Liked Videos special playlist
    try:
        channels_response = youtube.channels().list(
            part="contentDetails",
            mine=True
        ).execute()
        
        if channels_response['items']:
            channel = channels_response['items'][0]
            user_channel_id = channel['id']
            liked_playlist_id = channel['contentDetails']['relatedPlaylists']['likes']
            
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
        request = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        
        for item in response.get('items', []):
            is_own = item['snippet']['channelId'] == user_channel_id
            playlists.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                'videoCount': item['contentDetails']['itemCount'],
                'isOwn': is_own,
                'channelTitle': item['snippet']['channelTitle'] if not is_own else None
            })
            
        while 'nextPageToken' in response:
            request = youtube.playlists().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=50,
                pageToken=response['nextPageToken']
            )
            response = request.execute()
            
            for item in response.get('items', []):
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
    
    playlist_items_data = []
    next_page_token = None
    
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
        return [] 

    video_details_map = {}
    video_ids = [data['video_id'] for data in playlist_items_data]
    
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        
        video_request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(chunk) 
        )
        video_response = video_request.execute()
        
        for video_info in video_response.get('items', []):
            video_details_map[video_info['id']] = video_info

    videos = []
    for data in playlist_items_data:
        item = data['item']
        video_id = data['video_id']
        video_info = video_details_map.get(video_id)
        
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
    
    return videos

def get_video_transcript(video_id):
    """Get transcript for a video using Webshare proxies."""
    
    username = app.config.get('WEBSHARE_PROXY_USERNAME')
    password = app.config.get('WEBSHARE_PROXY_PASSWORD')

    proxy_config_obj = None
    
    if username and password:
        proxy_config_obj = WebshareProxyConfig(
            proxy_username=username,
            proxy_password=password
        )

    try:
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config_obj)
        transcript_obj = ytt_api.fetch(video_id)
        return transcript_obj.to_raw_data()

    # --- VALID "EMPTY" CASES (Return empty list) ---
    except (TranscriptsDisabled, NoTranscriptFound):
        print(f"Video {video_id} has no transcript. Indexing metadata only.")
        return [] 
        
    except VideoUnavailable:
        print(f"Video {video_id} is unavailable. Skipping.")
        return [] 

    # --- ERROR CASES (Raise exception to trigger Retry) ---
    except Exception as e:
        print(f"Proxy/Network error for {video_id}: {e}")
        raise e