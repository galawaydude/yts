# Local Setup Guide

This guide will walk you through setting up and running the YouTube Playlist Search & Indexing Tool locally.

## Prerequisites

1. Python 3.8 or higher
2. Node.js 14 or higher
3. Elasticsearch 7.x
4. Google Developer Console project with YouTube Data API v3 enabled

## Step 1: Set Up Elasticsearch

1. Download and install Elasticsearch 7.x from the [official website](https://www.elastic.co/downloads/elasticsearch)
2. Start Elasticsearch:
   - **Windows**: Run `bin\elasticsearch.bat` from the Elasticsearch directory
   - **Mac/Linux**: Run `./bin/elasticsearch` from the Elasticsearch directory
3. Verify Elasticsearch is running by opening `http://localhost:9200` in your browser

## Step 2: Clone the Repository

If you haven't already, clone the repository to your local machine:

```
git clone <repository-url>
cd projectForTheThing
```

## Step 3: Set Up the Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment (recommended):
   ```
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Mac/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up Google OAuth credentials:
   - Go to the [Google Developer Console](https://console.developers.google.com/)
   - Create a new project or select an existing one
   - Enable the YouTube Data API v3
   - Create OAuth 2.0 credentials (Web application type)
   - Add `http://localhost:5000/api/auth/callback` as an authorized redirect URI
   - Add `http://localhost:3000` as an authorized JavaScript origin
   - Download the credentials as `client_secret.json` and place it in the backend directory

5. Configure environment variables:
   - Copy `.env.example` to `.env`:
     ```
     copy .env.example .env  # Windows
     cp .env.example .env    # Mac/Linux
     ```
   - Open the `.env` file and fill in your Google credentials:
     ```
     GOOGLE_CLIENT_ID=your-client-id
     GOOGLE_CLIENT_SECRET=your-client-secret
     YOUTUBE_API_KEY=your-api-key  # Optional, for higher quota limits
     ```

6. Start the Flask server:
   ```
   python run.py
   ```
   The server will run on `http://localhost:5000`

## Step 4: Set Up the Frontend

1. Open a new terminal and navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Verify the `.env` file exists with:
   ```
   REACT_APP_API_URL=http://localhost:5000/api
   ```
   If it doesn't exist, create it with this content.

4. Start the React development server:
   ```
   npm start
   ```
   The frontend will run on `http://localhost:3000`

## Step 5: Use the Application

1. Open your browser and go to `http://localhost:3000`
2. Sign in with your Google account
3. You should see your YouTube playlists
4. Select a playlist to index and search

## Troubleshooting

### Elasticsearch Connection Issues

- Make sure Elasticsearch is running on port 9200
- Check if you can access `http://localhost:9200` in your browser
- Restart Elasticsearch if needed

### OAuth Authentication Issues

- Verify your `client_secret.json` file is in the backend directory
- Check that your redirect URI is correctly set in Google Developer Console
- Make sure you're using the correct Google account

### Backend Server Issues

- Check for error messages in the terminal
- Verify all dependencies are installed
- Make sure the port 5000 is not in use by another application

### Frontend Issues

- Check for error messages in the browser console
- Verify the `.env` file has the correct API URL
- Make sure the port 3000 is not in use by another application
