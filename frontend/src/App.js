import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import PlaylistSelector from './components/PlaylistSelector';
import SearchInterface from './components/SearchInterface';
import LoadingScreen from './components/LoadingScreen';
import LandingPage from './components/LandingPage';
import IndexingQueue from './components/IndexingQueue';
import {
  indexPlaylist,
  logout,
  getIndexedPlaylists,
  deletePlaylistIndex,
  getIndexingStatus,
  getAuthStatus,
  cancelIndexing, // <-- IMPORT NEW FUNCTION
} from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [indexedPlaylists, setIndexedPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState(null);
  const [indexingPlaylists, setIndexingPlaylists] = useState([]);

  const fetchIndexedPlaylists = useCallback(async () => {
    try {
      const response = await getIndexedPlaylists();
      setIndexedPlaylists(response.data.indexed_playlists || []);
    } catch (error) {
      console.error('Error fetching indexed playlists:', error);
    }
  }, []);

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

  // This polling function is updated to fix the race condition
  const checkAllIndexingStatuses = useCallback(async () => {
    if (indexingPlaylists.length === 0) return;

    // A list to hold the new metadata from completed tasks
    let completedPlaylistsData = [];
    
    const newIndexingPlaylists = await Promise.all(
      indexingPlaylists.map(async (playlist) => {
        try {
          const response = await getIndexingStatus(playlist.id);
          const status = response.data;

          if (status.status === 'completed' || status.status === 'failed') {
            
            if (status.status === 'completed') {
              let message = `Finished indexing ${playlist.title}.`;
              if (status.incremental && status.new_videos_count > 0) {
                message = `Added ${status.new_videos_count} new videos to ${playlist.title}.`;
              } else if (status.incremental) {
                message = `No new videos found in ${playlist.title}.`;
              }
              setNotification({ type: 'success', message });

              // Save the new metadata from the response
              if (status.indexed_data) {
                completedPlaylistsData.push(status.indexed_data);
              }

            } else {
              setNotification({ type: 'error', message: `Failed to index ${playlist.title}: ${status.error}` });
            }
            
            return null; // Filter this playlist out
          } else if (status.status === 'not_started') {
            // This can happen if the task was cancelled on the backend
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
          return playlist; // Keep it in the queue to retry
        }
      })
    );

    // Filter out the null (completed/failed) items
    setIndexingPlaylists(newIndexingPlaylists.filter(Boolean));

    // Instead of re-fetching, we manually update the state
    // with the data we just got from the poll.
    if (completedPlaylistsData.length > 0) {
      setIndexedPlaylists((prev) => {
        let newList = [...prev];
        completedPlaylistsData.forEach(newPlaylist => {
          const existingIndex = newList.findIndex(p => p.playlist_id === newPlaylist.playlist_id);
          if (existingIndex !== -1) {
            // It was a re-index, replace it
            newList[existingIndex] = newPlaylist;
          } else {
            // It's a new one, add it to the top
            newList.unshift(newPlaylist);
          }
        });
        return newList;
      });
    }
    
    setTimeout(() => {
      setNotification(null);
    }, 5000);

  }, [indexingPlaylists]); // Removed fetchIndexedPlaylists from dependencies

  useEffect(() => {
    if (indexingPlaylists.length === 0) return;

    const interval = setInterval(() => {
      checkAllIndexingStatuses();
    }, 3000);

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
        
        setIndexedPlaylists((prevPlaylists) =>
          prevPlaylists.filter((p) => p.playlist_id !== selectedPlaylist.id)
        );
        setSelectedPlaylist(null);
        setNotification({ type: 'success', message: 'Index deleted successfully.' });

      } catch (error) {
        if (error.response && error.response.status === 404) {
          setIndexedPlaylists((prevPlaylists) =>
            prevPlaylists.filter((p) => p.playlist_id !== selectedPlaylist.id)
          );
          setSelectedPlaylist(null);
          setNotification({ type: 'info', message: 'Index was already deleted.' });
        } else {
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

    if (indexingPlaylists.some(p => p.id === selectedPlaylist.id)) {
      setNotification({ type: 'info', message: 'Playlist is in the indexing queue.' });
      return;
    }

    try {
      setError(null);
      
      // Pass the title to the backend
      await indexPlaylist(selectedPlaylist.id, selectedPlaylist.title, incremental);

      // Add this playlist to the indexing queue
      setIndexingPlaylists((prev) => [
        ...prev,
        {
          id: selectedPlaylist.id,
          title: selectedPlaylist.title,
          status: 'in_progress',
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

  const handleCancelIndexing = async (playlistId, playlistTitle) => {
    if (!window.confirm(`Are you sure you want to cancel indexing "${playlistTitle}"?`)) {
      return;
    }
    
    try {
      await cancelIndexing(playlistId);
      setNotification({ type: 'success', message: 'Indexing cancelled.' });
      // Remove it from the queue
      setIndexingPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
    } catch (error) {
      console.error('Error cancelling indexing:', error);
      setError('Failed to cancel indexing task.');
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setIsAuthenticated(false);
      setSelectedPlaylist(null);
      setIndexedPlaylists([]);
      setIndexingPlaylists([]);
    } catch (error) {
      console.error('Error logging out:', error);
    }
  };

  const handleBackToPlaylists = () => {
    setSelectedPlaylist(null);
  };

  const renderContent = () => {
    if (!selectedPlaylist) {
      return loading ? (
        <LoadingScreen message="Loading playlists..." />
      ) : (
        <>
          <IndexingQueue
            queue={indexingPlaylists}
            onCancel={handleCancelIndexing} // <-- PASS HANDLER
          />
          <PlaylistSelector
            onSelectPlaylist={handleSelectPlaylist}
            indexedPlaylists={indexedPlaylists}
            indexingPlaylists={indexingPlaylists.map(p => p.id)}
          />
        </>
      );
    }
    
    const currentPlaylistStatus = indexingPlaylists.find(
      (p) => p.id === selectedPlaylist.id
    );

    // ==========================================================
    // === THIS IS THE FIX: Create a reusable status bar ========
    // ==========================================================
    const statusBar = currentPlaylistStatus ? (
      <div className="indexing-status">
        <div className="indexing-progress">
          {currentPlaylistStatus.total > 0
            ? `Indexing playlist... (${currentPlaylistStatus.progress}/${currentPlaylistStatus.total})`
            : 'Preparing to index playlist...'}
        </div>
        <button
          className="cancel-indexing-button"
          onClick={() => handleCancelIndexing(currentPlaylistStatus.id, currentPlaylistStatus.title)}
          style={{ marginLeft: '15px' }} // <-- STYLING FIX
        >
          Cancel
        </button>
      </div>
    ) : null;
    // ==========================================================

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

        {/* The old, badly-placed status bar has been removed from here */}

        {indexedPlaylists.some((p) => p.playlist_id === selectedPlaylist.id) ? (
          // --- If playlist IS indexed ---
          <>
            {statusBar} {/* Show status bar on top of search */}
            <SearchInterface
              playlist={selectedPlaylist}
              onDeleteIndex={handleDeleteIndex}
              onReindex={handleIndexPlaylist}
              isIndexing={!!currentPlaylistStatus}
            />
          </>
        ) : (
          // --- If playlist is NOT indexed ---
          <div className="index-container">
            <p>This playlist needs to be indexed before you can search it.</p>
            
            {/* This now shows EITHER the "Start" button OR the status bar.
              This is much cleaner.
            */}
            {!currentPlaylistStatus ? (
              <button
                onClick={(e) => handleIndexPlaylist(true, e)}
                className="index-button"
              >
                Start Indexing
              </button>
            ) : (
              statusBar // <-- Use the new status bar here
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