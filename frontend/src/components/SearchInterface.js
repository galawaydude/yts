import React, { useState, useEffect } from 'react';
import { searchPlaylist } from '../services/api';
import VideoResults from './VideoResults';
import LoadingScreen from './LoadingScreen';

const SearchInterface = ({ playlist, onDeleteIndex, onReindex }) => {
  const [query, setQuery] = useState('');
  const [searchFields, setSearchFields] = useState({
    title: true,
    description: true,
    transcript: true
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const resultsPerPage = 10;

  const handleSearch = async (e, page = 1) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const selectedFields = Object.entries(searchFields)
        .filter(([_, value]) => value)
        .map(([key]) => key);

      const response = await searchPlaylist(playlist.id, query, selectedFields, page, resultsPerPage);
      setResults(response.data.results || []);
      setTotalResults(response.data.total || 0);
      setCurrentPage(page);
      setSearchPerformed(true);
    } catch (error) {
      console.error('Search error:', error);
      setError(error.response?.data?.error || 'Failed to perform search');
    } finally {
      setLoading(false);
    }
  };

  const handleFieldToggle = (field) => {
    setSearchFields(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
  };

  const totalPages = Math.ceil(totalResults / resultsPerPage);

  const handlePageChange = (page) => {
    if (page < 1 || page > totalPages) return;
    handleSearch(null, page);
  };

  return (
    <div className="search-interface">
      <div className="search-header">
        <h2>{playlist.title}</h2>
        <div className="playlist-actions">
          <button onClick={onReindex} className="reindex-button">
            Reindex Playlist
          </button>
          <button onClick={onDeleteIndex} className="delete-index-button">
            Delete Index
          </button>
        </div>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <div className="search-input-container">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in playlist..."
            className="search-input"
          />
          <button type="submit" className="search-button" disabled={loading}>
            Search
          </button>
        </div>

        <div className="search-options">
          <label>
            <input
              type="checkbox"
              checked={searchFields.title}
              onChange={() => handleFieldToggle('title')}
            />
            Title
          </label>
          <label>
            <input
              type="checkbox"
              checked={searchFields.description}
              onChange={() => handleFieldToggle('description')}
            />
            Description
          </label>
          <label>
            <input
              type="checkbox"
              checked={searchFields.transcript}
              onChange={() => handleFieldToggle('transcript')}
            />
            Transcript
          </label>
        </div>
      </form>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {loading ? (
        <LoadingScreen message="Searching..." />
      ) : searchPerformed ? (
        <>
          {results.length > 0 ? (
            <>
              <VideoResults results={results} query={query} />
              {totalPages > 1 && (
                <div className="pagination">
                  <button 
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="pagination-button"
                  >
                    Previous
                  </button>
                  <span className="pagination-info">
                    Page {currentPage} of {totalPages}
                  </span>
                  <button 
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="pagination-button"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="no-results">
              No videos found matching your search.
            </div>
          )}
        </>
      ) : null}
    </div>
  );
};

export default SearchInterface;