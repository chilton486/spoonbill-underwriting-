import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Divider from '@mui/material/Divider'
import LinearProgress from '@mui/material/LinearProgress'
import Skeleton from '@mui/material/Skeleton'
import Tooltip from '@mui/material/Tooltip'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import BusinessIcon from '@mui/icons-material/Business'
import { tokens } from '../theme.js'

import { getPracticeCrm } from '../api.js'
import AgenticOpsPanel from './AgenticOpsPanel.jsx'

const ACTION_LABELS = {
  CLAIM_IMPORTED: 'Claim Imported',
  CLAIM_SUBMITTED: 'Claim Submitted',
  CLAIM_APPROVED: 'Claim Approved',
  CLAIM_DECLINED: 'Claim Declined',
  CLAIM_PAID: 'Claim Paid',
  CLAIM_CLOSED: 'Claim Closed',
  CLAIM_EXCEPTION: 'Payment Exception',
  PAYMENT_SENT: 'Payment Sent',
  PAYMENT_CONFIRMED: 'Payment Confirmed',
  PAYMENT_FAILED: 'Payment Failed',
  PAYMENT_RETRIED: 'Payment Retried',
  PAYMENT_CANCELLED: 'Payment Cancelled',
  ACTION_PROPOSED: 'Action Proposed',
  ACTION_EXECUTED: 'Action Executed',
  ontology_rebuilt: 'Ontology Rebuilt',
  ontology_built: 'Ontology Built',
  LIMIT_ADJUSTED: 'Limit Adjusted',
  FUNDING_PAUSED: 'Funding Paused',
  FUNDING_RESUMED: 'Funding Resumed',
  USER_INVITED: 'User Invited',
  USER_ACTIVATED: 'User Activated',
}

function formatAction(action) {
  if (ACTION_LABELS[action]) return ACTION_LABELS[action]
  return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getApiError(e) {
  if (e.status === 401) return { message: 'Session expired. Please log in again.', severity: 'warning' }
  if (e.status === 403) return { message: 'You do not have access to this practice.', severity: 'warning' }
  if (e.status === 404) return { message: 'Practice not found or CRM endpoint unavailable.', severity: 'error' }
  if (e.status === 503) return { message: 'System is updating. Please try again shortly.', severity: 'info' }
  if (e.status >= 500) return { message: 'Server error (' + e.status + '). Please try again later.', severity: 'error' }
  return { message: e.message || 'Failed to load practice data', severity: 'error' }
}

function KpiCard({ label, value, sub, color, loading }) {
  return (
    <Paper sx={{ p: 2, flex: 1, minWidth: 150 }}>
      <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>{label}</Typography>
      {loading ? (
        <Skeleton variant="text" width={80} height={32} />
      ) : (
        <Typography variant="h5" sx={{ mt: 0.5, fontWeight: 700, color: color || tokens.colors.text.primary }}>{value}</Typography>
      )}
      {sub && <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>{sub}</Typography>}
    </Paper>
  )
}

function SkeletonRows({ rows = 5, cols = 5 }) {
  return (
    <TableBody>
      {Array.from({ length: rows }).map((_, r) => (
        <TableRow key={r}>
          {Array.from({ length: cols }).map((_, c) => (
            <TableCell key={c}><Skeleton variant="text" width={60 + Math.random() * 40} /></TableCell>
          ))}
        </TableRow>
      ))}
    </TableBody>
  )
}

const ACTION_CHIP_COLOR = {
  CLAIM_APPROVED: 'success',
  CLAIM_PAID: 'success',
  PAYMENT_CONFIRMED: 'success',
  CLAIM_DECLINED: 'error',
  PAYMENT_FAILED: 'error',
  CLAIM_EXCEPTION: 'error',
  PAYMENT_CANCELLED: 'error',
  CLAIM_SUBMITTED: 'info',
  PAYMENT_SENT: 'info',
  ACTION_PROPOSED: 'warning',
  ACTION_EXECUTED: 'warning',
  LIMIT_ADJUSTED: 'warning',
}

export default function PracticeRecord({ practiceId, onBack }) {
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [apiError, setApiError] = React.useState(null)
  const [tab, setTab] = React.useState(0)

  const loadData = React.useCallback(() => {
    let mounted = true
    setLoading(true)
    setApiError(null)
    getPracticeCrm(practiceId).then((d) => {
      if (mounted) setData(d)
    }).catch((e) => {
      if (mounted) setApiError(getApiError(e))
    }).finally(() => {
      if (mounted) setLoading(false)
    })
    return () => { mounted = false }
  }, [practiceId])

  React.useEffect(() => { loadData() }, [loadData])

  const practice = data?.practice
  const kpis = data?.kpis || {}
  const timeline = data?.timeline || []
  const integrations = data?.integrations || []
  const recent_exceptions = data?.recent_exceptions || []
  const utilization = kpis.utilization_pct || 0

  return (
    <Stack spacing={3}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} size="small">Back</Button>
        {loading && !practice ? (
          <Skeleton variant="text" width={200} height={32} />
        ) : practice ? (
          <>
            <BusinessIcon sx={{ color: tokens.colors.accent[500], fontSize: 24 }} />
            <Typography variant="h5" sx={{ fontWeight: 700 }}>{practice.name}</Typography>
            <Chip
              label={practice.status}
              size="small"
              color={practice.status === 'ACTIVE' ? 'success' : practice.status === 'SUSPENDED' ? 'error' : 'default'}
            />
            <Typography variant="caption" sx={{ color: tokens.colors.text.muted }}>ID: {practiceId}</Typography>
          </>
        ) : null}
      </Stack>

      {apiError && (
        <Alert severity={apiError.severity} onClose={() => setApiError(null)}>
          {apiError.message}
        </Alert>
      )}

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2 }}>
        <KpiCard label="Total Claims" value={kpis.total_claims || 0} loading={loading && !data} />
        <KpiCard label="Total Funded" value={fmt(kpis.total_funded_cents)} color={tokens.colors.status.success} loading={loading && !data} />
        <KpiCard label="Outstanding" value={fmt(kpis.funded_outstanding_cents)} color={tokens.colors.status.warning} loading={loading && !data} />
        <KpiCard label="Funding Limit" value={fmt(kpis.funding_limit_cents)} loading={loading && !data} />
        <KpiCard label="Exceptions" value={kpis.exception_count || 0} color={kpis.exception_count > 0 ? tokens.colors.status.error : undefined} loading={loading && !data} />
      </Stack>

      {kpis.funding_limit_cents > 0 && (
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2">Funding Utilization</Typography>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{utilization}%</Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={Math.min(utilization, 100)}
            sx={{
              height: 8, borderRadius: 4,
              bgcolor: tokens.colors.surfaceHover,
              '& .MuiLinearProgress-bar': {
                borderRadius: 4,
                bgcolor: utilization >= 90 ? tokens.colors.status.error : utilization >= 70 ? tokens.colors.status.warning : tokens.colors.status.success,
              },
            }}
          />
        </Paper>
      )}

      <Paper sx={{ px: 0.5, py: 0 }}>
        <Tabs value={tab} onChange={(e, v) => setTab(v)}>
          <Tab label="Overview" />
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Timeline</span>
              {timeline.length > 0 && <Chip label={timeline.length} size="small" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
          <Tab label="Integrations" />
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Exceptions</span>
              {recent_exceptions.length > 0 && <Chip label={recent_exceptions.length} size="small" color="error" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
          <Tab label="Actions" />
        </Tabs>
      </Paper>

      {tab === 0 && (
        <Stack spacing={3}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>Practice Details</Typography>
            {loading && !data ? (
              <Stack spacing={1}>
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="text" width={300} />)}
              </Stack>
            ) : practice ? (
              <Stack spacing={1.5}>
                <Stack direction="row" spacing={8}>
                  <Box>
                    <Typography variant="caption">Practice Name</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>{practice.name}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption">Status</Typography>
                    <Box sx={{ mt: 0.5 }}>
                      <Chip label={practice.status} size="small" color={practice.status === 'ACTIVE' ? 'success' : 'default'} />
                    </Box>
                  </Box>
                  <Box>
                    <Typography variant="caption">Practice ID</Typography>
                    <Typography variant="body1" sx={{ fontFamily: tokens.typography.mono, fontSize: '0.85rem' }}>#{practiceId}</Typography>
                  </Box>
                </Stack>
                {practice.created_at && (
                  <Box>
                    <Typography variant="caption">Onboarded</Typography>
                    <Typography variant="body2">{new Date(practice.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</Typography>
                  </Box>
                )}
              </Stack>
            ) : null}
          </Paper>

          <Stack direction="row" spacing={2}>
            <Paper sx={{ p: 2, flex: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Integrations</Typography>
              {integrations.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No integrations configured</Typography>
              ) : (
                <Stack spacing={0.5}>
                  {integrations.map((ic) => (
                    <Stack key={ic.id} direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2">{ic.provider}</Typography>
                      <Chip label={ic.status} size="small" color={ic.status === 'ACTIVE' ? 'success' : ic.status === 'ERROR' ? 'error' : 'default'} />
                    </Stack>
                  ))}
                </Stack>
              )}
            </Paper>
            <Paper sx={{ p: 2, flex: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Recent Activity</Typography>
              {timeline.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No recent activity</Typography>
              ) : (
                <Stack spacing={0.5}>
                  {timeline.slice(0, 5).map((event) => (
                    <Stack key={event.id} direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2">{formatAction(event.action)}</Typography>
                      <Typography variant="caption">{event.created_at ? new Date(event.created_at).toLocaleDateString() : ''}</Typography>
                    </Stack>
                  ))}
                </Stack>
              )}
            </Paper>
          </Stack>
        </Stack>
      )}

      {tab === 1 && (
        <Paper sx={{ p: 0 }}>
          {loading && !data ? (
            <Stack spacing={0} divider={<Divider />}>
              {Array.from({ length: 6 }).map((_, i) => (
                <Stack key={i} direction="row" spacing={2} sx={{ px: 3, py: 1.5 }} alignItems="center">
                  <Skeleton variant="rounded" width={120} height={26} />
                  <Skeleton variant="text" width={200} />
                  <Box sx={{ flex: 1 }} />
                  <Skeleton variant="text" width={100} />
                </Stack>
              ))}
            </Stack>
          ) : timeline.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No timeline events</Typography>
            </Box>
          ) : (
            <Stack divider={<Divider />}>
              {timeline.map((event) => (
                <Stack key={event.id} direction="row" spacing={2} sx={{ px: 3, py: 1.5 }} alignItems="center">
                  <Chip
                    label={formatAction(event.action)}
                    size="small"
                    variant="outlined"
                    color={ACTION_CHIP_COLOR[event.action] || 'default'}
                    sx={{ minWidth: 140 }}
                  />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {event.from_status && event.to_status ? event.from_status + ' \u2192 ' + event.to_status : ''}
                    {event.claim_id ? ' (Claim #' + event.claim_id + ')' : ''}
                  </Typography>
                  <Typography variant="caption">{event.created_at ? new Date(event.created_at).toLocaleString() : ''}</Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </Paper>
      )}

      {tab === 2 && (
        <Stack spacing={2}>
          {loading && !data ? (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Provider</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Last Synced</TableCell>
                  </TableRow>
                </TableHead>
                <SkeletonRows rows={3} cols={3} />
              </Table>
            </TableContainer>
          ) : integrations.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No integrations configured for this practice</Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Provider</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Last Synced</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {integrations.map((ic) => (
                    <TableRow key={ic.id}>
                      <TableCell sx={{ fontWeight: 500 }}>{ic.provider}</TableCell>
                      <TableCell>
                        <Chip
                          label={ic.status}
                          size="small"
                          color={ic.status === 'ACTIVE' ? 'success' : ic.status === 'ERROR' ? 'error' : 'default'}
                        />
                      </TableCell>
                      <TableCell>{ic.last_synced_at ? new Date(ic.last_synced_at).toLocaleString() : 'Never'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}

      {tab === 3 && (
        <Stack spacing={2}>
          {loading && !data ? (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Claim</TableCell>
                    <TableCell>Payer</TableCell>
                    <TableCell>Amount</TableCell>
                    <TableCell>Code</TableCell>
                    <TableCell>Updated</TableCell>
                  </TableRow>
                </TableHead>
                <SkeletonRows rows={3} cols={5} />
              </Table>
            </TableContainer>
          ) : recent_exceptions.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No recent exceptions for this practice</Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Claim</TableCell>
                    <TableCell>Payer</TableCell>
                    <TableCell align="right">Amount</TableCell>
                    <TableCell>Code</TableCell>
                    <TableCell>Updated</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recent_exceptions.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.8rem' }}>#{c.id}</TableCell>
                      <TableCell>{c.payer}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(c.amount_cents)}</TableCell>
                      <TableCell><Chip label={c.exception_code || 'N/A'} size="small" color="error" /></TableCell>
                      <TableCell>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}

      {tab === 4 && (
        <AgenticOpsPanel practiceId={practiceId} />
      )}
    </Stack>
  )
}
