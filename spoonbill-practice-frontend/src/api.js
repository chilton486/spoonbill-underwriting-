export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const IS_DEV = import.meta.env.DEV;

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
  const url = `${API_BASE_URL}/practice/claims/${claimId}`;
  let response;
  try {
    response = await fetch(url, { headers: headers() });
  } catch (err) {
    if (IS_DEV) console.error('[getClaim] Network error:', url, err);
    throw new Error('Network error — check your connection and try again.');
  }

  if (!response.ok) {
    if (IS_DEV) {
      const body = await response.text().catch(() => '');
      console.error(`[getClaim] ${response.status} ${url}`, body);
    }
    if (response.status === 401) throw new Error('Session expired — please log in again.');
    if (response.status === 404) throw new Error('You don\'t have access to this claim.');
    if (response.status >= 500) throw new Error('Server error — try again later.');
    throw new Error('Failed to load claim details.');
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
  const url = `${API_BASE_URL}/practice/claims/${claimId}/documents`;
  let response;
  try {
    response = await fetch(url, { headers: headers() });
  } catch (err) {
    if (IS_DEV) console.error('[listDocuments] Network error:', url, err);
    throw new Error('Network error — check your connection and try again.');
  }

  if (!response.ok) {
    if (IS_DEV) {
      const body = await response.text().catch(() => '');
      console.error(`[listDocuments] ${response.status} ${url}`, body);
    }
    if (response.status === 401) throw new Error('Session expired — please log in again.');
    if (response.status === 404) throw new Error('You don\'t have access to this claim.');
    if (response.status >= 500) throw new Error('Server error — try again later.');
    throw new Error('Failed to load documents.');
  }

  return response.json();
};

export const getDocumentDownloadUrl = (documentId) => {
  return `${API_BASE_URL}/practice/documents/${documentId}`;
};

export const getPaymentStatus = async (claimId) => {
  const url = `${API_BASE_URL}/practice/claims/${claimId}/payment`;
  let response;
  try {
    response = await fetch(url, { headers: headers() });
  } catch (err) {
    if (IS_DEV) console.error('[getPaymentStatus] Network error:', url, err);
    return null;
  }

  if (!response.ok) {
    if (response.status === 404) return null;
    if (IS_DEV) {
      const body = await response.text().catch(() => '');
      console.error(`[getPaymentStatus] ${response.status} ${url}`, body);
    }
    return null;
  }

  return response.json();
};

export const getDashboard = async () => {
  const response = await fetch(`${API_BASE_URL}/practice/dashboard`, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch dashboard');
  }

  return response.json();
};

export const listPayments = async () => {
  const response = await fetch(`${API_BASE_URL}/practice/payments`, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch payments');
  }

  return response.json();
};

export const getOntologyContext = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/context`, {
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch ontology context');
  }

  return response.json();
};

export const generateOntologyBrief = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/brief`, {
    method: 'POST',
    headers: headers(),
  });

  if (!response.ok) {
    throw new Error('Failed to generate ontology brief');
  }

  return response.json();
};

export const adjustPracticeLimit = async (practiceId, newLimit, reason) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/limit`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ new_limit: newLimit, reason }),
  });

  if (!response.ok) {
    throw new Error('Failed to adjust practice limit');
  }

  return response.json();
};

export const getOntologyCohorts = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/cohorts`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error('Failed to fetch cohorts');
  return response.json();
};

export const getCfo360 = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/cfo`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error('Failed to fetch CFO 360');
  return response.json();
};

export const getOntologyRisks = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/risks`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error('Failed to fetch risks');
  return response.json();
};

export const getOntologyGraph = async (practiceId) => {
  const response = await fetch(`${API_BASE_URL}/practices/${practiceId}/ontology/graph`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error('Failed to fetch graph');
  return response.json();
};

export const getIntegrationStatus = async () => {
  const response = await fetch(`${API_BASE_URL}/practice/integrations/open-dental/status`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error('Failed to fetch integration status');
  return response.json();
};

export const uploadIntegrationCSV = async (claimsFile, linesFile) => {
  const formData = new FormData();
  formData.append('claims_file', claimsFile);
  if (linesFile) {
    formData.append('lines_file', linesFile);
  }

  const h = {};
  if (authToken) {
    h['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}/practice/integrations/open-dental/upload`, {
    method: 'POST',
    headers: h,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'CSV upload failed');
  }

  return response.json();
};

export const runIntegrationSync = async () => {
  const response = await fetch(`${API_BASE_URL}/practice/integrations/open-dental/sync`, {
    method: 'POST',
    headers: headers(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Sync failed');
  }

  return response.json();
};

export const validateInviteToken = async (token) => {
  const response = await fetch(`${API_BASE_URL}/public/invites/${token}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Invalid or expired invite link.');
  }

  return response.json();
};

export const setPassword = async (token, password) => {
  const response = await fetch(`${API_BASE_URL}/public/invites/${token}/set-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to set password.');
  }

  return response.json();
};
