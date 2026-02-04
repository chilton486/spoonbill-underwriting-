const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let authToken = localStorage.getItem('practice_token');

export const setAuthToken = (token) => {
  authToken = token;
  if (token) {
    localStorage.setItem('practice_token', token);
  } else {
    localStorage.removeItem('practice_token');
  }
};

export const getAuthToken = () => authToken;

const headers = () => {
  const h = { 'Content-Type': 'application/json' };
  if (authToken) {
    h['Authorization'] = `Bearer ${authToken}`;
  }
  return h;
};

export const login = async (email, password) => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  const data = await response.json();
  setAuthToken(data.access_token);
  return data;
};

export const logout = () => {
  setAuthToken(null);
};

export const getCurrentUser = async () => {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to get current user');
  }

  return response.json();
};

export const listClaims = async (statusFilter = null) => {
  let url = `${API_BASE_URL}/practice/claims`;
  if (statusFilter) {
    url += `?status_filter=${statusFilter}`;
  }

  const response = await fetch(url, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch claims');
  }

  return response.json();
};

export const getClaim = async (claimId) => {
  const response = await fetch(`${API_BASE_URL}/practice/claims/${claimId}`, {
    headers: headers(),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Claim not found');
    }
    throw new Error('Failed to fetch claim');
  }

  return response.json();
};

export const submitClaim = async (claimData) => {
  const response = await fetch(`${API_BASE_URL}/practice/claims`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(claimData),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to submit claim');
  }

  return response.json();
};

export const uploadDocument = async (claimId, file) => {
  const formData = new FormData();
  formData.append('file', file);

  const h = {};
  if (authToken) {
    h['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}/practice/claims/${claimId}/documents`, {
    method: 'POST',
    headers: h,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload document');
  }

  return response.json();
};

export const listDocuments = async (claimId) => {
  const response = await fetch(`${API_BASE_URL}/practice/claims/${claimId}/documents`, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch documents');
  }

  return response.json();
};

export const getDocumentDownloadUrl = (documentId) => {
  return `${API_BASE_URL}/practice/documents/${documentId}`;
};
