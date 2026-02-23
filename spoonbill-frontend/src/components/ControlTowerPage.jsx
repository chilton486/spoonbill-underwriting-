import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import Skeleton from '@mui/material/Skeleton'
import Tooltip from '@mui/material/Tooltip'
import Divider from '@mui/material/Divider'
import RefreshIcon from '@mui/icons-material/Refresh'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import LockIcon from '@mui/icons-material/Lock'
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import { tokens } from '../theme.js'
import { getControlTower } from '../api.js'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function FacilityCard({ facility, loading }) {
  if (loading) {
    return (
      <Paper sx={{ p: 2.5, flex: 1, minWidth: 220 }}>
        <Skeleton variant="text" width={120} />
        <Skeleton variant="text" width={80} height={36} />
        <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
          <Skeleton variant="text" width={60} />
          <Skeleton variant="text" width={60} />
        </Stack>
      </Paper>
    )
  }
  return (
    <Paper sx={{ p: 2.5, flex: 1, minWidth: 220 }}>
      <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
        {facility.facility}
      </Typography>
      <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: tokens.colors.status.success, fontSize: '1.5rem' }}>
        {fmt(facility.cash_cents)}
      </Typography>
      <Stack direction="row" spacing={2} sx={{ mt: 1.5 }}>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <LockIcon sx={{ fontSize: 14, color: tokens.colors.status.warning }} />
          <Typography variant="caption">{fmt(facility.reserved_cents)} reserved</Typography>
        </Stack>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <FlightTakeoffIcon sx={{ fontSize: 14, color: tokens.colors.status.info }} />
          <Typography variant="caption">{fmt(facility.inflight_cents)} in-flight</Typography>
        </Stack>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <CheckCircleIcon sx={{ fontSize: 14, color: tokens.colors.text.secondary }} />
          <Typography variant="caption">{fmt(facility.settled_cents)} settled</Typography>
        </Stack>
      </Stack>
      <Typography variant="caption" sx={{ color: tokens.colors.text.muted, mt: 1, display: 'block' }}>
        as of {facility.as_of ? new Date(facility.as_of).toLocaleTimeString() : '—'}
      </Typography>
    </Paper>
  )
}

function AlertItem({ alert }) {
  const severityMap = { critical: 'error', high: 'warning', medium: 'info', low: 'info' }
  const iconMap = {
    critical: <ErrorOutlineIcon />,
    high: <WarningAmberIcon />,
    medium: <InfoOutlinedIcon />,
    low: <InfoOutlinedIcon />,
  }
  return (
    <Alert
      severity={severityMap[alert.severity] || 'info'}
      icon={iconMap[alert.severity]}
      sx={{ mb: 1 }}
    >
      <Stack>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>{alert.title}</Typography>
        <Typography variant="caption" color="text.secondary">{alert.detail}</Typography>
      </Stack>
    </Alert>
  )
}

export default function ControlTowerPage() {
  const [data, setData] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getControlTower()
      setData(result)
    } catch (e) {
      setError(e.message || 'Failed to load Control Tower data')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { load() }, [load])

  const staleness = data?.freshness?.staleness_seconds
  const stalenessBadge = staleness != null
    ? staleness < 300 ? { label: 'Fresh', color: 'success' }
    : staleness < 3600 ? { label: `${Math.round(staleness / 60)}m ago`, color: 'warning' }
    : { label: `${Math.round(staleness / 3600)}h stale`, color: 'error' }
    : null

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={2} alignItems="center">
          <AccountBalanceIcon sx={{ fontSize: 28, color: tokens.colors.accent[600] }} />
          <Stack>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>Control Tower</Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Real-time liquidity, commitments, and alerts
              </Typography>
              {stalenessBadge && (
                <Chip label={stalenessBadge.label} size="small" color={stalenessBadge.color} sx={{ height: 20, fontSize: '0.7rem' }} />
              )}
            </Stack>
          </Stack>
        </Stack>
        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2 }}>
        {loading && !data ? (
          <>
            <FacilityCard loading />
            <FacilityCard loading />
          </>
        ) : (
          (data?.liquidity_by_facility || []).map((f, i) => (
            <FacilityCard key={i} facility={f} />
          ))
        )}
      </Stack>

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 200 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Approved, Not Sent
          </Typography>
          {loading && !data ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tokens.colors.status.warning }}>
              {fmt(data?.commitments?.approved_not_sent_cents)}
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 200 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Sent, Not Confirmed
          </Typography>
          {loading && !data ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tokens.colors.status.info }}>
              {fmt(data?.commitments?.sent_not_confirmed_cents)}
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 200 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            Exception Amount
          </Typography>
          {loading && !data ? (
            <Skeleton variant="text" width={80} height={32} />
          ) : (
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: data?.commitments?.exception_amount_cents > 0 ? tokens.colors.status.error : tokens.colors.text.primary }}>
              {fmt(data?.commitments?.exception_amount_cents)}
            </Typography>
          )}
        </Paper>
      </Stack>

      <Paper sx={{ p: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Can Fund Now?</Typography>
        </Stack>
        {loading && !data ? (
          <Skeleton variant="text" width={200} />
        ) : data?.can_fund_now?.value ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label="YES" color="success" size="small" />
            <Typography variant="body2">
              {fmt(data.can_fund_now.available_cents)} available for new funding
            </Typography>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label="NO" color="error" size="small" />
            <Typography variant="body2" color="error.main">
              {data?.can_fund_now?.reason || 'Insufficient funds'}
            </Typography>
          </Stack>
        )}
      </Paper>

      {(data?.alerts || []).length > 0 && (
        <Stack spacing={0}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>Alerts</Typography>
          {data.alerts.map((a, i) => <AlertItem key={i} alert={a} />)}
        </Stack>
      )}

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
        <Paper sx={{ p: 2.5, flex: 1, minWidth: 280 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>Top Practices</Typography>
          {loading && !data ? (
            <Stack spacing={1}>
              {[1,2,3].map(i => <Skeleton key={i} variant="text" width="100%" />)}
            </Stack>
          ) : (data?.top_concentrations?.practices || []).length === 0 ? (
            <Typography variant="body2" color="text.secondary">No practice data</Typography>
          ) : (
            <Stack spacing={1}>
              {data.top_concentrations.practices.map((p, i) => (
                <Stack key={p.practice_id} direction="row" justifyContent="space-between" alignItems="center">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip label={`#${i + 1}`} size="small" sx={{ height: 20, fontSize: '0.65rem', minWidth: 28, bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[700] }} />
                    <Typography variant="body2">{p.practice_name}</Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{fmt(p.total_cents)}</Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </Paper>

        <Paper sx={{ p: 2.5, flex: 1, minWidth: 280 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>Top Payers</Typography>
          {loading && !data ? (
            <Stack spacing={1}>
              {[1,2,3].map(i => <Skeleton key={i} variant="text" width="100%" />)}
            </Stack>
          ) : (data?.top_concentrations?.payers || []).length === 0 ? (
            <Typography variant="body2" color="text.secondary">No payer data</Typography>
          ) : (
            <Stack spacing={1}>
              {data.top_concentrations.payers.map((p, i) => (
                <Stack key={p.payer} direction="row" justifyContent="space-between" alignItems="center">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip label={`#${i + 1}`} size="small" sx={{ height: 20, fontSize: '0.65rem', minWidth: 28, bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[700] }} />
                    <Typography variant="body2">{p.payer}</Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{fmt(p.total_cents)} ({p.claim_count})</Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </Paper>
      </Stack>

      {data?.computed_at && (
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'right' }}>
          Computed at {new Date(data.computed_at).toLocaleString()}
        </Typography>
      )}
    </Stack>
  )
}
