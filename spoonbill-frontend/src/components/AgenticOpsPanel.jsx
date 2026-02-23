import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Skeleton from '@mui/material/Skeleton'
import Tooltip from '@mui/material/Tooltip'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { tokens } from '../theme.js'

import {
  generateActionProposals,
  executeActionProposal,
} from '../api.js'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getApiError(e) {
  if (e.status === 401) return 'Session expired. Please log in again.'
  if (e.status === 403) return 'You do not have permission for agentic operations.'
  if (e.status === 404) return 'Action proposals endpoint not found. Backend may need updating.'
  if (e.status === 503) return 'System is updating. Please try again shortly.'
  if (e.status >= 500) return 'Server error (' + e.status + '). Please try again later.'
  return e.message || 'Operation failed'
}

const SEVERITY_COLORS = {
  high: 'error',
  medium: 'warning',
  low: 'info',
}

const SEVERITY_LABELS = {
  high: 'High Priority',
  medium: 'Medium',
  low: 'Low',
}

const ACTION_LABELS = {
  ADJUST_LIMIT: 'Adjust Funding Limit',
  PAUSE_FUNDING: 'Pause Funding',
  RESUME_FUNDING: 'Resume Funding',
  REVIEW_EXCEPTIONS: 'Review Exceptions',
  FLAG_CONCENTRATION: 'Flag Concentration Risk',
}

function ProposalCard({ proposal, onApply, index }) {
  const [expanded, setExpanded] = React.useState(false)

  return (
    <Paper sx={{ p: 2.5 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label={ACTION_LABELS[proposal.action] || proposal.action} size="small" color={SEVERITY_COLORS[proposal.severity] || 'default'} />
            <Chip label={SEVERITY_LABELS[proposal.severity] || proposal.severity} size="small" variant="outlined" />
            {proposal.required_approvals && (
              <Tooltip title={'Requires ' + proposal.required_approvals + ' approval(s)'}>
                <Chip label={proposal.required_approvals + ' approval(s)'} size="small" variant="outlined" sx={{ borderColor: tokens.colors.status.warning }} />
              </Tooltip>
            )}
          </Stack>
          <Typography variant="caption" sx={{ color: tokens.colors.text.muted }}>{proposal.practice_name}</Typography>
        </Stack>

        <Typography variant="body2">{proposal.reason}</Typography>

        {proposal.action === 'ADJUST_LIMIT' && proposal.params && (
          <Stack direction="row" spacing={4} sx={{ py: 0.5 }}>
            <Box>
              <Typography variant="caption">Current Limit</Typography>
              <Typography variant="subtitle2">{fmt(proposal.params.current_limit_cents)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="body2" sx={{ color: tokens.colors.text.muted }}>&rarr;</Typography>
            </Box>
            <Box>
              <Typography variant="caption">Proposed</Typography>
              <Typography variant="subtitle2" sx={{ color: tokens.colors.status.success }}>{fmt(proposal.params.proposed_limit_cents)}</Typography>
            </Box>
            {proposal.params.current_limit_cents && proposal.params.proposed_limit_cents && (
              <Box>
                <Typography variant="caption">Change</Typography>
                <Typography variant="subtitle2" sx={{
                  color: proposal.params.proposed_limit_cents > proposal.params.current_limit_cents ? tokens.colors.status.success : tokens.colors.status.error,
                }}>
                  {proposal.params.proposed_limit_cents > proposal.params.current_limit_cents ? '+' : ''}
                  {fmt(proposal.params.proposed_limit_cents - proposal.params.current_limit_cents)}
                </Typography>
              </Box>
            )}
          </Stack>
        )}

        <Button size="small" variant="text" onClick={() => setExpanded(!expanded)} sx={{ alignSelf: 'flex-start' }}>
          {expanded ? 'Hide Metrics' : 'Show Metrics'}
        </Button>

        {expanded && proposal.supporting_metrics && (
          <Paper variant="outlined" sx={{ p: 1.5, bgcolor: tokens.colors.surfaceHover }}>
            <Stack spacing={0.5}>
              {Object.entries(proposal.supporting_metrics).map(([k, v]) => (
                <Stack key={k} direction="row" justifyContent="space-between">
                  <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>{k.replace(/_/g, ' ')}</Typography>
                  <Typography variant="caption" sx={{ fontWeight: 600, fontFamily: tokens.typography.mono }}>
                    {typeof v === 'number' && k.includes('cents') ? fmt(v) : typeof v === 'number' && k.includes('pct') ? v + '%' : String(v)}
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
      if ((result.proposals || []).length === 0) {
        setSuccess('Analysis complete. No actionable recommendations at this time.')
      }
    } catch (e) {
      setError(getApiError(e))
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
      await executeActionProposal(confirmDialog)
      setSuccess('Action "' + (ACTION_LABELS[confirmDialog.action] || confirmDialog.action) + '" executed successfully for ' + confirmDialog.practice_name + '.')
      setProposals((prev) => prev.filter((p) => p !== confirmDialog))
      setConfirmDialog(null)
    } catch (e) {
      const detail = e.body?.detail
      const errMsg = detail?.errors ? detail.errors.join('; ') : getApiError(e)
      setError(errMsg)
      setConfirmDialog(null)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <SmartToyIcon sx={{ color: tokens.colors.accent[500], fontSize: 22 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>Agentic Ops</Typography>
        </Stack>
        <Button variant="contained" size="small" onClick={handleGenerate} disabled={loading}>
          {loading ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
          Generate Recommendations
        </Button>
      </Stack>

      <Alert severity="info" sx={{ py: 0.5 }} icon={<WarningAmberIcon fontSize="small" />}>
        Recommendations are generated by a deterministic rules engine. Applying an action requires explicit confirmation and writes an audit event. No action is taken without human approval.
      </Alert>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>}

      {loading && (
        <Stack spacing={2}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Paper key={i} sx={{ p: 2.5 }}>
              <Stack spacing={1.5}>
                <Stack direction="row" spacing={1}>
                  <Skeleton variant="rounded" width={140} height={26} />
                  <Skeleton variant="rounded" width={80} height={26} />
                </Stack>
                <Skeleton variant="text" width="80%" />
                <Skeleton variant="text" width="60%" />
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      {proposals.length === 0 && !loading && !success && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <SmartToyIcon sx={{ fontSize: 40, color: tokens.colors.text.muted, mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Click "Generate Recommendations" to analyze {practiceId ? 'this practice' : 'all practices'} and surface actionable proposals.
          </Typography>
        </Paper>
      )}

      {proposals.length > 0 && (
        <Typography variant="caption" color="text.secondary">
          {proposals.length} recommendation{proposals.length !== 1 ? 's' : ''} generated
        </Typography>
      )}

      {proposals.map((p, i) => (
        <ProposalCard key={p.action + '-' + (p.practice_id || '') + '-' + i} proposal={p} onApply={handleApply} index={i} />
      ))}

      <Dialog open={!!confirmDialog} onClose={() => setConfirmDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningAmberIcon sx={{ color: tokens.colors.status.warning }} />
          Confirm Action
        </DialogTitle>
        <DialogContent>
          {confirmDialog && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body1">
                <strong>{ACTION_LABELS[confirmDialog.action] || confirmDialog.action}</strong> for {confirmDialog.practice_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">{confirmDialog.reason}</Typography>
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
              <Alert severity="warning" variant="outlined">
                This action will be logged as an audit event and cannot be undone without a manual correction.
              </Alert>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog(null)} disabled={executing}>Cancel</Button>
          <Button variant="contained" color="warning" onClick={handleConfirmExecute} disabled={executing}>
            {executing ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
            Confirm & Execute
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
