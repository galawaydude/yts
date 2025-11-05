import React from 'react';
import DOMPurify from 'dompurify';

// Helper function to format timestamp (e.g., 125.5 -> 2:05)
const formatTimestamp = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

// Helper function to safely render highlighted HTML
const createMarkup = (html) => {
  if (!html) return { __html: '' };
  // Sanitize the HTML to prevent XSS attacks
  return { __html: DOMPurify.sanitize(html) };
};

const VideoCard = ({ video }) => {
  // Determine the primary link URL (first matching segment or start of video)
  const primaryTimestamp = video.matching_segments?.[0]?.start || 0;
  const videoUrl = `https://youtube.com/watch?v=${video.id}&t=${Math.floor(primaryTimestamp)}`;

  return (
    <div className="video-card">
      <div className="video-thumbnail-container">
        <a href={videoUrl} target="_blank" rel="noopener noreferrer">
          <img
            src={video.thumbnail}
            alt={video.title}
            className="video-thumbnail"
          />
        </a>
      </div>
      <div className="video-info">
        <h3 className="video-title">
          <a
            href={videoUrl}
            target="_blank"
            rel="noopener noreferrer"
            dangerouslySetInnerHTML={createMarkup(video.highlighted_title)}
          />
        </h3>

        <div className="video-meta">
          <span className="channel-name">{video.channel_title}</span>
          <span className="bullet">•</span>
          <span className="view-count">
            {parseInt(video.view_count).toLocaleString()} views
          </span>
          <span className="bullet">•</span>
          <span className="publish-date">
            {new Date(video.published_at).toLocaleDateString()}
          </span>
        </div>

        {video.highlighted_description && (
          <div className="video-description">
            <div
              dangerouslySetInnerHTML={createMarkup(
                video.highlighted_description
              )}
            />
          </div>
        )}

        {video.matching_segments && video.matching_segments.length > 0 && (
          <div className="video-transcript-matches">
            {video.matching_segments.map((segment, i) => (
              <div key={i} className="video-transcript-segment">
                <div
                  dangerouslySetInnerHTML={createMarkup(
                    segment.highlighted_text
                  )}
                />
                <a
                  href={`https://youtube.com/watch?v=${video.id}&t=${Math.floor(
                    segment.start
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="timestamp-link"
                >
                  {formatTimestamp(segment.start)}
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoCard;