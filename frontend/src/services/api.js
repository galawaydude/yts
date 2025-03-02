import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true
});

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