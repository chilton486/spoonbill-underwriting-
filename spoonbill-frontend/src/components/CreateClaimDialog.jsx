import * as React from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'

import { createClaim } from '../api.js'

export default function CreateClaimDialog({ open, onClose, onCreated }) {
  const [payer, setPayer] = React.useState('')
  const [patientName, setPatientName] = React.useState('')
  const [amountCents, setAmountCents] = React.useState('')
  const [procedureDate, setProcedureDate] = React.useState('')
  const [practiceId, setPracticeId] = React.useState('')
  const [procedureCodes, setProcedureCodes] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(null)

  const resetForm = () => {
    setPayer('')
    setPatientName('')
    setAmountCents('')
    setProcedureDate('')
    setPracticeId('')
    setProcedureCodes('')
    setError(null)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await createClaim({
        payer,
        patient_name: patientName || null,
        amount_cents: parseInt(amountCents, 10),
        procedure_date: procedureDate || null,
        practice_id: practiceId || null,
        procedure_codes: procedureCodes || null,
      })
      resetForm()
      onCreated()
    } catch (err) {
      setError(err.body?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Create New Claim</DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent dividers>
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
            
            <TextField
              label="Payer"
              value={payer}
              onChange={(e) => setPayer(e.target.value)}
              required
              fullWidth
              placeholder="e.g., Aetna, BCBS, Delta Dental"
            />
            
            <TextField
              label="Amount (cents)"
              type="number"
              value={amountCents}
              onChange={(e) => setAmountCents(e.target.value)}
              required
              fullWidth
              placeholder="e.g., 15000 for $150.00"
              inputProps={{ min: 1 }}
            />
            
            <TextField
              label="Patient Name (optional)"
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              fullWidth
            />
            
            <TextField
              label="Procedure Date (optional)"
              type="date"
              value={procedureDate}
              onChange={(e) => setProcedureDate(e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            
            <TextField
              label="Practice ID (optional)"
              value={practiceId}
              onChange={(e) => setPracticeId(e.target.value)}
              fullWidth
            />
            
            <TextField
              label="Procedure Codes (optional)"
              value={procedureCodes}
              onChange={(e) => setProcedureCodes(e.target.value)}
              fullWidth
              placeholder="e.g., D0120, D1110"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading || !payer || !amountCents}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
          >
            {loading ? 'Creating...' : 'Create Claim'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
