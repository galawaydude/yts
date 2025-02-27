from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json

# OAuth setup
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

# Get credentials
flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
credentials = flow.run_local_server(port=8080)

# Build YouTube API client
youtube = build('youtube', 'v3', credentials=credentials)

# Get channel info
channels_response = youtube.channels().list(
    part="contentDetails",
    mine=True
).execute()

# Get Watch Later playlist ID
if channels_response['items']:
    channel = channels_response['items'][0]
    watch_later_id = channel['contentDetails']['relatedPlaylists']['watchLater']
    print(f"Watch Later ID: {watch_later_id}")
    
    # Try to get videos from Watch Later
    try:
        watch_later_videos = youtube.playlistItems().list(
            part="snippet",
            playlistId=watch_later_id,
            maxResults=5
        ).execute()
        
        print(f"Found {watch_later_videos['pageInfo']['totalResults']} videos in Watch Later")
        print(json.dumps(watch_later_videos, indent=2))
    except Exception as e:
        print(f"Error accessing Watch Later: {e}")