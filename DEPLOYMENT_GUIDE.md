# Deployment Guide and Conversation

## Deployment Steps for Railway with Bonsai Elasticsearch

### Step 1: Set Up Bonsai Elasticsearch

1. Create a Bonsai account at [bonsai.io](https://bonsai.io/)
2. Create a new Elasticsearch cluster (free tier works for testing)
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

## Our Conversation About Local Setup and Deployment

### Question: Will the application run locally without any changes?

Based on my analysis, the application should run locally without any additional changes, but there are a few prerequisites:

1. **Elasticsearch must be running** on port 9200
2. **Google OAuth credentials must be set up** - you already have a client_secret.json file in your backend directory

### Here's the verdict:

Yes, the application should run locally without any additional changes if you:

1. **Start Elasticsearch** on port 9200
2. **Start the backend server**:
   ```
   cd backend
   python run.py
   ```
3. **Start the frontend server**:
   ```
   cd frontend
   npm start
   ```

The application is already configured to:
- Use local Elasticsearch at `http://localhost:9200`
- Load Google OAuth credentials from your existing client_secret.json file
- Connect the frontend to the backend at `http://localhost:5000/api`
- Use the correct OAuth redirect URI for local development

### Potential issues you might encounter:

1. **Elasticsearch not running**: If Elasticsearch isn't running on port 9200, the backend will log an error but should still start. However, indexing and search functionality won't work.

2. **Google OAuth credentials**: The application will try to use your existing client_secret.json file. If this file doesn't have the correct redirect URIs (`http://localhost:5000/api/auth/callback` and `http://localhost:3000` as an authorized JavaScript origin), authentication will fail.

3. **Environment variables**: The application will use the .env files I created, which have default values for local development. If you need to customize any settings, you can edit these files.

4. **Dependencies**: Make sure all dependencies are installed:
   - For the backend: `pip install -r requirements.txt`
   - For the frontend: `npm install`

If you encounter any issues, the detailed troubleshooting sections in the LOCAL_SETUP.md file should help you resolve them.
