import React from 'react';

const VideoCard = ({ video, query }) => {
  // Format the published date
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };

  // Format view count with commas
  const formatViewCount = (count) => {
    return parseInt(count).toLocaleString();
  };

  // Create a YouTube video URL with timestamp
  const createVideoUrl = (videoId, timestamp) => {
    return `https://www.youtube.com/watch?v=${videoId}&t=${Math.floor(timestamp)}s`;
  };

  // Highlight the matching text
  const renderHighlightedText = (text) => {
    if (!text) return '';
    
    // If there's already highlighted text from the backend
    if (video.matching_segments[0].highlighted_text) {
      return (
        <div dangerouslySetInnerHTML={{ 
          __html: video.matching_segments[0].highlighted_text.replace(
            /<em>(.*?)<\/em>/g, 
            '<span class="highlight">$1</span>'
          )
        }} />
      );
    }
    
    // Fallback if no highlighting from backend
    const regex = new RegExp(`(${query})`, 'gi');
    return (
      <div dangerouslySetInnerHTML={{ 
        __html: text.replace(regex, '<span class="highlight">$1</span>')
      }} />
    );
  };

  const renderHighlightedTitle = () => {
    if (video.highlighted_title) {
      return (
        <div dangerouslySetInnerHTML={{ 
          __html: video.highlighted_title.replace(
            /<em>(.*?)<\/em>/g, 
            '<span class="highlight">$1</span>'
          )
        }} />
      );
    }
    return video.title;
  };

  const renderHighlightedDescription = () => {
    if (video.highlighted_description) {
      return (
        <div className="video-description" dangerouslySetInnerHTML={{ 
          __html: video.highlighted_description.replace(
            /<em>(.*?)<\/em>/g, 
            '<span class="highlight">$1</span>'
          )
        }} />
      );
    }
    if (video.description) {
      return (
        <div className="video-description">
          {video.description.length > 150 
            ? `${video.description.substring(0, 150)}...` 
            : video.description}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="video-card">
      <div className="video-thumbnail">
        <a 
          href={createVideoUrl(video.video_id, video.matching_segments[0]?.start || 0)} 
          target="_blank" 
          rel="noopener noreferrer"
        >
          <img src={video.thumbnail} alt={video.title} />
        </a>
      </div>
      
      <div className="video-details">
        <h3 className="video-title">
          <a 
            href={createVideoUrl(video.video_id, video.matching_segments[0]?.start || 0)} 
            target="_blank" 
            rel="noopener noreferrer"
          >
            {renderHighlightedTitle()}
          </a>
        </h3>
        
        {renderHighlightedDescription()}
        
        <div className="video-meta">
          <span className="channel-name">{video.channel}</span>
          <span className="video-date">{formatDate(video.published_at)}</span>
          <span className="view-count">{formatViewCount(video.view_count)} views</span>
        </div>
        
        <div className="transcript-context">
          {video.matching_segments.map((segment, index) => (
            <div key={index} className="transcript-segment">
              <a 
                href={createVideoUrl(video.video_id, segment.start)} 
                target="_blank" 
                rel="noopener noreferrer"
                className="timestamp"
              >
                {Math.floor(segment.start / 60)}:{(segment.start % 60).toFixed(0).padStart(2, '0')}
              </a>
              <div className="segment-text">
                {renderHighlightedText(segment.text)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default VideoCard; 