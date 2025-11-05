import React, { useState } from 'react';

const IndexingQueue = ({ queue }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (queue.length === 0) {
    return null; // Don't show anything if the queue is empty
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
          {/* Show a simple overall progress bar when collapsed */}
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

      {/* Collapsible section */}
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
                        : 0
                    }%`,
                  }}
                ></div>
              </div>
              <span className="queue-item-status">
                {playlist.total > 0
                  ? `(${playlist.progress}/${playlist.total})`
                  : 'Starting...'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default IndexingQueue;