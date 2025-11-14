
# YTS

  

YTS (Youtube Transcript Search) is a high-performance distributed search engine designed to index and search personal YouTube playlists. Unlike standard YouTube search, which does not let you search through your playlists, YTS, lets you do that, and a little more...

  

## Features

  

- Go beyond titles. Search for any spoken word or phrase across the entire video library of a playlist to find exactly what you're looking for.

- Don't just find a video—find the moment. Search results link directly to the exact timestamp a keyword was mentioned, letting you jump straight to the relevant part.

- Use powerful query logic to narrow your results. Find videos that contain "Python" AND "Flask" but "NOT Java", or "AWS" OR "GCP"

- When you update a playlist, the system automatically detects and skips videos that are already indexed, downloading only the new ones. This saves time and proxy bandwidth.

- For large playlists with multiple creators, you can instantly filter search results to show videos from only the specific channels you select.

- Download the complete indexed data for any playlist, including all metadata and transcript segments, in a clean JSON format.

  

## Setup (Local Development, works only on WSL)

  

This guide assumes you have **Redis** and **Elasticsearch** installed and running on `localhost:6379` and `http://localhost:9200`.

  

### 1. Clone the Repository

```bash

git clone https://github.com/galawaydude/yts

cd yts

```

  

### 2. Configure Backend (Python)

First, set up your Python environment and install dependencies.

  

```bash

cd backend

python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

```

  

### 3. Configure Frontend (React)

In a separate terminal, install the Node.js dependencies.

  

```bash

cd frontend

npm install

```

  

### 4. Set Environment Variables

Create a file named `.env` in the `backend/` directory.  

Fill it with the stuff given in the example env

  

### 5. Run the Application

You must run the following commands in 3 separate terminals.

  

#### Terminal 1: Start the Flask API

```bash

# In the /backend directory

source venv/bin/activate

python run.py

```

  

#### Terminal 2: Start the Celery Worker

```bash

# In the /backend directory

source venv/bin/activate

celery -A app.celery worker --loglevel=info -P gevent -c 50

```

  

#### Terminal 3: Start the React App

```bash

# In the /frontend directory

npm start

```

  
  

The website is deployed here: **https://yts-88.com/**