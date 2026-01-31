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

export default function SubmitClaimDialog({ open, onClose, practices, onSubmit }) {
  const [practiceId, setPracticeId] = React.useState('')
  const [payer, setPayer] = React.useState('')
  const [procedureCodes, setProcedureCodes] = React.useState('')
  const [billedAmount, setBilledAmount] = React.useState('')
  const [expectedAllowedAmount, setExpectedAllowedAmount] = React.useState('')
  const [serviceDate, setServiceDate] = React.useState('')
  const [externalClaimId, setExternalClaimId] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState(null)

  const payers = ['Aetna', 'UnitedHealthcare', 'BCBS', 'Cigna']

  React.useEffect(() => {
    if (open) {
      setPracticeId('')
      setPayer('')
      setProcedureCodes('')
      setBilledAmount('')
      setExpectedAllowedAmount('')
      setServiceDate(new Date().toISOString().slice(0, 10))
      setExternalClaimId(`EXT-${Date.now()}`)
      setError(null)
    }
  }, [open])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const codes = procedureCodes.split(',').map(c => c.trim()).filter(Boolean)
      if (codes.length === 0) {
        throw new Error('Please enter at least one procedure code')
      }

      await onSubmit({
        practiceId,
        payer,
        procedureCodes: codes,
        billedAmount: parseFloat(billedAmount),
        expectedAllowedAmount: parseFloat(expectedAllowedAmount),
        serviceDate,
        externalClaimId
      })
      onClose()
    } catch (err) {
      setError(err?.body?.detail || err?.message || 'Failed to submit claim')
    } finally {
      setSubmitting(false)
    }
  }

  const isValid = practiceId && payer && procedureCodes && billedAmount && expectedAllowedAmount && serviceDate && externalClaimId

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 700 }}>Submit New Claim</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}

            <TextField
              select
              label="Practice"
              value={practiceId}
              onChange={(e) => setPracticeId(e.target.value)}
              required
              fullWidth
            >
              {(practices || []).map((p) => (
                <MenuItem key={p.id} value={p.id}>{p.id}</MenuItem>
              ))}
            </TextField>

            <TextField
              select
              label="Payer"
              value={payer}
              onChange={(e) => setPayer(e.target.value)}
              required
              fullWidth
            >
              {payers.map((p) => (
                <MenuItem key={p} value={p}>{p}</MenuItem>
              ))}
            </TextField>

            <TextField
              label="Procedure Codes"
              value={procedureCodes}
              onChange={(e) => setProcedureCodes(e.target.value)}
              required
              fullWidth
              placeholder="D0120, D1110"
              helperText="Comma-separated procedure codes"
            />

            <Stack direction="row" spacing={2}>
              <TextField
                label="Billed Amount ($)"
                type="number"
                value={billedAmount}
                onChange={(e) => setBilledAmount(e.target.value)}
                required
                fullWidth
                inputProps={{ min: 0, step: 0.01 }}
              />
              <TextField
                label="Expected Allowed ($)"
                type="number"
                value={expectedAllowedAmount}
                onChange={(e) => setExpectedAllowedAmount(e.target.value)}
                required
                fullWidth
                inputProps={{ min: 0, step: 0.01 }}
              />
            </Stack>

            <TextField
              label="Service Date"
              type="date"
              value={serviceDate}
              onChange={(e) => setServiceDate(e.target.value)}
              required
              fullWidth
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="External Claim ID"
              value={externalClaimId}
              onChange={(e) => setExternalClaimId(e.target.value)}
              required
              fullWidth
              helperText="Unique identifier from practice system"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={!isValid || submitting}
            startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {submitting ? 'Submitting...' : 'Submit Claim'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
