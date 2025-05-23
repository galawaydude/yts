# YouTube Transcript Search (YTS)

A tool that lets you search videos from your personal YouTube playlists based on transcript information, title, and description. This project was inspired by a friend's need for personalized search in private playlists, similar to platforms like Filmot but with added functionalities.

## Tech Stack

-   **Frontend**: React.js
-   **Backend**: Flask (Python)
-   **Search Engine**: Elasticsearch 7.x (Successfully tested with 7.10.x, may work with other 7.x versions)
-   **Authentication**: Google OAuth2 (via YouTube API)

## Prerequisites

-   Python 3.8+
-   Node.js 14+ (LTS recommended)
-   pip (Python package installer)
-   Elasticsearch 7.x instance accessible to the backend.
-   A Google Developer Account with:
    -   YouTube Data API v3 enabled.
    -   OAuth 2.0 credentials (client ID and client secret) configured. Ensure your authorized redirect URIs in Google Cloud Console include the one you'll configure for the backend (e.g., `http://localhost:5000/api/auth/callback`).

## Project Structure

```
/
├── backend/        # Flask backend application
│   ├── app/          # Core application logic, routes, services
│   ├── venv/         # Python virtual environment (if created here)
│   ├── .env          # Backend environment variables (create this)
│   ├── .env.example  # Example for backend environment variables
│   ├── requirements.txt # Python dependencies
│   └── run.py        # Script to run the backend
├── frontend/       # React frontend application
│   ├── public/
│   ├── src/          # Source files
│   ├── .env          # Frontend environment variables (create this)
│   ├── .env.example  # Example for frontend environment variables
│   └── package.json  # Node dependencies
└── Readme.md
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Elasticsearch Setup

-   Ensure your Elasticsearch 7.x instance is running and accessible.
-   Verify its availability, typically at `http://localhost:9200` if running locally.
-   If using a cloud-hosted Elasticsearch (like Bonsai), have your connection URL and credentials ready.

### 3. Backend Setup

```bash
cd backend
```

**a. Create and Activate Virtual Environment:**

```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

**b. Environment Variables (`.env` file):**

Create a `.env` file in the `backend/` directory by copying from `backend/.env.example` and filling in your details:

```
# backend/.env - Essential for local development:
SECRET_KEY=your_very_secret_flask_key_here_make_it_long_and_random
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
YOUTUBE_API_KEY=your_youtube_data_api_key # Optional if all access is via OAuth user, but good for some checks
ELASTICSEARCH_URL=http://localhost:9200 # Adjust if your ES is elsewhere
FRONTEND_URL=http://localhost:3000
OAUTH_REDIRECT_URI=http://localhost:5000/api/auth/callback

# Optional/Advanced (defaults are usually fine for local dev):
# PORT=5000
# PRODUCTION=False
# ELASTICSEARCH_USERNAME= # For secured Elasticsearch
# ELASTICSEARCH_PASSWORD= # For secured Elasticsearch
# SESSION_COOKIE_SECURE=False # Set to True if using HTTPS locally
# SESSION_COOKIE_SAMESITE='Lax'
```

Refer to `backend/.env.example` for more options, especially for production.

**c. Install Python Dependencies:**

The `requirements.txt` file lists all necessary Python packages.

-   If `requirements.txt` is already provided and up-to-date:
    ```bash
    pip install -r requirements.txt
    ```
-   If you've added new dependencies or need to generate it for the first time:
    ```bash
    pip install Flask Flask-CORS elasticsearch google-api-python-client google-auth-oauthlib youtube-transcript-api python-dotenv
    pip freeze > requirements.txt
    ```
    It's good practice to update `requirements.txt` whenever you add or change dependencies.

**d. Run the Backend:**

```bash
python run.py
```

The backend should now be running, typically at `http://localhost:5000`.

### 4. Frontend Setup

```bash
cd frontend
```

**a. Environment Variables (`.env` file):**

Create a `.env` file in the `frontend/` directory by copying from `frontend/.env.example`:

```
# frontend/.env
REACT_APP_API_URL=http://localhost:5000/api
```
This tells your React app where the backend API is located.

**b. Install Node.js Dependencies:**

```bash
npm install
```

**c. Run the Frontend:**

```bash
npm start
```

The frontend development server should start, and the application will typically open in your browser at `http://localhost:3000`.

## Using the Application

1.  Open your browser to the frontend URL (e.g., `http://localhost:3000`).
2.  Log in using your Google account. This will grant the application permission to access your YouTube playlists.
3.  Once logged in, you'll see a list of your YouTube playlists.
4.  Select a playlist. If it's not already indexed, you'll be prompted to index it.
    -   **Indexing:** The application will fetch video details and transcripts for the selected playlist and store them in Elasticsearch. This may take time for large playlists.
    -   **Incremental Indexing (Update Index):** If a playlist is already indexed, you can choose to "Update Index". This will fetch only new videos added since the last indexing.
    -   **Full Reindex:** This option re-indexes the entire playlist from scratch.
5.  Once a playlist is indexed, you can search its content using the search bar. You can search by title, description, or transcript content.
6.  Search results will display matching videos, with highlighted segments from titles, descriptions, or transcripts. Clicking on a video or timestamp will take you to the video on YouTube.

## API Endpoints

The backend exposes the following API endpoints, all prefixed with `/api`.

### Authentication

| Method | Endpoint             | Description                                                                                                |
| :----- | :------------------- | :--------------------------------------------------------------------------------------------------------- |
| `GET`  | `/auth/login`        | Returns the Google OAuth URL to initiate the login flow. The frontend redirects the user to this URL.        |
| `GET`  | `/auth/callback`     | Handles the OAuth callback from Google after successful authentication. Manages token exchange. (Browser redirect) |
| `GET`  | `/auth/logout`       | Clears the user's session and logs them out.                                                               |
| `GET`  | `/auth/status`       | Checks if the current user is authenticated and returns `{"authenticated": true/false}`.                   |

### Playlists

| Method | Endpoint             | Description                                                                                                |
| :----- | :------------------- | :--------------------------------------------------------------------------------------------------------- |
| `GET`  | `/playlists`         | Fetches all of the authenticated user's YouTube playlists (both owned and saved).                            |
| `GET`  | `/indexed-playlists` | Retrieves a list of playlists that have already been indexed by the application and have metadata stored.    |

### Indexing

| Method   | Endpoint                          | Description                                                                                                                                                              |
| :------- | :-------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST`   | `/playlist/<playlist_id>/index`   | Starts the indexing process for a specific playlist. <br> **Body (JSON):** `{"incremental": true/false}` (Optional, `true` for incremental update, `false` for full reindex). |
| `GET`    | `/indexing-status`                | Gets the current indexing status for a playlist. <br> **Query Param:** `playlist_id=<playlist_id>`                                                                        |
| `DELETE` | `/playlist/<playlist_id>/delete-index` | Deletes the Elasticsearch index and stored metadata for the specified playlist.                                                                                         |

### Search & Data

| Method | Endpoint                             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| :----- | :----------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/playlist/<playlist_id>/search`     | Searches for videos within a specific indexed playlist. <br> **Query Params:** <br> - `q=<query_string>` (required) <br> - `page=<page_number>` (optional, default: 1) <br> - `size=<results_per_page>` (optional, default: 10) <br> - `search_in[]=<field>` (optional, can be repeated; values: `title`, `description`, `transcript`; defaults to all) <br> - `channel[]=<channel_name>` (optional, can be repeated to filter by specific channel names) |
| `GET`  | `/playlist/<playlist_id>/channels`   | Retrieves a list of unique video channel names present within the indexed data of a specific playlist.                                                                                                                                                                                                                                                                                                                                                   |
| `GET`  | `/playlist/<playlist_id>/export`     | Exports all indexed data (video metadata and transcripts) for a specific playlist as a downloadable JSON file.                                                                                                                                                                                                                                                                                                                                             |

### Debugging (Primarily for Development)

| Method | Endpoint                     | Description                                                                                                                             |
| :----- | :--------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/debug/index/<index_name>`  | Returns debugging information about a specific Elasticsearch index, including mapping and sample documents. Disabled in production. |

## Images

![Home page](./assets/home.png)
![Indexing page](./assets/indexing.png)
![Searching page](./assets/process.png)
![Results page](./assets/results.png)

## Future Considerations & Deployment Note

-   **Deployment:** Deploying applications with Elasticsearch can be challenging, especially finding cost-free hosting for Elasticsearch that persists data. This project is primarily designed for local execution or deployment environments where you can manage your Elasticsearch instance.
-   **Scalability:** For very large playlists or high user loads, further optimizations (e.g., background task queues like Celery for indexing, more robust Elasticsearch cluster) might be needed.

---

Contributions and suggestions are welcome!
```
