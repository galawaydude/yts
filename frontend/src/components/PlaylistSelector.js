import React, { useEffect, useState } from 'react';
import { getPlaylists } from '../services/api';

const PlaylistSelector = ({ onSelectPlaylist, indexedPlaylists, indexingPlaylists }) => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPlaylists();
  }, []);

  const fetchPlaylists = async () => {
    try {
      setLoading(true);
      const response = await getPlaylists();
      setPlaylists(response.data.playlists);
      setError(null);
    } catch (error) {
      console.error('Error fetching playlists:', error);
      setError('Failed to load playlists. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const isPlaylistIndexed = (playlistId) => {
    return indexedPlaylists.some(indexed => indexed.playlist_id === playlistId);
  };

  const isPlaylistIndexing = (playlistId) => {
    return indexingPlaylists && indexingPlaylists.includes(playlistId);
  };

  // Separate playlists into own and saved
  const ownPlaylists = playlists.filter(playlist => playlist.isOwn);
  const savedPlaylists = playlists.filter(playlist => !playlist.isOwn);

  if (loading) {
    return <div className="loading">Loading your playlists...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>{error}</p>
        <button onClick={fetchPlaylists}>Retry</button>
      </div>
    );
  }

  const renderPlaylistCard = (playlist) => (
    <div 
      key={playlist.id} 
      className={`playlist-card ${isPlaylistIndexed(playlist.id) ? 'indexed' : ''} ${isPlaylistIndexing(playlist.id) ? 'indexing' : ''}`}
      onClick={() => onSelectPlaylist(playlist)}
    >
      <div className="playlist-thumbnail">
        {playlist.thumbnail ? (
          <img src={playlist.thumbnail} alt={playlist.title} />
        ) : (
          <div className="no-thumbnail">No Thumbnail</div>
        )}
      </div>
      <div className="playlist-info">
        <h3>{playlist.title}</h3>
        <p>{playlist.videoCount} videos</p>
        {isPlaylistIndexing(playlist.id) ? (
          <span className="indexing-badge">Indexing...</span>
        ) : isPlaylistIndexed(playlist.id) && (
          <span className="indexed-badge">Indexed</span>
        )}
      </div>
    </div>
  );

  return (
    <div className="playlist-selector">
      <h2>Select a Playlist</h2>
      
      <div className="playlists-section">
        <h3>Your Playlists</h3>
        <div className="playlists-grid">
          {ownPlaylists.map(renderPlaylistCard)}
        </div>
      </div>
      
      {savedPlaylists.length > 0 && (
        <div className="playlists-section">
          <h3>Saved Playlists</h3>
          <div className="playlists-grid">
            {savedPlaylists.map(renderPlaylistCard)}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlaylistSelector;