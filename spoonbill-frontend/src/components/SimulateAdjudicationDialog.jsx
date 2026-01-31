import * as React from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Typography from '@mui/material/Typography'

export default function SimulateAdjudicationDialog({ open, onClose, claims, onSubmit }) {
  const [externalClaimId, setExternalClaimId] = React.useState('')
  const [status, setStatus] = React.useState('approved')
  const [approvedAmount, setApprovedAmount] = React.useState('')
  const [reasonCodes, setReasonCodes] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState(null)

  const submittedClaims = (claims || []).filter(
    c => c.status === 'submitted' && c.external_claim_id
  )

  React.useEffect(() => {
    if (open) {
      setExternalClaimId('')
      setStatus('approved')
      setApprovedAmount('')
      setReasonCodes('')
      setError(null)
    }
  }, [open])

  React.useEffect(() => {
    if (externalClaimId) {
      const claim = submittedClaims.find(c => c.external_claim_id === externalClaimId)
      if (claim && status === 'approved') {
        setApprovedAmount((claim.expected_allowed_amount / 100).toFixed(2))
      }
    }
  }, [externalClaimId, status, submittedClaims])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const codes = reasonCodes ? reasonCodes.split(',').map(c => c.trim()).filter(Boolean) : null

      await onSubmit({
        externalClaimId,
        status,
        approvedAmount: status === 'approved' && approvedAmount ? parseFloat(approvedAmount) : null,
        reasonCodes: codes && codes.length > 0 ? codes : null
      })
      onClose()
    } catch (err) {
      setError(err?.body?.detail || err?.message || 'Failed to simulate adjudication')
    } finally {
      setSubmitting(false)
    }
  }

  const isValid = externalClaimId && status

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 700 }}>Simulate Adjudication</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}

            {submittedClaims.length === 0 ? (
              <Alert severity="info">
                No claims with external IDs are in "submitted" status. Submit a claim first using the "Submit Claim" button.
              </Alert>
            ) : (
              <>
                <TextField
                  select
                  label="Select Claim"
                  value={externalClaimId}
                  onChange={(e) => setExternalClaimId(e.target.value)}
                  required
                  fullWidth
                  helperText="Only claims with external IDs in 'submitted' status are shown"
                >
                  {submittedClaims.map((c) => (
                    <MenuItem key={c.external_claim_id} value={c.external_claim_id}>
                      {c.external_claim_id} ({c.claim_id} - {c.practice_id})
                    </MenuItem>
                  ))}
                </TextField>

                <TextField
                  select
                  label="Adjudication Status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  required
                  fullWidth
                >
                  <MenuItem value="approved">Approved</MenuItem>
                  <MenuItem value="denied">Denied</MenuItem>
                </TextField>

                {status === 'approved' && (
                  <TextField
                    label="Approved Amount ($)"
                    type="number"
                    value={approvedAmount}
                    onChange={(e) => setApprovedAmount(e.target.value)}
                    fullWidth
                    inputProps={{ min: 0, step: 0.01 }}
                    helperText="Amount approved by the payer"
                  />
                )}

                <TextField
                  label="Reason Codes"
                  value={reasonCodes}
                  onChange={(e) => setReasonCodes(e.target.value)}
                  fullWidth
                  placeholder="CO45, PR1"
                  helperText="Optional comma-separated reason codes (e.g., CO45 for contractual adjustment)"
                />

                <Typography variant="caption" sx={{ color: 'rgba(226,232,240,0.6)' }}>
                  This simulates a clearinghouse webhook response. Approved claims will move to "adjudicated" status, denied claims will move to "exception" status.
                </Typography>
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={!isValid || submitting || submittedClaims.length === 0}
            startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
            color={status === 'denied' ? 'error' : 'primary'}
          >
            {submitting ? 'Processing...' : `Simulate ${status === 'approved' ? 'Approval' : 'Denial'}`}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
