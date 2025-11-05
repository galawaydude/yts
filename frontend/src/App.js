import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import PlaylistSelector from './components/PlaylistSelector';
import SearchInterface from './components/SearchInterface';
import LoadingScreen from './components/LoadingScreen';
import LandingPage from './components/LandingPage';
import IndexingQueue from './components/IndexingQueue'; // Import the new component
import {
  indexPlaylist,
  logout,
  getIndexedPlaylists,
  deletePlaylistIndex,
  getIndexingStatus,
  getAuthStatus,
} from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [indexedPlaylists, setIndexedPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState(null);

  // NEW: This state will now hold the full status for all indexing playlists
  // From: ['PL1', 'PL2']
  // To:   [{id: 'PL1', status: 'in_progress', progress: 10, total: 50, title: 'My Playlist'}, ...]
  const [indexingPlaylists, setIndexingPlaylists] = useState([]);

  // REMOVED: These global state variables were causing the bugs
  // const [isIndexing, setIsIndexing] = useState(false);
  // const [indexingProgress, setIndexingProgress] = useState(null);

  const fetchIndexedPlaylists = useCallback(async () => {
    try {
      const response = await getIndexedPlaylists();
      setIndexedPlaylists(response.data.indexed_playlists || []);
    } catch (error) {
      console.error('Error fetching indexed playlists:', error);
    }
  }, []);

  // Check authentication status on component mount
  useEffect(() => {
    const checkAuth = async () => {
      setLoading(true);
      try {
        const response = await getAuthStatus();
        setIsAuthenticated(response.data.authenticated);
        if (response.data.authenticated) {
          fetchIndexedPlaylists();
        }
      } catch (error) {
        console.error('Error checking auth status:', error);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [fetchIndexedPlaylists]);

  // This function is now the main engine, running every 3 seconds
  // if there is anything in the indexing queue.
  const checkAllIndexingStatuses = useCallback(async () => {
    if (indexingPlaylists.length === 0) return;

    let hasCompleted = false;
    
    // Create a new array based on the results of the API calls
    const newIndexingPlaylists = await Promise.all(
      indexingPlaylists.map(async (playlist) => {
        try {
          const response = await getIndexingStatus(playlist.id);
          const status = response.data;

          if (status.status === 'completed' || status.status === 'failed') {
            hasCompleted = true; // Flag to refetch indexed list
            
            // Show notification
            if (status.status === 'completed') {
              let message = `Finished indexing ${playlist.title}.`;
              if (status.incremental && status.new_videos_count > 0) {
                message = `Added ${status.new_videos_count} new videos to ${playlist.title}.`;
              } else if (status.incremental) {
                message = `No new videos found in ${playlist.title}.`;
              }
              setNotification({ type: 'success', message });
            } else {
              setNotification({ type: 'error', message: `Failed to index ${playlist.title}: ${status.error}` });
            }
            
            // Return null to filter this playlist out of the queue
            return null;
          } else {
            // It's still in progress, update its status
            return {
              ...playlist,
              status: status.status,
              progress: status.progress,
              total: status.total,
            };
          }
        } catch (error) {
          console.error(`Error checking status for ${playlist.id}:`, error);
          // Keep it in the queue to retry
          return playlist;
        }
      })
    );

    // Filter out the null (completed/failed) items
    setIndexingPlaylists(newIndexingPlaylists.filter(Boolean));

    // If any playlist finished, refresh the main list
    if (hasCompleted) {
      fetchIndexedPlaylists();
    }
    
    // Clear notification after 5 seconds
    setTimeout(() => {
      setNotification(null);
    }, 5000);

  }, [indexingPlaylists, fetchIndexedPlaylists]);

  // Setup the polling interval
  useEffect(() => {
    if (indexingPlaylists.length === 0) return;

    const interval = setInterval(() => {
      checkAllIndexingStatuses();
    }, 3000); // Check every 3 seconds

    return () => clearInterval(interval);
  }, [indexingPlaylists, checkAllIndexingStatuses]);

  const handleSelectPlaylist = (playlist) => {
    const isIndexed = indexedPlaylists.some(
      (indexed) => indexed.playlist_id === playlist.id
    );

    setSelectedPlaylist({
      ...playlist,
      isIndexed,
    });
  };

  const handleDeleteIndex = async () => {
    if (!selectedPlaylist) return;

    if (
      window.confirm(
        `Are you sure you want to delete the index for "${selectedPlaylist.title}"?`
      )
    ) {
      try {
        setError(null);
        await deletePlaylistIndex(selectedPlaylist.id);
        
        // Success: Remove from indexed list and go back
        setIndexedPlaylists((prevPlaylists) =>
          prevPlaylists.filter((p) => p.playlist_id !== selectedPlaylist.id)
        );
        setSelectedPlaylist(null);
        setNotification({ type: 'success', message: 'Index deleted successfully.' });

      } catch (error) {
        // FIX: Check for 404 error
        if (error.response && error.response.status === 404) {
          // A 404 means it's already deleted. Treat as success.
          setIndexedPlaylists((prevPlaylists) =>
            prevPlaylists.filter((p) => p.playlist_id !== selectedPlaylist.id)
          );
          setSelectedPlaylist(null);
          setNotification({ type: 'info', message: 'Index was already deleted.' });
        } else {
          // A real error (like 500)
          console.error('Error deleting index:', error);
          setError('Failed to delete index');
        }
      }
    }
  };

  const handleIndexPlaylist = async (incremental = true, event = null) => {
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    if (!selectedPlaylist) return;

    // Check if it's already in the queue
    if (indexingPlaylists.some(p => p.id === selectedPlaylist.id)) {
      setNotification({ type: 'info', message: 'Playlist is already in the indexing queue.' });
      return;
    }

    try {
      setError(null);
      
      // Call the API to start the backend job
      await indexPlaylist(selectedPlaylist.id, incremental);

      // Add this playlist to the indexing queue
      setIndexingPlaylists((prev) => [
        ...prev,
        {
          id: selectedPlaylist.id,
          title: selectedPlaylist.title,
          status: 'in_progress', // Or 'pending' if you change backend
          progress: 0,
          total: selectedPlaylist.videoCount, // Use estimate
        },
      ]);
      
      setNotification({ type: 'success', message: 'Added to indexing queue.' });

    } catch (error) {
      console.error('Error starting indexing:', error);
      setError('Failed to start indexing');
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setIsAuthenticated(false);
      setSelectedPlaylist(null);
      setIndexedPlaylists([]);
      setIndexingPlaylists([]); // Clear the queue on logout
    } catch (error) {
      console.error('Error logging out:', error);
    }
  };

  const handleBackToPlaylists = () => {
    setSelectedPlaylist(null);
  };

  const renderContent = () => {
    // ---- Playlist Selector Page ----
    if (!selectedPlaylist) {
      return loading ? (
        <LoadingScreen message="Loading playlists..." />
      ) : (
        <>
          {/* Show the new queue component */}
          <IndexingQueue queue={indexingPlaylists} />
          <PlaylistSelector
            onSelectPlaylist={handleSelectPlaylist}
            indexedPlaylists={indexedPlaylists}
            // Pass the array of IDs
            indexingPlaylists={indexingPlaylists.map(p => p.id)}
          />
        </>
      );
    }

    // ---- Specific Playlist Page ----
    
    // FIX: Check if the *current* playlist is indexing
    const currentPlaylistStatus = indexingPlaylists.find(
      (p) => p.id === selectedPlaylist.id
    );

    return (
      <div className="playlist-content">
        <div className="playlist-header">
          <h2>{selectedPlaylist.title}</h2>
          <div className="playlist-actions">
            <button className="back-button" onClick={handleBackToPlaylists}>
              Back to Playlists
            </button>
          </div>
        </div>

        {/* FIX: Only show progress bar if the *current* playlist is indexing */}
        {currentPlaylistStatus && (
          <div className="indexing-status">
            <div className="indexing-progress">
              {currentPlaylistStatus.total > 0
                ? `Indexing playlist... (${currentPlaylistStatus.progress}/${currentPlaylistStatus.total})`
                : 'Preparing to index playlist...'}
            </div>
          </div>
        )}

        {indexedPlaylists.some((p) => p.playlist_id === selectedPlaylist.id) ? (
          // This playlist is indexed, show search
          <SearchInterface
            playlist={selectedPlaylist}
            onDeleteIndex={handleDeleteIndex}
            onReindex={handleIndexPlaylist}
          />
        ) : (
          // This playlist is NOT indexed, show index button
          <div className="index-container">
            <p>This playlist needs to be indexed before you can search it.</p>
            {/* Show message if it's indexing, or button if it's not */}
            {!currentPlaylistStatus ? (
              <button
                onClick={(e) => handleIndexPlaylist(true, e)}
                className="index-button"
              >
                Start Indexing
              </button>
            ) : (
              <div className="indexing-message">Indexing in progress...</div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app">
      {loading ? (
        <LoadingScreen message="Loading application..." />
      ) : isAuthenticated ? (
        <>
          <header className="app-header">
            <h1>YouTube Transcript Search</h1>
            <button onClick={handleLogout} className="logout-button">
              Logout
            </button>
          </header>

          {renderContent()}
        </>
      ) : (
        <LandingPage />
      )}

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}
      {notification && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
          <button onClick={() => setNotification(null)}>X</button>
        </div>
      )}
    </div>
  );
}

export default App;