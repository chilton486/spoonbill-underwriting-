const BASE_URL = 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  })

  const contentType = res.headers.get('content-type')
  const isJson = contentType && contentType.includes('application/json')
  const body = isJson ? await res.json() : await res.text()

  if (!res.ok) {
    const err = new Error('API request failed')
    err.status = res.status
    err.body = body
    throw err
  }

  return body
}

export async function getClaims() {
  return request('/claims')
}

export async function getPractices() {
  return request('/practices')
}

export async function getCapitalPool(poolId = 'POOL') {
  return request(`/capital-pool/${encodeURIComponent(poolId)}`)
}

export async function simulate({ poolId = 'POOL', seedIfEmpty = true, advanceOneStep = true } = {}) {
  return request('/simulate', {
    method: 'POST',
    body: JSON.stringify({
      pool_id: poolId,
      seed_if_empty: seedIfEmpty,
      advance_one_step: advanceOneStep
    })
  })
}

export async function underwriteClaim(claimId, { poolId = 'POOL' } = {}) {
  return request(`/claims/${encodeURIComponent(claimId)}/underwrite`, {
    method: 'POST',
    body: JSON.stringify({ pool_id: poolId })
  })
}

export async function fundClaim(claimId, { poolId = 'POOL' } = {}) {
  return request(`/claims/${encodeURIComponent(claimId)}/fund`, {
    method: 'POST',
    body: JSON.stringify({ pool_id: poolId })
  })
}

export async function settleClaim(claimId, { poolId = 'POOL', settlementDate, settlementAmount } = {}) {
  return request(`/claims/${encodeURIComponent(claimId)}/settle`, {
    method: 'POST',
    body: JSON.stringify({
      pool_id: poolId,
      settlement_date: settlementDate,
      settlement_amount: settlementAmount
    })
  })
}

export async function resetDemo({ poolId = 'POOL' } = {}) {
  return request('/reset', {
    method: 'POST',
    body: JSON.stringify({ pool_id: poolId })
  })
}

export async function submitClaim({
  practiceId,
  payer,
  procedureCodes,
  billedAmount,
  expectedAllowedAmount,
  serviceDate,
  externalClaimId
}) {
  return request('/claims/submit', {
    method: 'POST',
    body: JSON.stringify({
      practice_id: practiceId,
      payer: payer,
      procedure_codes: procedureCodes,
      billed_amount: billedAmount,
      expected_allowed_amount: expectedAllowedAmount,
      service_date: serviceDate,
      external_claim_id: externalClaimId
    })
  })
}

export async function simulateAdjudication({
  externalClaimId,
  status,
  approvedAmount = null,
  reasonCodes = null
}) {
  return request('/webhooks/clearinghouse', {
    method: 'POST',
    body: JSON.stringify({
      external_claim_id: externalClaimId,
      status: status,
      approved_amount: approvedAmount,
      reason_codes: reasonCodes
    })
  })
}
