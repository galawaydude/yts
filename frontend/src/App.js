import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import PlaylistSelector from './components/PlaylistSelector';
import SearchInterface from './components/SearchInterface';
import LoadingScreen from './components/LoadingScreen';
import LandingPage from './components/LandingPage';
import { indexPlaylist, logout, getIndexedPlaylists, deletePlaylistIndex, getIndexingStatus, getAuthStatus } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingProgress, setIndexingProgress] = useState(null);
  const [indexedPlaylists, setIndexedPlaylists] = useState([]);
  const [indexingPlaylists, setIndexingPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState(null);

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
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchIndexedPlaylists();
    }
  }, [isAuthenticated]);

  const fetchIndexedPlaylists = async () => {
    try {
      const response = await getIndexedPlaylists();
      setIndexedPlaylists(response.data.indexed_playlists || []);
    } catch (error) {
      console.error('Error fetching indexed playlists:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkIndexingStatus = useCallback(async () => {
    if (!selectedPlaylist || !isIndexing) return;
    
    try {
      const response = await getIndexingStatus(selectedPlaylist.id);
      const status = response.data;
      
      if (status.status === 'completed' || status.status === 'failed') {
        setIsIndexing(false);
        setIndexingProgress(null);
        
        // Remove this playlist from the list of currently indexing playlists
        setIndexingPlaylists(prev => prev.filter(id => id !== selectedPlaylist.id));
        
        // Refresh the list of indexed playlists
        await fetchIndexedPlaylists();
        
        // Show notification based on indexing results
        if (status.status === 'completed') {
          if (status.incremental) {
            if (status.new_videos_count > 0) {
              setNotification({
                type: 'success',
                message: `Added ${status.new_videos_count} new videos to the index.`
              });
            } else {
              setNotification({
                type: 'info',
                message: 'No new videos detected in this playlist.'
              });
            }
          } else {
            setNotification({
              type: 'success',
              message: `Successfully indexed ${status.success_count} videos.`
            });
          }
          
          // Clear notification after 5 seconds
          setTimeout(() => {
            setNotification(null);
          }, 5000);
        } else if (status.status === 'failed') {
          setError(status.error || 'Indexing failed');
        }
      } else if (status.status === 'in_progress') {
        setIndexingProgress({
          current: status.progress,
          total: status.total
        });
      }
    } catch (error) {
      console.error('Error checking indexing status:', error);
    }
  }, [selectedPlaylist, isIndexing, fetchIndexedPlaylists]);

  useEffect(() => {
    if (isIndexing) {
      const interval = setInterval(checkIndexingStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [isIndexing, checkIndexingStatus]);

  // Check indexing status for all playlists that are being indexed
  const checkAllIndexingStatuses = useCallback(async () => {
    if (indexingPlaylists.length === 0) return;
    
    // Make a copy to avoid modifying the array while iterating
    const playlistsToCheck = [...indexingPlaylists];
    
    for (const playlistId of playlistsToCheck) {
      try {
        const response = await getIndexingStatus(playlistId);
        const status = response.data;
        
        if (status.status === 'completed' || status.status === 'failed') {
          // Remove this playlist from the list of currently indexing playlists
          setIndexingPlaylists(prev => prev.filter(id => id !== playlistId));
          
          // Refresh the list of indexed playlists
          await fetchIndexedPlaylists();
        }
      } catch (error) {
        console.error(`Error checking indexing status for playlist ${playlistId}:`, error);
      }
    }
  }, [indexingPlaylists, fetchIndexedPlaylists]);

  // Check indexing status periodically when there are playlists being indexed
  useEffect(() => {
    if (indexingPlaylists.length === 0) return;
    
    const interval = setInterval(() => {
      checkAllIndexingStatuses();
    }, 3000); // Check every 3 seconds
    
    return () => clearInterval(interval);
  }, [indexingPlaylists, checkAllIndexingStatuses]);

  const handleSelectPlaylist = (playlist) => {
    const isIndexed = indexedPlaylists.some(
      indexed => indexed.playlist_id === playlist.id
    );
    
    setSelectedPlaylist({
      ...playlist,
      isIndexed
    });
  };

  const handleDeleteIndex = async () => {
    if (!selectedPlaylist) return;
    
    if (window.confirm(`Are you sure you want to delete the index for "${selectedPlaylist.title}"?`)) {
      try {
        setError(null);
        await deletePlaylistIndex(selectedPlaylist.id);
        setIndexedPlaylists(prevPlaylists => 
          prevPlaylists.filter(p => p.playlist_id !== selectedPlaylist.id)
        );
        setSelectedPlaylist(null);
      } catch (error) {
        console.error('Error deleting index:', error);
        setError('Failed to delete index');
      }
    }
  };

  const handleIndexPlaylist = async (incremental = true, event = null) => {
    // If an event was passed, ignore it to avoid circular JSON issues
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    
    if (!selectedPlaylist) return;
    
    try {
      setError(null);
      setIsIndexing(true);
      
      // Add this playlist to the list of currently indexing playlists
      setIndexingPlaylists(prev => [...prev, selectedPlaylist.id]);
      
      // Only pass the playlist ID and incremental flag to avoid circular references
      const playlistId = selectedPlaylist.id;
      await indexPlaylist(playlistId, incremental);
    } catch (error) {
      console.error('Error indexing playlist:', error);
      setError('Failed to start indexing');
      setIsIndexing(false);
      
      // Remove this playlist from the list of currently indexing playlists
      setIndexingPlaylists(prev => prev.filter(id => id !== selectedPlaylist.id));
    }
  };

  const handleFullReindex = async (event = null) => {
    // If an event was passed, ignore it to avoid circular JSON issues
    if (event && event.preventDefault) {
      event.preventDefault();
    }
    
    try {
      setError(null);
      setIsIndexing(true);
      
      // Add this playlist to the list of currently indexing playlists
      setIndexingPlaylists(prev => [...prev, selectedPlaylist.id]);
      
      // Only pass the playlist ID and incremental flag to avoid circular references
      const playlistId = selectedPlaylist.id;
      await indexPlaylist(playlistId, false); // false for full reindex
    } catch (error) {
      console.error('Error reindexing playlist:', error);
      setError('Failed to start reindexing');
      setIsIndexing(false);
      
      // Remove this playlist from the list of currently indexing playlists
      setIndexingPlaylists(prev => prev.filter(id => id !== selectedPlaylist.id));
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
    // If we're currently indexing, we want to keep that state
    // but we need to clear the selected playlist
    if (isIndexing) {
      // Only clear the selected playlist, but keep isIndexing true
      setSelectedPlaylist(null);
    } else {
      // Normal case - just go back to playlist selection
      setSelectedPlaylist(null);
    }
  };

  const renderContent = () => {
    if (!selectedPlaylist) {
      return loading ? (
        <LoadingScreen message="Loading playlists..." />
      ) : (
        <PlaylistSelector 
          onSelectPlaylist={handleSelectPlaylist} 
          indexedPlaylists={indexedPlaylists}
          indexingPlaylists={indexingPlaylists}
        />
      );
    }

    return (
      <div className="playlist-content">
        <div className="playlist-header">
          <h2>{selectedPlaylist.title}</h2>
          <div className="playlist-actions">
            <button 
              className="back-button"
              onClick={handleBackToPlaylists}
            >
              Back to Playlists
            </button>
          </div>
        </div>
        
        {isIndexing && (
          <div className="indexing-status">
            <div className="indexing-progress">
              {indexingProgress 
                ? `Indexing playlist... (${indexingProgress.current}/${indexingProgress.total})`
                : "Preparing to index playlist..."}
            </div>
          </div>
        )}
        
        {selectedPlaylist && indexedPlaylists.some(p => p.playlist_id === selectedPlaylist.id) ? (
            <SearchInterface 
                playlist={selectedPlaylist}
                onDeleteIndex={handleDeleteIndex}
                onReindex={handleIndexPlaylist}
            />
        ) : (
            <div className="index-container">
                <p>This playlist needs to be indexed before you can search it.</p>
                {!indexingPlaylists.includes(selectedPlaylist.id) ? (
                    <button onClick={(e) => handleIndexPlaylist(true, e)} className="index-button">
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
          <button onClick={() => setNotification(null)}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

export default App;