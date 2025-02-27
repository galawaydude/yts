import React, { useEffect, useState } from 'react';
import { getPlaylists } from '../services/api';

const PlaylistSelector = ({ onSelectPlaylist, indexedPlaylists }) => {
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

  return (
    <div className="playlist-selector">
      <h2>Select a Playlist</h2>
      <div className="playlists-grid">
        {playlists.map(playlist => (
          <div 
            key={playlist.id} 
            className={`playlist-card ${indexedPlaylists.includes(playlist.id) ? 'indexed' : ''}`}
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
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PlaylistSelector; 