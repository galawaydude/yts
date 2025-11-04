import React from 'react';
import VideoCard from './VideoCard'; // Import the refactored VideoCard

const VideoResults = ({ results }) => {
  return (
    <div className="video-results">
      {results.map((video, index) => (
        <VideoCard
          // Use a unique key for each item
          key={`${video.id}-${index}`}
          video={video}
        />
      ))}
    </div>
  );
};

export default VideoResults;