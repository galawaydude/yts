import React, { useState, useEffect, useCallback } from 'react';
import Auth from './components/Auth';
import PlaylistSelector from './components/PlaylistSelector';
import SearchInterface from './components/SearchInterface';
import LoadingScreen from './components/LoadingScreen';
import { indexPlaylist, logout, getIndexedPlaylists, deletePlaylistIndex, getIndexingStatus } from './services/api';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingProgress, setIndexingProgress] = useState(null);
  const [indexedPlaylists, setIndexedPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [showSearch, setShowSearch] = useState(false);

  const fetchIndexedPlaylists = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const response = await getIndexedPlaylists();
      setIndexedPlaylists(response.data.indexed_playlists);
    } catch (error) {
      console.error('Error fetching indexed playlists:', error);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchIndexedPlaylists();
    const interval = setInterval(fetchIndexedPlaylists, 5000);
    return () => clearInterval(interval);
  }, [fetchIndexedPlaylists]);

  const checkIndexingStatus = useCallback(async () => {
    if (!selectedPlaylist || !isIndexing) return;
    
    try {
      const response = await getIndexingStatus(selectedPlaylist.id);
      const status = response.data;
      
      if (status.status === 'completed') {
        setIsIndexing(false);
        setIndexingProgress(null);
        await fetchIndexedPlaylists();
        setShowSearch(true);
      } else if (status.status === 'failed') {
        setIsIndexing(false);
        setIndexingProgress(null);
        setError(status.error || 'Indexing failed');
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

  const handleSelectPlaylist = (playlist) => {
    setSelectedPlaylist(playlist);
    setError(null);
    setShowSearch(isPlaylistIndexed(playlist.id));
  };

  const handleIndexPlaylist = async () => {
    try {
      setError(null);
      setIsIndexing(true);
      setShowSearch(false);
      await indexPlaylist(selectedPlaylist.id);
    } catch (error) {
      console.error('Error indexing playlist:', error);
      setError('Failed to start indexing');
      setIsIndexing(false);
    }
  };

  const handleDeleteIndex = async () => {
    try {
      setError(null);
      await deletePlaylistIndex(selectedPlaylist.id);
      await fetchIndexedPlaylists();
      setShowSearch(false);
    } catch (error) {
      console.error('Error deleting index:', error);
      setError('Failed to delete index');
    }
  };

  const isPlaylistIndexed = useCallback((playlistId) => {
    return indexedPlaylists.some(id => id.toLowerCase() === playlistId.toLowerCase());
  }, [indexedPlaylists]);

  const handleBackToPlaylists = () => {
    setSelectedPlaylist(null);
    setError(null);
    setIsIndexing(false);
    setIndexingProgress(null);
    setShowSearch(false);
  };

  return (
    <div className="app">
      {!isAuthenticated ? (
        <Auth onAuthChange={setIsAuthenticated} />
      ) : (
        <>
          <header className="app-header">
            <h1>YouTube Transcript Search</h1>
            <button className="logout-button" onClick={logout}>
              Logout
            </button>
          </header>

          {error && (
            <div className="error-message">
              {error}
              <button onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}

          {!selectedPlaylist ? (
            <PlaylistSelector 
              onSelectPlaylist={handleSelectPlaylist} 
              indexedPlaylists={indexedPlaylists}
            />
          ) : (
            <div className="playlist-view">
              <div className="back-button-container">
                <button onClick={handleBackToPlaylists}>
                  ← Back to Playlists
                </button>
              </div>

              {isIndexing ? (
                <LoadingScreen 
                  message={
                    indexingProgress 
                      ? `Indexing playlist... (${indexingProgress.current}/${indexingProgress.total})`
                      : "Preparing to index playlist..."
                  } 
                />
              ) : showSearch ? (
                <SearchInterface 
                  key={selectedPlaylist.id}
                  playlist={selectedPlaylist}
                  onDeleteIndex={handleDeleteIndex}
                  onReindex={handleIndexPlaylist}
                />
              ) : (
                <div className="index-container">
                  <h2>Index Playlist</h2>
                  <p>This playlist needs to be indexed before you can search it.</p>
                  <button onClick={handleIndexPlaylist} disabled={isIndexing}>
                    Start Indexing
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App; 