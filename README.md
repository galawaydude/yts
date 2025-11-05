# YouTube Transcript Search

A powerful web application that enables efficient searching through YouTube video transcripts. Built with a sleek dark retro interface, this tool helps you find specific content within your YouTube playlists.

## Features

- **Smart Transcript Search**: Search through video transcripts with millisecond-precise timestamps
- **Playlist Management**: 
  - View and manage both your created and saved playlists
  - Automatic reindexing when playlist content changes
  - Real-time indexing status updates
- **Advanced Search Capabilities**:
  - Search across multiple videos simultaneously
  - Results show exact transcript matches with context
  - Direct links to specific video timestamps
- **Modern UI**:
  - Dark retro theme with responsive design
  - Intuitive pagination with direct page navigation
  - Real-time search feedback and result counts

## Tech Stack

- **Frontend**: React.js with custom CSS
- **Backend**: Python
- **APIs**: YouTube Data API, YouTube Transcript API
- **Search**: Custom indexing and search algorithm

## Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd youtube-transcript-search
```

2. Install backend dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Install frontend dependencies:
```bash
cd frontend
npm install
```

4. Set up environment variables:
   - Create `.env` file in the backend directory
   - Add your YouTube API credentials:
     ```
     YOUTUBE_API_KEY=your_api_key
     ```

5. Start the backend server:
```bash
python app.py
```

6. Start the frontend development server:
```bash
npm start
```

## Usage

1. **Authentication**: 
   - Log in with your YouTube account
   - Grant necessary permissions for playlist access

2. **Select Playlists**:
   - Choose from your created or saved playlists
   - Wait for initial indexing to complete

3. **Search**:
   - Enter search terms in the search bar
   - Use the pagination controls to navigate results
   - Click timestamp links to jump to specific video moments

## Contributing

Feel free to submit issues and enhancement requests!

## License

[Your chosen license]

## Acknowledgments

- YouTube Data API
- YouTube Transcript API
- React.js Community 