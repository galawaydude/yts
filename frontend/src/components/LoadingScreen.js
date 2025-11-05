import React from 'react';

const LoadingScreen = ({ message }) => {
  return (
    <div className="loading-screen">
      <div className="spinner"></div>
      <p>{message || 'Loading...'}</p>
    </div>
  );
};

export default LoadingScreen; 