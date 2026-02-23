import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import Divider from '@mui/material/Divider'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import { tokens } from '../theme.js'

import {
  generateActionProposals,
  executeActionProposal,
} from '../api.js'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const SEVERITY_COLORS = {
  high: 'error',
  medium: 'warning',
  low: 'info',
}

const ACTION_LABELS = {
  ADJUST_LIMIT: 'Adjust Funding Limit',
  PAUSE_FUNDING: 'Pause Funding',
  REVIEW_EXCEPTIONS: 'Review Exceptions',
}

function ProposalCard({ proposal, onApply }) {
  const [expanded, setExpanded] = React.useState(false)

  return (
    <Paper sx={{ p: 2.5 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label={ACTION_LABELS[proposal.action] || proposal.action} size="small" color={SEVERITY_COLORS[proposal.severity] || 'default'} />
            <Chip label={proposal.severity} size="small" variant="outlined" />
          </Stack>
          <Typography variant="caption">{proposal.practice_name}</Typography>
        </Stack>

        <Typography variant="body2">{proposal.reason}</Typography>

        {proposal.action === 'ADJUST_LIMIT' && proposal.params && (
          <Stack direction="row" spacing={3} sx={{ py: 0.5 }}>
            <Box>
              <Typography variant="caption">Current Limit</Typography>
              <Typography variant="subtitle2">{fmt(proposal.params.current_limit_cents)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption">→ Proposed</Typography>
              <Typography variant="subtitle2" sx={{ color: tokens.colors.status.success }}>{fmt(proposal.params.proposed_limit_cents)}</Typography>
            </Box>
          </Stack>
        )}

        <Button size="small" variant="text" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Hide Metrics' : 'Show Metrics'}
        </Button>

        {expanded && proposal.supporting_metrics && (
          <Paper variant="outlined" sx={{ p: 1.5, bgcolor: tokens.colors.surfaceHover }}>
            <Stack spacing={0.5}>
              {Object.entries(proposal.supporting_metrics).map(([k, v]) => (
                <Stack key={k} direction="row" justifyContent="space-between">
                  <Typography variant="caption">{k.replace(/_/g, ' ')}</Typography>
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    {typeof v === 'number' && k.includes('cents') ? fmt(v) : String(v)}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Paper>
        )}

        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button size="small" variant="contained" onClick={() => onApply(proposal)}>
            Apply
          </Button>
        </Stack>
      </Stack>
    </Paper>
  )
}

export default function AgenticOpsPanel({ practiceId }) {
  const [proposals, setProposals] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(null)
  const [success, setSuccess] = React.useState(null)
  const [confirmDialog, setConfirmDialog] = React.useState(null)
  const [executing, setExecuting] = React.useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await generateActionProposals(practiceId)
      setProposals(result.proposals || [])
    } catch (e) {
      setError(e.message || 'Failed to generate recommendations')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = (proposal) => {
    setConfirmDialog(proposal)
  }

  const handleConfirmExecute = async () => {
    if (!confirmDialog) return
    setExecuting(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await executeActionProposal(confirmDialog)
      setSuccess(`Action "${confirmDialog.action}" executed successfully.`)
      setProposals((prev) => prev.filter((p) => p !== confirmDialog))
      setConfirmDialog(null)
    } catch (e) {
      const detail = e.body?.detail
      const errMsg = detail?.errors ? detail.errors.join('; ') : (e.message || 'Execution failed')
      setError(errMsg)
      setConfirmDialog(null)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h6" sx={{ fontWeight: 600 }}>Agentic Ops</Typography>
        <Button variant="contained" size="small" onClick={handleGenerate} disabled={loading}>
          {loading ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
          Generate Recommendations
        </Button>
      </Stack>

      <Alert severity="info" sx={{ py: 0.5 }}>
        Recommendations are generated by a deterministic rules engine. Applying an action requires explicit confirmation and writes an audit event.
      </Alert>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>}

      {proposals.length === 0 && !loading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Click "Generate Recommendations" to analyze practices and surface actionable proposals.
          </Typography>
        </Paper>
      )}

      {proposals.map((p, i) => (
        <ProposalCard key={`${p.action}-${p.practice_id}-${i}`} proposal={p} onApply={handleApply} />
      ))}

      <Dialog open={!!confirmDialog} onClose={() => setConfirmDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Confirm Action</DialogTitle>
        <DialogContent>
          {confirmDialog && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body1">
                <strong>{ACTION_LABELS[confirmDialog.action] || confirmDialog.action}</strong> for {confirmDialog.practice_name}
              </Typography>
              <Typography variant="body2">{confirmDialog.reason}</Typography>
              {confirmDialog.action === 'ADJUST_LIMIT' && confirmDialog.params && (
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Stack spacing={1}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2">Current Limit</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>{fmt(confirmDialog.params.current_limit_cents)}</Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2">New Limit</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: tokens.colors.status.success }}>{fmt(confirmDialog.params.proposed_limit_cents)}</Typography>
                    </Stack>
                  </Stack>
                </Paper>
              )}
              <Alert severity="warning">This action will be logged as an audit event and cannot be undone without a manual correction.</Alert>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog(null)} disabled={executing}>Cancel</Button>
          <Button variant="contained" onClick={handleConfirmExecute} disabled={executing}>
            {executing ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
            Confirm & Execute
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
