from youtube_transcript_api import YouTubeTranscriptApi
from app.auth import build_youtube_client, API_SERVICE_NAME, API_VERSION
import googleapiclient.discovery
from google.oauth2.credentials import Credentials

def get_user_playlists():
    """Get all playlists for the authenticated user, including Liked Videos."""
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
                    'videoCount': liked_playlist['contentDetails']['itemCount']
                })
    except Exception as e:
        print(f"Error fetching Liked Videos playlist: {e}")
    
    # Get regular playlists
    try:
        request = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        
        for item in response.get('items', []):
            playlists.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                'videoCount': item['contentDetails']['itemCount']
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
    
    videos = []
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
            video_id = item['contentDetails']['videoId']
            
            # Get video details
            video_request = youtube.videos().list(
                part="snippet,statistics",
                id=video_id
            )
            video_response = video_request.execute()
            
            if video_response['items']:
                video_info = video_response['items'][0]
                
                # Use the channel title from the video info, not from the playlist item
                channel_title = video_info['snippet']['channelTitle']
                
                videos.append({
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': video_info['snippet'].get('description', ''),
                    'thumbnail': item['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                    'channelTitle': channel_title,  # Use the correct channel title
                    'publishedAt': item['snippet']['publishedAt'],
                    'viewCount': video_info['statistics'].get('viewCount', '0')
                })
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    
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