import axios from 'axios';

// Use environment variable for API URL with fallback for local development
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

// Log the API URL being used (helpful for debugging)
console.log(`Using API URL: ${API_URL}`);

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true
});

// Add response interceptor for handling common errors
api.interceptors.response.use(
  response => response,
  error => {
    // Handle authentication errors
    if (error.response && error.response.status === 401) {
      console.error('Authentication error:', error);
      // You could redirect to login page here if needed
    }
    
    // Handle server errors
    if (error.response && error.response.status >= 500) {
      console.error('Server error:', error);
    }
    
    // Handle network errors
    if (error.message === 'Network Error') {
      console.error('Network error - API server may be unavailable');
    }
    
    return Promise.reject(error);
  }
);

export const getAuthStatus = () => api.get('/auth/status');
export const getLoginUrl = () => api.get('/auth/login');
export const logout = () => api.get('/auth/logout');

export const getPlaylists = () => api.get('/playlists');
export const getIndexedPlaylists = () => api.get('/indexed-playlists');
export const indexPlaylist = (playlistId, incremental = false) => {
  // Make sure we're only sending a simple object with the incremental flag
  return api.post(`/playlist/${playlistId}/index`, { incremental });
};
export const deletePlaylistIndex = (playlistId) => api.delete(`/playlist/${playlistId}/delete-index`);
export const getIndexingStatus = (playlistId) => api.get(`/indexing-status?playlist_id=${playlistId}`);
export const getPlaylistChannels = (playlistId) => api.get(`/playlist/${playlistId}/channels`);

export const searchPlaylist = (playlistId, query, searchIn = ['title', 'description', 'transcript'], page = 1, size = 10, channels = []) => {
  const params = new URLSearchParams();
  params.append('q', query);
  params.append('page', page);
  params.append('size', size);
  searchIn.forEach(field => params.append('search_in', field));
  
  // Add channel filters if provided
  if (channels && channels.length > 0) {
    channels.forEach(channel => params.append('channel', channel));
  }
  
  return api.get(`/playlist/${playlistId}/search?${params.toString()}`);
};

export const exportPlaylistData = (playlistId) => {
  // Using window.open for direct download instead of axios
  // This will trigger the browser's download behavior
  window.open(`${API_URL}/playlist/${playlistId}/export`);
};

export default api;