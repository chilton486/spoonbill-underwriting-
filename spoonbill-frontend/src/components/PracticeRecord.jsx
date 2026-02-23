import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
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
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import { tokens } from '../theme.js'

import { getPracticeCrm } from '../api.js'
import AgenticOpsPanel from './AgenticOpsPanel.jsx'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function KpiCard({ label, value, sub, color }) {
  return (
    <Paper sx={{ p: 2, flex: 1, minWidth: 150 }}>
      <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</Typography>
      <Typography variant="h5" sx={{ mt: 0.5, fontWeight: 700, color: color || tokens.colors.text.primary }}>{value}</Typography>
      {sub && <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>{sub}</Typography>}
    </Paper>
  )
}

export default function PracticeRecord({ practiceId, onBack }) {
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [tab, setTab] = React.useState(0)

  React.useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)
    getPracticeCrm(practiceId).then((d) => {
      if (mounted) setData(d)
    }).catch((e) => {
      if (mounted) setError(e.message || 'Failed to load practice data')
    }).finally(() => {
      if (mounted) setLoading(false)
    })
    return () => { mounted = false }
  }, [practiceId])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress size={32} />
      </Box>
    )
  }

  if (error) {
    return (
      <Stack spacing={2}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} size="small">Back to Practices</Button>
        <Alert severity="error">{error}</Alert>
      </Stack>
    )
  }

  if (!data) return null

  const { practice, kpis, timeline, integrations, recent_exceptions } = data
  const utilization = kpis.utilization_pct || 0

  return (
    <Stack spacing={3}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} size="small">Back</Button>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>{practice.name}</Typography>
        <Chip
          label={practice.status}
          size="small"
          color={practice.status === 'ACTIVE' ? 'success' : 'default'}
        />
      </Stack>

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2 }}>
        <KpiCard label="Total Claims" value={kpis.total_claims || 0} />
        <KpiCard label="Total Funded" value={fmt(kpis.total_funded_cents)} color={tokens.colors.status.success} />
        <KpiCard label="Outstanding" value={fmt(kpis.funded_outstanding_cents)} color={tokens.colors.status.warning} />
        <KpiCard label="Funding Limit" value={fmt(kpis.funding_limit_cents)} />
        <KpiCard label="Exceptions" value={kpis.exception_count || 0} color={kpis.exception_count > 0 ? tokens.colors.status.error : undefined} />
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
          <Tab label="Timeline" />
          <Tab label="Integrations" />
          <Tab label="Exceptions" />
          <Tab label="Recommendations" />
        </Tabs>
      </Paper>

      {tab === 0 && (
        <Paper sx={{ p: 0 }}>
          {(timeline || []).length === 0 ? (
            <Box sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No timeline events</Typography>
            </Box>
          ) : (
            <Stack divider={<Divider />}>
              {timeline.map((event) => (
                <Stack key={event.id} direction="row" spacing={2} sx={{ px: 3, py: 1.5 }} alignItems="center">
                  <Chip label={event.action} size="small" variant="outlined" sx={{ minWidth: 120 }} />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {event.from_status && event.to_status ? `${event.from_status} → ${event.to_status}` : ''}
                    {event.claim_id ? ` (Claim #${event.claim_id})` : ''}
                  </Typography>
                  <Typography variant="caption">{event.created_at ? new Date(event.created_at).toLocaleString() : ''}</Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </Paper>
      )}

      {tab === 1 && (
        <Stack spacing={2}>
          {(integrations || []).length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No integrations configured</Typography>
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
                      <TableCell>{ic.provider}</TableCell>
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

      {tab === 2 && (
        <Stack spacing={2}>
          {(recent_exceptions || []).length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">No recent exceptions</Typography>
            </Paper>
          ) : (
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
                <TableBody>
                  {recent_exceptions.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>#{c.id}</TableCell>
                      <TableCell>{c.payer}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{fmt(c.amount_cents)}</TableCell>
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

      {tab === 3 && (
        <AgenticOpsPanel practiceId={practiceId} />
      )}
    </Stack>
  )
}
