import * as React from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'

import { getClaim, getValidTransitions, transitionClaim } from '../api.js'

function formatCurrency(cents) {
  if (cents === null || cents === undefined) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(cents / 100)
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const STATUS_COLORS = {
  NEW: 'info',
  NEEDS_REVIEW: 'warning',
  APPROVED: 'success',
  PAID: 'success',
  COLLECTING: 'info',
  CLOSED: 'default',
  DECLINED: 'error'
}

export default function ClaimDetailDialog({ open, onClose, claim: initialClaim, onRefresh }) {
  const [claim, setClaim] = React.useState(null)
  const [validTransitions, setValidTransitions] = React.useState([])
  const [selectedTransition, setSelectedTransition] = React.useState('')
  const [reason, setReason] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [transitioning, setTransitioning] = React.useState(false)
  const [error, setError] = React.useState(null)

  React.useEffect(() => {
    if (!open || !initialClaim) {
      setClaim(null)
      setValidTransitions([])
      setSelectedTransition('')
      setReason('')
      setError(null)
      return
    }

    let mounted = true
    ;(async () => {
      setLoading(true)
      try {
        const [claimData, transitions] = await Promise.all([
          getClaim(initialClaim.id),
          getValidTransitions(initialClaim.id)
        ])
        if (mounted) {
          setClaim(claimData)
          setValidTransitions(transitions.valid_transitions || [])
        }
      } catch (e) {
        if (mounted) setError(e.message)
      } finally {
        if (mounted) setLoading(false)
      }
    })()

    return () => { mounted = false }
  }, [open, initialClaim])

  const handleTransition = async () => {
    if (!selectedTransition) return
    setTransitioning(true)
    setError(null)
    try {
      await transitionClaim(claim.id, selectedTransition, reason || null)
      const [claimData, transitions] = await Promise.all([
        getClaim(claim.id),
        getValidTransitions(claim.id)
      ])
      setClaim(claimData)
      setValidTransitions(transitions.valid_transitions || [])
      setSelectedTransition('')
      setReason('')
      if (onRefresh) onRefresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setTransitioning(false)
    }
  }

  if (!open) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        Claim Details {claim ? `#${claim.id}` : ''}
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Stack sx={{ py: 4, alignItems: 'center' }}>
            <CircularProgress />
          </Stack>
        ) : claim ? (
          <Stack spacing={3}>
            {error && <Alert severity="error">{error}</Alert>}

            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="h6">Status:</Typography>
              <Chip 
                label={claim.status.replace('_', ' ')} 
                color={STATUS_COLORS[claim.status] || 'default'}
              />
            </Stack>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Claim Information</Typography>
              <Stack spacing={1}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Payer:</Typography>
                  <Typography>{claim.payer}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Patient Name:</Typography>
                  <Typography>{claim.patient_name || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Amount:</Typography>
                  <Typography>{formatCurrency(claim.amount_cents)}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Procedure Date:</Typography>
                  <Typography>{claim.procedure_date || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Practice ID:</Typography>
                  <Typography>{claim.practice_id || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Procedure Codes:</Typography>
                  <Typography>{claim.procedure_codes || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Created:</Typography>
                  <Typography>{formatDateTime(claim.created_at)}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Updated:</Typography>
                  <Typography>{formatDateTime(claim.updated_at)}</Typography>
                </Stack>
              </Stack>
            </Paper>

            {claim.underwriting_decisions && claim.underwriting_decisions.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Underwriting Decisions</Typography>
                {claim.underwriting_decisions.map((decision, idx) => (
                  <Stack key={idx} spacing={1} sx={{ mb: idx < claim.underwriting_decisions.length - 1 ? 2 : 0 }}>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Chip 
                        label={decision.decision} 
                        size="small"
                        color={decision.decision === 'APPROVE' ? 'success' : decision.decision === 'DECLINE' ? 'error' : 'warning'}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {formatDateTime(decision.decided_at)}
                      </Typography>
                    </Stack>
                    {decision.reasons && (
                      <Typography variant="body2" sx={{ pl: 1, fontStyle: 'italic' }}>
                        {decision.reasons}
                      </Typography>
                    )}
                  </Stack>
                ))}
              </Paper>
            )}

            {claim.audit_events && claim.audit_events.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Audit Trail</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell>From</TableCell>
                      <TableCell>To</TableCell>
                      <TableCell>Actor</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {claim.audit_events.map((event, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{formatDateTime(event.created_at)}</TableCell>
                        <TableCell>{event.action}</TableCell>
                        <TableCell>{event.from_status || '-'}</TableCell>
                        <TableCell>{event.to_status || '-'}</TableCell>
                        <TableCell>{event.actor_email || 'system'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Paper>
            )}

            {validTransitions.length > 0 && (
              <>
                <Divider />
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Transition Status</Typography>
                  <Stack spacing={2}>
                    <Select
                      value={selectedTransition}
                      onChange={(e) => setSelectedTransition(e.target.value)}
                      displayEmpty
                      fullWidth
                      size="small"
                    >
                      <MenuItem value="">Select new status...</MenuItem>
                      {validTransitions.map((status) => (
                        <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
                      ))}
                    </Select>
                    <TextField
                      label="Reason (optional)"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      fullWidth
                      size="small"
                      multiline
                      rows={2}
                    />
                    <Button
                      variant="contained"
                      onClick={handleTransition}
                      disabled={!selectedTransition || transitioning}
                      startIcon={transitioning ? <CircularProgress size={20} color="inherit" /> : null}
                    >
                      {transitioning ? 'Transitioning...' : 'Apply Transition'}
                    </Button>
                  </Stack>
                </Paper>
              </>
            )}
          </Stack>
        ) : (
          <Typography color="text.secondary">No claim selected</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
