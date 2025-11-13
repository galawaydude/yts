import React, { useState } from 'react';

const IndexingQueue = ({ queue, onCancel }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (queue.length === 0) {
    return null; 
  }

  const totalProgress = queue.reduce((acc, p) => acc + p.progress, 0);
  const totalItems = queue.reduce((acc, p) => acc + p.total, 0);
  const overallPercent = totalItems > 0 ? (totalProgress / totalItems) * 100 : 0;

  return (
    <div className="indexing-queue-container">
      <div
        className="indexing-queue-header"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="queue-header-left">
          <h3>
            Currently Indexing ({queue.length} Playlist
            {queue.length > 1 ? 's' : ''})
          </h3>
          {isCollapsed && (
            <div className="queue-overall-progress">
              <div
                className="queue-item-progress-fill"
                style={{ width: `${overallPercent}%` }}
              ></div>
            </div>
          )}
        </div>
        <button className="queue-toggle-button">
          {isCollapsed ? 'Show' : 'Hide'}
        </button>
      </div>

      {!isCollapsed && (
        <div className="queue-items-container">
          {queue.map((playlist) => (
            <div key={playlist.id} className="indexing-queue-item">
              <span className="queue-item-title">{playlist.title}</span>
              <div className="queue-item-progress-bar">
                <div
                  className="queue-item-progress-fill"
                  style={{
                    width: `${
                      playlist.total > 0
                        ? (playlist.progress / playlist.total) * 100
                        : (playlist.status === 'starting' ? 5 : 0) // Show a tiny bar for 'starting'
                    }%`,
                  }}
                ></div>
              </div>
              <span className="queue-item-status">
                {/* --- FIX: Use backend message if available --- */}
                {playlist.message || (playlist.total > 0
                  ? `(${playlist.progress}/${playlist.total})`
                  : 'Starting...')}
              </span>
              
              <button
                className="queue-item-cancel"
                title="Cancel Indexing"
                onClick={(e) => {
                  e.stopPropagation(); 
                  onCancel(playlist.id, playlist.title);
                }}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default IndexingQueue;