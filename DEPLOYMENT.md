# Deployment & Local Setup Guide

## Running Locally (Step by Step)

### Step 1: Set Up Elasticsearch

1. Download and install Elasticsearch 7.x from the [official website](https://www.elastic.co/downloads/elasticsearch)
2. Start Elasticsearch:
   - **Windows**: Run `bin\elasticsearch.bat` from the Elasticsearch directory
   - **Mac/Linux**: Run `./bin/elasticsearch` from the Elasticsearch directory
3. Verify Elasticsearch is running by opening `http://localhost:9200` in your browser

### Step 2: Set Up the Backend

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

### Step 3: Set Up the Frontend

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

### Step 4: Use the Application

1. Open your browser and go to `http://localhost:3000`
2. Sign in with your Google account
3. You should see your YouTube playlists
4. Select a playlist to index and search

## Deploying to Railway with Bonsai (Step by Step)

### Step 1: Set Up Bonsai Elasticsearch

1. Create a Bonsai account at [bonsai.io](https://bonsai.io/)
2. Create a new Elasticsearch cluster:
   - Sign up for a free account or choose a paid plan
   - Create a new cluster (the free tier works for testing)
3. Get your connection details:
   - Go to the "Access" tab in your cluster dashboard
   - Note your cluster URL (e.g., `https://username:password@cluster-name.bonsaisearch.net:443`)
   - Note your access credentials (username and password)

### Step 2: Prepare Your Repository for Deployment

1. Make sure your code is in a GitHub repository
2. Ensure your repository includes:
   - Updated `requirements.txt` in the backend directory
   - `Procfile` in the backend directory
   - `package.json` in both the root and frontend directories

### Step 3: Deploy the Backend to Railway

1. Create a Railway account at [railway.app](https://railway.app/)
2. Create a new project:
   - Click "New Project" > "Deploy from GitHub repo"
   - Select your GitHub repository
   - Railway will detect your repository

3. Configure the backend service:
   - In your project, go to "Settings"
   - Set the root directory to `/backend`
   - Set the build command to `pip install -r requirements.txt`
   - Set the start command to `gunicorn --bind 0.0.0.0:$PORT run:app`

4. Set up environment variables:
   - Go to the "Variables" tab
   - Add the following variables (replace with your actual values):
   
   ```
   PRODUCTION=True
   SECRET_KEY=your-secure-random-string
   PORT=$PORT
   
   # Google OAuth
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   YOUTUBE_API_KEY=your-youtube-api-key
   
   # Bonsai Elasticsearch
   ELASTICSEARCH_URL=https://your-bonsai-cluster-url.bonsaisearch.net:443
   ELASTICSEARCH_USERNAME=your-bonsai-username
   ELASTICSEARCH_PASSWORD=your-bonsai-password
   
   # The frontend URL will be your Railway frontend URL once deployed
   # For now, use a placeholder and update it later
   FRONTEND_URL=https://your-frontend-railway-app.up.railway.app
   
   # The OAuth redirect URI will be your backend URL + /api/auth/callback
   # For now, use a placeholder and update it later
   OAUTH_REDIRECT_URI=https://your-backend-railway-app.up.railway.app/api/auth/callback
   
   # Session configuration
   SESSION_COOKIE_SECURE=True
   SESSION_COOKIE_SAMESITE=None
   ```

5. Deploy the backend:
   - Railway will automatically deploy your backend
   - Note the generated URL (e.g., `https://your-backend-app.up.railway.app`)

### Step 4: Deploy the Frontend to Railway

1. Add a new service to your Railway project:
   - Click "New Service" > "GitHub Repo"
   - Select the same repository

2. Configure the frontend service:
   - In the service settings, set the root directory to `/frontend`
   - Set the build command to `npm install && npm run build`
   - Set the start command to `npx serve -s build`

3. Set up environment variables:
   - Go to the "Variables" tab
   - Add the following variable:
   ```
   REACT_APP_API_URL=https://your-backend-railway-app.up.railway.app/api
   ```
   Replace with your actual backend URL

4. Deploy the frontend:
   - Railway will automatically deploy your frontend
   - Note the generated URL (e.g., `https://your-frontend-app.up.railway.app`)

### Step 5: Update Environment Variables and Google OAuth

1. Update the backend environment variables:
   - Go back to your backend service in Railway
   - Update the following variables with the actual URLs:
   ```
   FRONTEND_URL=https://your-frontend-railway-app.up.railway.app
   OAUTH_REDIRECT_URI=https://your-backend-railway-app.up.railway.app/api/auth/callback
   ```

2. Update Google OAuth configuration:
   - Go to the [Google Developer Console](https://console.developers.google.com/)
   - Select your project
   - Go to "Credentials" > "OAuth 2.0 Client IDs"
   - Edit your OAuth client
   - Add the following authorized redirect URI:
     `https://your-backend-railway-app.up.railway.app/api/auth/callback`
   - Add the following authorized JavaScript origin:
     `https://your-frontend-railway-app.up.railway.app`

### Step 6: Test Your Deployment

1. Open your frontend URL in a browser
2. Sign in with your Google account
3. You should be able to:
   - See your YouTube playlists
   - Index playlists
   - Search indexed playlists

## Troubleshooting

### Local Development Issues

1. **Elasticsearch Connection Issues**:
   - Make sure Elasticsearch is running on port 9200
   - Check if you can access `http://localhost:9200` in your browser
   - Restart Elasticsearch if needed

2. **OAuth Authentication Issues**:
   - Verify your `client_secret.json` file is in the backend directory
   - Check that your redirect URI is correctly set in Google Developer Console
   - Make sure you're using the correct Google account

3. **Backend Server Issues**:
   - Check for error messages in the terminal
   - Verify all dependencies are installed
   - Make sure the port 5000 is not in use by another application

4. **Frontend Issues**:
   - Check for error messages in the browser console
   - Verify the `.env` file has the correct API URL
   - Make sure the port 3000 is not in use by another application

### Railway Deployment Issues

1. **Elasticsearch Connection Issues**:
   - Verify your Bonsai credentials in Railway environment variables
   - Check Bonsai dashboard for connection limits or errors
   - Look at Railway logs for connection errors

2. **OAuth Authentication Issues**:
   - Make sure redirect URIs are correctly configured in Google Developer Console
   - Verify environment variables in Railway match your Google credentials
   - Check Railway logs for authentication errors

3. **CORS Issues**:
   - Ensure `FRONTEND_URL` is correctly set in backend environment variables
   - Verify `SESSION_COOKIE_SAMESITE` is set to `None` for cross-domain cookies
   - Check that `SESSION_COOKIE_SECURE` is set to `True` for HTTPS

4. **Session Issues**:
   - Make sure `SECRET_KEY` is properly set
   - Check Railway logs for session-related errors
   - Try clearing browser cookies and cache
