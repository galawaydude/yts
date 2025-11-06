import React from 'react';
import { getLoginUrl } from '../services/api';
import '../styles/LandingPage.css';

const LandingPage = () => {
  const handleLogin = async () => {
    try {
      const response = await getLoginUrl();
      window.location.href = response.data.auth_url;
    } catch (error) {
      console.error('Error getting login URL:', error);
    }
  };

  return (
    <div className="landing-container">
      <div className="landing-content">
        <div className="landing-logo">
          <i className="fas fa-play-circle"></i>
        </div>
        <h1 className="landing-title">YouTube Playlist Search</h1>
        <p className="landing-description">
          Index and search your YouTube playlists with advanced search capabilities.
          Find any video by content, transcript, or description in seconds.
        </p>
        <div className="features-grid">
          <div className="feature-item">
            <i className="fas fa-search"></i>
            <h3>Full-Text Search</h3>
            <p>Search across video titles, descriptions, and transcripts</p>
          </div>
          <div className="feature-item">
            <i className="fas fa-list"></i>
            <p>Index your playlists for lightning-fast search results</p>
            <h3>Playlist Indexing</h3>
          </div>
          <div className="feature-item">
            <i className="fas fa-filter"></i>
            <h3>Advanced Filtering</h3>
            <p>Filter results by channel, date, and more</p>
          </div>
          <div className="feature-item">
            <i className="fas fa-download"></i>
            <h3>Export Data</h3>
            <p>Export your playlist data in JSON format</p>
          </div>
        </div>
        <button className="google-login-button" onClick={handleLogin}>
          <i className="fab fa-google"></i> Login with Google
        </button>
      </div>
    </div>
  );
};

export default LandingPage;
