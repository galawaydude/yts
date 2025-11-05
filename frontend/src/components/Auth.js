import React, { useEffect, useState } from 'react';
import { getAuthStatus, getLoginUrl } from '../services/api';

const Auth = ({ onAuthChange }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await getAuthStatus();
      setIsAuthenticated(response.data.authenticated);
      onAuthChange(response.data.authenticated);
    } catch (error) {
      console.error('Error checking auth status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    try {
      const response = await getLoginUrl();
      window.location.href = response.data.auth_url;
    } catch (error) {
      console.error('Error getting login URL:', error);
    }
  };

  if (loading) {
    return <div className="loading">Loading authentication status...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <h1>YouTube Transcript Search</h1>
        <p>Search for words and phrases in your YouTube playlists</p>
        <button className="login-button" onClick={handleLogin}>
          Login with Google
        </button>
      </div>
    );
  }

  return null;
};

export default Auth; 