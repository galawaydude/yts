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
          Index your YouTube playlists and search video titles, descriptions,
          and full transcripts in seconds.
        </p>
        <button className="google-login-button" onClick={handleLogin}>
          <i className="fab fa-google"></i> Login with Google
        </button>

        <h2 className="search-how-to-title">Powerful Search Capabilities</h2>
        <div className="features-grid">
          <div className="feature-item">
            <i className="fas fa-search"></i>
            <h3>Keyword Search</h3>
            <p>
              Find videos containing all your words. A search for
              <code>python api</code> finds videos with both "python" AND "api".
            </p>
          </div>
          <div className="feature-item">
            <i className="fas fa-quote-right"></i>
            <h3>Phrase Search</h3>
            <p>
              Wrap your search in quotes to find an exact phrase, like
              <code>"django rest framework"</code>.
            </p>
          </div>
          <div className="feature-item">
            <i className="fas fa-project-diagram"></i>
            <h3>Boolean Search</h3>
            <p>
              Use operators like <code>OR</code>, <code>AND</code>, and
              <code>NOT</code> for complex queries, e.g.,
              <code>(flask OR django) NOT api</code>.
            </p>
          </div>
          <div className="feature-item">
            <i className="fas fa-filter"></i>
            <h3>Filter Results</h3>
            <p>
              Narrow your search to specific fields (title, transcript) and
              filter by channel to find what you need.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;