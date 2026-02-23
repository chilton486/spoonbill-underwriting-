import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import Skeleton from '@mui/material/Skeleton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import TextField from '@mui/material/TextField'
import RefreshIcon from '@mui/icons-material/Refresh'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import { tokens } from '../theme.js'
import {
  getReconciliationSummary,
  getReconciliationPaymentIntents,
  resolveReconciliationMismatch,
} from '../api.js'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function ReconciliationPage() {
  const [summary, setSummary] = React.useState(null)
  const [piRecon, setPiRecon] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [subTab, setSubTab] = React.useState(0)
  const [resolveDialog, setResolveDialog] = React.useState(null)
  const [resolveNote, setResolveNote] = React.useState('')
  const [resolving, setResolving] = React.useState(false)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, pi] = await Promise.all([
        getReconciliationSummary(),
        getReconciliationPaymentIntents(),
      ])
      setSummary(s)
      setPiRecon(pi)
    } catch (e) {
      setError(e.message || 'Failed to load reconciliation data')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { load() }, [load])

  const handleResolve = async () => {
    if (!resolveDialog) return
    setResolving(true)
    try {
      await resolveReconciliationMismatch({
        confirmation_id: resolveDialog.id,
        resolution_note: resolveNote,
      })
      setResolveDialog(null)
      setResolveNote('')
      load()
    } catch (e) {
      setError(e.message || 'Failed to resolve mismatch')
    } finally {
      setResolving(false)
    }
  }

  const mismatches = React.useMemo(() => {
    if (!piRecon?.items) return []
    return piRecon.items.filter(i => i.mismatch)
  }, [piRecon])

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={2} alignItems="center">
          <CompareArrowsIcon sx={{ fontSize: 28, color: tokens.colors.accent[600] }} />
          <Stack>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>Reconciliation</Typography>
            <Typography variant="body2" color="text.secondary">
              Ledger vs external confirmations
            </Typography>
          </Stack>
        </Stack>
        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 180 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Queued (Ledger)
          </Typography>
          {loading && !summary ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tokens.colors.status.warning }}>
              {fmt(summary?.ledger_totals?.queued_cents)}
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 180 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Sent (Ledger)
          </Typography>
          {loading && !summary ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tokens.colors.status.info }}>
              {fmt(summary?.ledger_totals?.sent_cents)}
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 180 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Confirmed (Ledger)
          </Typography>
          {loading && !summary ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tokens.colors.status.success }}>
              {fmt(summary?.ledger_totals?.confirmed_cents)}
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 180 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Unmatched Confirmations
          </Typography>
          {loading && !summary ? (
            <Skeleton variant="text" width={40} height={32} />
          ) : (
            <Typography variant="h5" sx={{
              fontWeight: 700, mt: 0.5,
              color: (summary?.unmatched_confirmations || 0) > 0 ? tokens.colors.status.error : tokens.colors.status.success,
            }}>
              {summary?.unmatched_confirmations || 0}
            </Typography>
          )}
        </Paper>
      </Stack>

      {(summary?.external_balances || []).length > 0 && (
        <Paper sx={{ p: 2.5 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>External Balance Snapshots</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Facility</TableCell>
                  <TableCell align="right">External Balance</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>As Of</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {summary.external_balances.map((b, i) => (
                  <TableRow key={i}>
                    <TableCell sx={{ fontWeight: 500 }}>{b.facility}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(b.external_balance_cents)}</TableCell>
                    <TableCell>{b.source}</TableCell>
                    <TableCell>{b.as_of ? new Date(b.as_of).toLocaleString() : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      <Paper sx={{ px: 0.5, py: 0 }}>
        <Tabs value={subTab} onChange={(e, v) => setSubTab(v)}>
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Payment Intents</span>
              {piRecon && <Chip label={piRecon.total || 0} size="small" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Mismatches</span>
              {mismatches.length > 0 && <Chip label={mismatches.length} size="small" color="error" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
        </Tabs>
      </Paper>

      {subTab === 0 && (
        loading && !piRecon ? (
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Skeleton variant="rectangular" height={200} />
          </Paper>
        ) : !piRecon || (piRecon.items || []).length === 0 ? (
          <Paper sx={{ p: 5, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">No payment intents to reconcile</Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  <TableCell>Ledger Status</TableCell>
                  <TableCell>Matched</TableCell>
                  <TableCell>Mismatch</TableCell>
                  <TableCell>Updated</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {piRecon.items.map((item) => (
                  <TableRow key={item.id} sx={item.mismatch ? { bgcolor: tokens.colors.status.errorBg } : {}}>
                    <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.75rem' }}>{item.id.slice(0, 8)}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(item.amount_cents)}</TableCell>
                    <TableCell>
                      <Chip
                        label={item.ledger_status}
                        size="small"
                        color={item.ledger_status === 'CONFIRMED' ? 'success' : item.ledger_status === 'FAILED' ? 'error' : item.ledger_status === 'SENT' ? 'info' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip label={item.matched ? 'Yes' : 'No'} size="small" color={item.matched ? 'success' : 'default'} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      {item.mismatch ? <Chip label="MISMATCH" size="small" color="error" /> : '—'}
                    </TableCell>
                    <TableCell>{new Date(item.updated_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )
      )}

      {subTab === 1 && (
        mismatches.length === 0 ? (
          <Paper sx={{ p: 5, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">No mismatches found</Typography>
          </Paper>
        ) : (
          <Stack spacing={2}>
            {mismatches.map((item) => (
              <Paper key={item.id} sx={{ p: 2.5, borderLeft: `4px solid ${tokens.colors.status.error}` }}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                  <Stack spacing={0.5}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      Payment {item.id.slice(0, 8)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Ledger: {item.ledger_status} | Amount: {fmt(item.amount_cents)}
                    </Typography>
                    {(item.external_confirmations || []).map((ec, i) => (
                      <Typography key={i} variant="caption" color="text.secondary">
                        External: {ec.status} (ref: {ec.rail_ref || '—'})
                        {ec.resolved === 'true' && <Chip label="Resolved" size="small" color="success" sx={{ ml: 1, height: 18 }} />}
                      </Typography>
                    ))}
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    {(item.external_confirmations || []).filter(ec => ec.resolved !== 'true').map((ec) => (
                      <Button
                        key={ec.id}
                        size="small"
                        variant="outlined"
                        color="warning"
                        onClick={() => setResolveDialog(ec)}
                      >
                        Resolve
                      </Button>
                    ))}
                  </Stack>
                </Stack>
              </Paper>
            ))}
          </Stack>
        )
      )}

      <Dialog open={!!resolveDialog} onClose={() => setResolveDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Resolve Mismatch</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Resolution Note"
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResolveDialog(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleResolve} disabled={resolving || !resolveNote.trim()}>
            {resolving ? 'Resolving...' : 'Resolve'}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
