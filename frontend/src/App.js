import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Auth from './components/Auth';
import PlaylistSelector from './components/PlaylistSelector';
import SearchInterface from './components/SearchInterface';
import LoadingScreen from './components/LoadingScreen';
import { indexPlaylist, logout, getIndexedPlaylists, deletePlaylistIndex, getIndexingStatus } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingProgress, setIndexingProgress] = useState(null);
  const [indexedPlaylists, setIndexedPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

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
      
      if (status.status === 'completed') {
        setIsIndexing(false);
        setIndexingProgress(null);
        await fetchIndexedPlaylists();
        setSelectedPlaylist(prev => ({
          ...prev,
          isIndexed: true
        }));
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
  }, [selectedPlaylist, isIndexing]);

  useEffect(() => {
    if (isIndexing) {
      const interval = setInterval(checkIndexingStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [isIndexing, checkIndexingStatus]);

  const handleSelectPlaylist = (playlist) => {
    const isIndexed = indexedPlaylists.some(
      indexed => indexed.playlist_id === playlist.id
    );
    
    setSelectedPlaylist({
      ...playlist,
      isIndexed
    });
  };

  const handleIndexPlaylist = async () => {
    if (!selectedPlaylist) return;
    
    try {
      setError(null);
      setIsIndexing(true);
      await indexPlaylist(selectedPlaylist.id);
    } catch (error) {
      console.error('Error indexing playlist:', error);
      setError('Failed to start indexing');
      setIsIndexing(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setIsAuthenticated(false);
      setSelectedPlaylist(null);
      setIndexedPlaylists([]);
    } catch (error) {
      console.error('Error logging out:', error);
    }
  };

  const handleDeleteIndex = async () => {
    if (!selectedPlaylist) return;
    
    try {
      await deletePlaylistIndex(selectedPlaylist.id);
      setSelectedPlaylist(null);
      await fetchIndexedPlaylists();
    } catch (error) {
      console.error('Error deleting index:', error);
      setError('Failed to delete index');
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
        />
      );
    }

    if (isIndexing) {
      return (
        <LoadingScreen 
          message={
            indexingProgress 
              ? `Indexing playlist... (${indexingProgress.current}/${indexingProgress.total})`
              : "Preparing to index playlist..."
          } 
        />
      );
    }

    if (!selectedPlaylist.isIndexed) {
      return (
        <div className="index-container">
          <div className="back-button-container">
            <button onClick={() => setSelectedPlaylist(null)}>
              ← Back to Playlists
            </button>
          </div>
          <h2>{selectedPlaylist.title}</h2>
          <p>This playlist needs to be indexed before you can search it.</p>
          <button onClick={handleIndexPlaylist} className="index-button">
            Start Indexing
          </button>
        </div>
      );
    }

    return (
      <SearchInterface 
        playlist={selectedPlaylist}
        onDeleteIndex={handleDeleteIndex}
        onReindex={handleIndexPlaylist}
      />
    );
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>YouTube Transcript Search</h1>
        {isAuthenticated && (
          <button onClick={handleLogout} className="logout-button">
            Logout
          </button>
        )}
      </header>

      <Auth onAuthChange={setIsAuthenticated} />

      {isAuthenticated && renderContent()}

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

export default App; 