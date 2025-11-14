import React from 'react';

const ReadmeModal = ({ onClose }) => {
  return (
    <div className="modal-backdrop">
      <div className="modal-content">
        <h2 className="modal-title">READ_ME.txt</h2>
        
        <div className="modal-body">
          <p>Welcome, Operator.</p>
          <p>
            [This is placeholder text. You can explain how your application's 
            backend is built for scale here, mentioning the concurrent workers.]
          </p>
          
          <h3 className="modal-subtitle">The Bottleneck: Proxy Bandwidth</h3>
          <p>
            [This is placeholder text. Explain the residential proxies, why 
            they are necessary for bypassing IP blocks, and that they are 
            billed by bandwidth.]
          </p>
          
          <h3 className="modal-subtitle">What This Means For You</h3>
          <p>
            <span className="text-highlight-red">
              [Placeholder: Explain the consequences of indexing large 
              playlists, e.g., how much data it consumes.]
            </span>
          </p>
          <p>
            <span className="text-highlight-red">
              [Placeholder: Explain what the "402 Payment Required" error 
              means (i.e., the bandwidth limit is hit).]
            </span>
          </p>
        </div>

        <button className="modal-close-button" onClick={onClose}>
          [ I understand ]
        </button>
      </div>
    </div>
  );
};

export default ReadmeModal;