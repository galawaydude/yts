# YouTube Playlist Search & Indexing Tool

A powerful web application for searching, indexing, and managing YouTube playlists with advanced search capabilities powered by Elasticsearch.

![YouTube Playlist Search](https://img.shields.io/badge/YouTube-Playlist_Search-red)
![Flask](https://img.shields.io/badge/Backend-Flask-blue)
![React](https://img.shields.io/badge/Frontend-React-blue)
![Elasticsearch](https://img.shields.io/badge/Search-Elasticsearch-green)

## 🌟 Features

- **Google OAuth Authentication**: Securely access your YouTube playlists
- **Playlist Indexing**: Index your YouTube playlists for powerful searching
  - **Incremental Indexing**: Only index new videos added since last indexing
  - **Full Reindexing**: Completely rebuild the index for a playlist
  - **Real-time Status**: Visual indicators show indexing progress and status
- **Advanced Search Capabilities**:
  - Search across video titles, descriptions, and transcripts
  - Filter search results by channel
  - View search results with video thumbnails and metadata
- **Data Export**: Export indexed playlist data as JSON for backup or analysis
- **User-friendly Interface**:
  - Clean, modern UI with responsive design
  - Visual indicators for indexing status
  - Notification system for operation feedback

## 🚀 Getting Started

For detailed setup instructions, see:
- [LOCAL_SETUP.md](LOCAL_SETUP.md) for local development
- [DEPLOYMENT.md](DEPLOYMENT.md) for deployment to Railway with Bonsai Elasticsearch

### Prerequisites

- Python 3.7+
- Node.js 14+
- Elasticsearch 7.x
- Google API credentials

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up Google OAuth credentials:
   - Create a project in the [Google Developer Console](https://console.developers.google.com/)
   - Enable the YouTube Data API v3
   - Create OAuth 2.0 credentials
   - Download the credentials as `client_secret.json` and place in the backend directory

4. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your credentials.

5. Start the Flask server:
   ```
   python run.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file if needed.

4. Start the React development server:
   ```
   npm start
   ```

### Elasticsearch Setup

1. Install and start Elasticsearch according to the [official documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html)

2. Ensure Elasticsearch is running on the default port (9200)

## 🌐 Deployment

This application supports deployment to Railway with Bonsai Elasticsearch. For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Quick Deployment Overview

1. Set up a Bonsai Elasticsearch cluster
2. Deploy the backend to Railway
3. Deploy the frontend to Railway
4. Configure environment variables
5. Update Google OAuth redirect URIs

The application is designed to work both locally and in production environments with minimal configuration changes.

## 🔍 How to Use

1. **Authentication**: Sign in with your Google account to access your YouTube playlists
2. **Select a Playlist**: Browse your playlists and select one to work with
3. **Index the Playlist**: Choose between incremental update or full reindex
4. **Search**: Use the search interface to find videos within the indexed playlist
   - Enter search terms in the search box
   - Filter by channel using the channel chips
   - View search results with video details
5. **Export Data**: Use the Export Data button to download the indexed playlist data as JSON

## 🔧 Advanced Features

### Incremental Indexing

The incremental indexing feature only processes videos that have been added to a playlist since the last indexing operation. This significantly reduces processing time for large playlists.

### Real-time Indexing Status

The application provides visual feedback on the indexing process:
- Orange "Indexing..." badge with pulsing animation on playlists being indexed
- Progress indicators showing the current indexing status
- Notification system with different message types (success, info, warning)

### Multi-playlist Management

You can start indexing one playlist and navigate back to the playlist selection view to monitor multiple indexing operations simultaneously.

## 🛠️ Technical Architecture

### Backend (Flask)

- **app/routes.py**: API endpoints for authentication, playlist management, and search
- **app/elastic.py**: Elasticsearch integration for indexing and searching
- **app/youtube.py**: YouTube API integration for fetching playlist data
- **app/auth.py**: Google OAuth authentication handling

### Frontend (React)

- **src/App.js**: Main application component and state management
- **src/components/SearchInterface.js**: Search interface and results display
- **src/components/PlaylistSelector.js**: Playlist selection and management
- **src/services/api.js**: API service for backend communication

### Data Flow

1. User authenticates with Google OAuth
2. Application fetches user's YouTube playlists
3. User selects a playlist to index
4. Backend fetches playlist videos and metadata from YouTube API
5. Videos are indexed in Elasticsearch with titles, descriptions, and transcripts
6. Frontend provides search interface to query the Elasticsearch index
7. Search results are displayed with video metadata and links

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Elasticsearch](https://www.elastic.co/)
- [React](https://reactjs.org/)
- [Flask](https://flask.palletsprojects.com/)
