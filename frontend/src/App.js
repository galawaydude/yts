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
  cancelIndexing,
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

  const checkAllIndexingStatuses = useCallback(async () => {
    if (indexingPlaylists.length === 0) return;

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

              if (status.indexed_data) {
                completedPlaylistsData.push(status.indexed_data);
              }

            } else {
              setNotification({ type: 'error', message: `Failed to index ${playlist.title}: ${status.error}` });
            }
            return null;
          } else if (status.status === 'not_started') {
            return null;
          } else {
            return {
              ...playlist,
              status: status.status,
              progress: status.progress,
              total: status.total,
              // --- FIX: Save the message from backend ---
              message: status.message 
            };
          }
        } catch (error) {
          console.error(`Error checking status for ${playlist.id}:`, error);
          return playlist;
        }
      })
    );

    setIndexingPlaylists(newIndexingPlaylists.filter(Boolean));

    if (completedPlaylistsData.length > 0) {
      setIndexedPlaylists((prev) => {
        let newList = [...prev];
        completedPlaylistsData.forEach(newPlaylist => {
          const existingIndex = newList.findIndex(p => p.playlist_id === newPlaylist.playlist_id);
          if (existingIndex !== -1) {
            newList[existingIndex] = newPlaylist;
          } else {
            newList.unshift(newPlaylist);
          }
        });
        return newList;
      });
    }
    
    if (completedPlaylistsData.length > 0) {
        setTimeout(() => {
            setNotification(null);
        }, 5000);
    }

  }, [indexingPlaylists]);

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

  const handleIndexPlaylist = async (incremental = true, event = null, force = false) => {
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    if (!selectedPlaylist) return;

    // If forcing, we don't check if it's already in queue
    if (!force && indexingPlaylists.some(p => p.id === selectedPlaylist.id)) {
      setNotification({ type: 'info', message: 'Playlist is in the indexing queue.' });
      return;
    }

    try {
      setError(null);
      
      // --- NEW: Pass 'force' param ---
      await indexPlaylist(selectedPlaylist.id, selectedPlaylist.title, incremental, force);

      setIndexingPlaylists((prev) => {
        // Remove if exists (for force restart)
        const filtered = prev.filter(p => p.id !== selectedPlaylist.id);
        return [
            ...filtered,
            {
            id: selectedPlaylist.id,
            title: selectedPlaylist.title,
            status: 'starting',
            message: 'Requesting start...', // Initial UI feedback
            progress: 0,
            total: selectedPlaylist.videoCount,
            },
        ];
      });
      
      setNotification({ type: 'success', message: 'Added to indexing queue.' });

    } catch (error) {
        // --- NEW: Handle 409 Conflict by offering Force Restart ---
        if (error.response && error.response.status === 409) {
            if (window.confirm("Indexing is already running or stuck. Do you want to FORCE restart it?")) {
                handleIndexPlaylist(incremental, null, true); // Call recursively with force=true
                return;
            }
        }
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
            onCancel={handleCancelIndexing}
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

    const statusBar = currentPlaylistStatus ? (
      <div className="indexing-status">
        <div className="indexing-progress">
          {/* --- FIX: Use backend message --- */}
          {currentPlaylistStatus.message || (currentPlaylistStatus.total > 0
            ? `Indexing... (${currentPlaylistStatus.progress}/${currentPlaylistStatus.total})`
            : 'Initializing...')}
        </div>
        <button
          className="cancel-indexing-button"
          onClick={() => handleCancelIndexing(currentPlaylistStatus.id, currentPlaylistStatus.title)}
          style={{ marginLeft: '15px', background: 'transparent', border: '1px solid currentColor', padding: '5px 10px', fontSize: '14px' }}
        >
          Cancel
        </button>
      </div>
    ) : null;

    return (
      <div className="playlist-content">
        <button className="back-button" onClick={handleBackToPlaylists}>
          ← Back to Playlists
        </button>

        {indexedPlaylists.some((p) => p.playlist_id === selectedPlaylist.id) ? (
          <>
            {statusBar}
            <SearchInterface
              playlist={selectedPlaylist}
              onDeleteIndex={handleDeleteIndex}
              onReindex={handleIndexPlaylist}
              isIndexing={!!currentPlaylistStatus}
            />
          </>
        ) : (
          <div className="index-container">
            <p>This playlist needs to be indexed before you can search it.</p>
            {!currentPlaylistStatus ? (
              <button
                onClick={(e) => handleIndexPlaylist(true, e)}
                className="index-button"
              >
                Start Indexing
              </button>
            ) : (
              statusBar
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