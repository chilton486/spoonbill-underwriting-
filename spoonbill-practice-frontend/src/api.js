const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

export const listClaims = async (filters = {}) => {
  const params = new URLSearchParams();
  
  if (filters.status_filter) params.append('status_filter', filters.status_filter);
  if (filters.claim_id) params.append('claim_id', filters.claim_id);
  if (filters.claim_token) params.append('claim_token', filters.claim_token);
  if (filters.submitted_from) params.append('submitted_from', filters.submitted_from);
  if (filters.submitted_to) params.append('submitted_to', filters.submitted_to);
  if (filters.decision_from) params.append('decision_from', filters.decision_from);
  if (filters.decision_to) params.append('decision_to', filters.decision_to);
  if (filters.q) params.append('q', filters.q);
  if (filters.page) params.append('page', filters.page);
  if (filters.page_size) params.append('page_size', filters.page_size);

  const queryString = params.toString();
  const url = `${API_BASE_URL}/practice/claims${queryString ? `?${queryString}` : ''}`;

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

export const getPaymentStatus = async (claimId) => {
  const response = await fetch(`${API_BASE_URL}/practice/claims/${claimId}/payment`, {
    headers: headers(),
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    throw new Error('Failed to fetch payment status');
  }

  return response.json();
};

export const validateInviteToken = async (token) => {
  const response = await fetch(`${API_BASE_URL}/invite/${token}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Invalid or expired invite link.');
  }

  return response.json();
};

export const setPassword = async (token, password) => {
  const response = await fetch(`${API_BASE_URL}/set-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to set password.');
  }

  return response.json();
};
