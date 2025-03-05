import React, { useState, useEffect } from 'react';
import { searchPlaylist, exportPlaylistData, getIndexingStatus } from '../services/api';
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
  const [selectedChannels, setSelectedChannels] = useState([]);
  const [channelsInResults, setChannelsInResults] = useState([]);
  const [showChannelFilter, setShowChannelFilter] = useState(false);
  const [pendingChannelSearch, setPendingChannelSearch] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const resultsPerPage = 10;
  const [pageInput, setPageInput] = useState('');

  // Check if the playlist is currently being indexed
  useEffect(() => {
    const checkIndexingStatus = async () => {
      try {
        const response = await getIndexingStatus(playlist.id);
        setIsIndexing(response.data.status === 'in_progress');
      } catch (error) {
        console.error('Error checking indexing status:', error);
      }
    };

    checkIndexingStatus();
    const interval = setInterval(checkIndexingStatus, 5000);
    return () => clearInterval(interval);
  }, [playlist.id]);

  const handleSearch = async (e, page = 1, channelFilters = selectedChannels) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const selectedFields = Object.entries(searchFields)
        .filter(([_, value]) => value)
        .map(([key]) => key);

      const response = await searchPlaylist(
        playlist.id, 
        query, 
        selectedFields, 
        page, 
        resultsPerPage, 
        channelFilters
      );
      
      setResults(response.data.results || []);
      setTotalResults(response.data.total || 0);
      setCurrentPage(page);
      setSearchPerformed(true);
      
      // Set channels from search results
      setChannelsInResults(response.data.channels || []);
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

  const handleChannelToggle = (channelName) => {
    setSelectedChannels(prev => {
      const newChannels = prev.includes(channelName)
        ? prev.filter(c => c !== channelName) // Remove channel if already selected
        : [...prev, channelName];             // Add channel if not selected
      
      // Set flag that we have pending channel changes
      setPendingChannelSearch(true);
      
      return newChannels;
    });
  };

  const clearChannelFilters = () => {
    setSelectedChannels([]);
    handleSearch(null, 1, []);
    setPendingChannelSearch(false);
  };

  const applyChannelFilters = () => {
    handleSearch(null, 1, selectedChannels);
    setPendingChannelSearch(false);
  };

  const handleExportPlaylist = () => {
    exportPlaylistData(playlist.id);
  };

  const handleIncrementalReindex = (e) => {
    // Pass the event object to onReindex so it can be properly handled
    onReindex(true, e);
  };

  const handleFullReindex = (e) => {
    // Pass the event object to onReindex so it can be properly handled
    e.preventDefault();
    if (window.confirm("This will reindex the entire playlist from scratch. Continue?")) {
      onReindex(false, e);
    }
  };

  const totalPages = Math.ceil(totalResults / resultsPerPage);

  const handlePageChange = (page) => {
    if (page < 1 || page > totalPages) return;
    handleSearch(null, page);
  };

  return (
    <div className="search-interface">
      <div className="playlist-header">
        <h2>{playlist.title}</h2>
        <div className="playlist-actions">
          <button onClick={handleExportPlaylist} className="export-button">
            Export Data
          </button>
          {!isIndexing && (
            <>
              <button onClick={handleIncrementalReindex} className="reindex-button">
                Update Index
              </button>
              <button onClick={handleFullReindex} className="full-reindex-button">
                Full Reindex
              </button>
              <button onClick={onDeleteIndex} className="delete-index-button">
                Delete Index
              </button>
            </>
          )}
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
          <div className="search-fields">
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
          {/* Search Results Count */}
          <div className="results-count-container">
            <p className="results-count">
              {totalResults === 0 ? 'No results found' : 
               `Found ${totalResults} video${totalResults === 1 ? '' : 's'}`}
            </p>
          </div>

          {results.length > 0 ? (
            <>
              {/* Channel filter section - displayed after search results are shown */}
              {channelsInResults.length > 0 && (
                <div className="channel-filter-container">
                  <div className="channel-filter-header">
                    <h3>Filter by Channel</h3>
                    <div className="channel-filter-actions">
                      {pendingChannelSearch && (
                        <button 
                          type="button" 
                          className="apply-filters-button"
                          onClick={applyChannelFilters}
                        >
                          Apply Filters
                        </button>
                      )}
                      {selectedChannels.length > 0 && (
                        <button 
                          type="button" 
                          className="clear-filters-button"
                          onClick={clearChannelFilters}
                        >
                          Clear Filters
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="channel-filter-chips">
                    {channelsInResults.map(channel => (
                      <div 
                        key={channel.name} 
                        className={`channel-chip ${selectedChannels.includes(channel.name) ? 'selected' : ''}`}
                        onClick={() => handleChannelToggle(channel.name)}
                      >
                        <span className="channel-name">{channel.name}</span>
                        <span className="channel-count">{channel.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
                  <input
                    type="number"
                    min="1"
                    max={totalPages}
                    value={pageInput || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setPageInput(value);
                      const pageNum = parseInt(value);
                      if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
                        handlePageChange(pageNum);
                      }
                    }}
                    onBlur={() => {
                      if (!pageInput || isNaN(parseInt(pageInput))) {
                        setPageInput(currentPage.toString());
                      }
                    }}
                    className="page-input"
                    placeholder="#"
                  />
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