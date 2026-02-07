const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

let authToken = localStorage.getItem('authToken')

export function setAuthToken(token) {
  authToken = token
  if (token) {
    localStorage.setItem('authToken', token)
  } else {
    localStorage.removeItem('authToken')
  }
}

export function getAuthToken() {
  return authToken
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options
  })

  const contentType = res.headers.get('content-type')
  const isJson = contentType && contentType.includes('application/json')
  const body = isJson ? await res.json() : await res.text()

  if (!res.ok) {
    const err = new Error(body?.detail || 'API request failed')
    err.status = res.status
    err.body = body
    throw err
  }

  return body
}

export async function login(email, password) {
  const formData = new URLSearchParams()
  formData.append('username', email)
  formData.append('password', password)
  
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData
  })
  
  const body = await res.json()
  
  if (!res.ok) {
    throw new Error(body?.detail || 'Login failed')
  }
  
  setAuthToken(body.access_token)
  return body
}

export async function logout() {
  setAuthToken(null)
}

export async function getCurrentUser() {
  return request('/auth/me')
}

export async function getClaims(status = null) {
  const params = status ? `?status=${encodeURIComponent(status)}` : ''
  return request(`/api/claims${params}`)
}

export async function getClaim(claimId) {
  return request(`/api/claims/${claimId}`)
}

export async function createClaim(data) {
  return request('/api/claims', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export async function updateClaim(claimId, data) {
  return request(`/api/claims/${claimId}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  })
}

export async function transitionClaim(claimId, toStatus, reason = null) {
  return request(`/api/claims/${claimId}/transition`, {
    method: 'POST',
    body: JSON.stringify({
      to_status: toStatus,
      reason: reason
    })
  })
}

export async function getValidTransitions(claimId) {
  return request(`/api/claims/${claimId}/transitions`)
}

export async function getUsers() {
  return request('/api/users')
}

export async function createUser(data) {
  return request('/api/users', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export async function deactivateUser(userId) {
  return request(`/api/users/${userId}/deactivate`, {
    method: 'PATCH'
  })
}

export async function activateUser(userId) {
  return request(`/api/users/${userId}/activate`, {
    method: 'PATCH'
  })
}

export async function getPaymentForClaim(claimId) {
  return request(`/api/payments/claim/${claimId}`)
}

export async function processPayment(claimId) {
  return request('/api/payments/process', {
    method: 'POST',
    body: JSON.stringify({ claim_id: claimId })
  })
}

export async function retryPayment(paymentId) {
  return request(`/api/payments/${paymentId}/retry`, {
    method: 'POST'
  })
}

export async function getLedgerSummary(currency = 'USD') {
  return request(`/api/payments/ledger/summary?currency=${encodeURIComponent(currency)}`)
}

export async function seedCapital(amountCents, currency = 'USD') {
  return request('/api/payments/ledger/seed', {
    method: 'POST',
    body: JSON.stringify({ amount_cents: amountCents, currency })
  })
}
