import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TableSortLabel from '@mui/material/TableSortLabel'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Skeleton from '@mui/material/Skeleton'
import Tooltip from '@mui/material/Tooltip'
import RefreshIcon from '@mui/icons-material/Refresh'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import SendIcon from '@mui/icons-material/Send'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ScheduleIcon from '@mui/icons-material/Schedule'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import { tokens } from '../theme.js'

import {
  getEconomicsSummary,
  getEconomicsExposure,
  getEconomicsPaymentIntents,
  getEconomicsExceptions,
} from '../api.js'

function fmt(cents) {
  if (cents == null) return '$0.00'
  return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getApiError(e) {
  if (e.status === 401) return { message: 'Session expired. Please log in again.', severity: 'warning' }
  if (e.status === 403) return { message: 'You do not have access to economics data.', severity: 'warning' }
  if (e.status === 404) return { message: 'Economics endpoint not found. The backend may need updating.', severity: 'error' }
  if (e.status === 503) return { message: 'System is updating. Please try again in a moment.', severity: 'info' }
  if (e.status >= 500) return { message: 'Server error (' + e.status + '). Please try again later.', severity: 'error' }
  return { message: e.message || 'Failed to load economics data', severity: 'error' }
}

function LiquidityCard({ label, value, icon: Icon, color, loading }) {
  return (
    <Paper sx={{ p: 2.5, flex: 1, minWidth: 170 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: tokens.colors.text.muted }}>
            {label}
          </Typography>
          {loading ? (
            <Skeleton variant="text" width={100} height={36} />
          ) : (
            <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: color || tokens.colors.text.primary, fontSize: '1.5rem' }}>
              {value}
            </Typography>
          )}
        </Box>
        {Icon && (
          <Box sx={{ p: 0.75, borderRadius: tokens.radius.sm, bgcolor: color ? color + '14' : tokens.colors.surfaceHover }}>
            <Icon sx={{ fontSize: 20, color: color || tokens.colors.text.muted }} />
          </Box>
        )}
      </Stack>
    </Paper>
  )
}

function SkeletonTable({ rows = 5, cols = 6 }) {
  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {Array.from({ length: cols }).map((_, i) => (
              <TableCell key={i}><Skeleton variant="text" width={80} /></TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {Array.from({ length: rows }).map((_, r) => (
            <TableRow key={r}>
              {Array.from({ length: cols }).map((_, c) => (
                <TableCell key={c}><Skeleton variant="text" width={60 + Math.random() * 40} /></TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}

function EmptyState({ message }) {
  return (
    <Paper sx={{ p: 5, textAlign: 'center' }}>
      <Typography variant="body2" color="text.secondary">{message}</Typography>
    </Paper>
  )
}

const PI_STATUSES = ['All', 'QUEUED', 'SENT', 'CONFIRMED', 'FAILED']

const STATUS_CHIP_COLOR = {
  CONFIRMED: 'success',
  FAILED: 'error',
  SENT: 'info',
  QUEUED: 'warning',
}

export default function EconomicsTab() {
  const [liquidity, setLiquidity] = React.useState(null)
  const [exposure, setExposure] = React.useState(null)
  const [piBoard, setPiBoard] = React.useState(null)
  const [exceptions, setExceptions] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [apiError, setApiError] = React.useState(null)
  const [subTab, setSubTab] = React.useState(0)
  const [piStatusFilter, setPiStatusFilter] = React.useState('All')
  const [exposureSort, setExposureSort] = React.useState({ field: 'total_funded_cents', dir: 'desc' })

  const loadAll = React.useCallback(async () => {
    setLoading(true)
    setApiError(null)
    try {
      const [liq, exp, pi, exc] = await Promise.all([
        getEconomicsSummary(),
        getEconomicsExposure(),
        getEconomicsPaymentIntents({ status: piStatusFilter === 'All' ? undefined : piStatusFilter }),
        getEconomicsExceptions(),
      ])
      setLiquidity(liq)
      setExposure(exp)
      setPiBoard(pi)
      setExceptions(exc)
    } catch (e) {
      setApiError(getApiError(e))
    } finally {
      setLoading(false)
    }
  }, [piStatusFilter])

  React.useEffect(() => { loadAll() }, [loadAll])

  const sortedExposure = React.useMemo(() => {
    if (!exposure?.by_practice) return []
    const arr = [...exposure.by_practice]
    arr.sort((a, b) => {
      const aVal = a[exposureSort.field] ?? 0
      const bVal = b[exposureSort.field] ?? 0
      return exposureSort.dir === 'asc' ? aVal - bVal : bVal - aVal
    })
    return arr
  }, [exposure, exposureSort])

  const handleExposureSort = (field) => {
    setExposureSort((prev) => ({
      field,
      dir: prev.field === field && prev.dir === 'desc' ? 'asc' : 'desc',
    }))
  }

  const exceptionCount = React.useMemo(() => {
    if (!exceptions) return 0
    return (exceptions.exception_claims?.length || 0) + (exceptions.failed_payments?.length || 0)
  }, [exceptions])

  return (
    <Stack spacing={3}>
      {apiError && (
        <Alert severity={apiError.severity} onClose={() => setApiError(null)}>
          {apiError.message}
        </Alert>
      )}

      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>Liquidity Control Tower</Typography>
          <Typography variant="body2" color="text.secondary">Real-time view of cash positions, exposure, and payment pipeline</Typography>
        </Stack>
        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={loadAll} disabled={loading}>
          Refresh
        </Button>
      </Stack>

      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2 }}>
        <LiquidityCard label="Available Cash" value={fmt(liquidity?.available_cash_cents)} icon={AccountBalanceIcon} color={tokens.colors.status.success} loading={loading && !liquidity} />
        <LiquidityCard label="Reserved (Queued)" value={fmt(liquidity?.reserved_cents)} icon={ScheduleIcon} color={tokens.colors.status.warning} loading={loading && !liquidity} />
        <LiquidityCard label="In-Flight (Sent)" value={fmt(liquidity?.in_flight_cents)} icon={SendIcon} color={tokens.colors.status.info} loading={loading && !liquidity} />
        <LiquidityCard label="Settled" value={fmt(liquidity?.settled_cents)} icon={CheckCircleOutlineIcon} color={tokens.colors.text.secondary} loading={loading && !liquidity} />
        <LiquidityCard label="Total Payable" value={fmt(liquidity?.total_practice_payable_cents)} icon={TrendingUpIcon} loading={loading && !liquidity} />
      </Stack>

      <Paper sx={{ px: 0.5, py: 0 }}>
        <Tabs value={subTab} onChange={(e, v) => setSubTab(v)}>
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Funding Pipeline</span>
              {piBoard && <Chip label={piBoard.total || 0} size="small" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
          <Tab label="Exposure" />
          <Tab label={
            <Stack direction="row" spacing={0.75} alignItems="center">
              <span>Exceptions</span>
              {exceptionCount > 0 && <Chip label={exceptionCount} size="small" color="error" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />}
            </Stack>
          } />
        </Tabs>
      </Paper>

      {subTab === 0 && (
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} alignItems="center">
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Status</InputLabel>
              <Select value={piStatusFilter} label="Status" onChange={(e) => setPiStatusFilter(e.target.value)}>
                {PI_STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </Select>
            </FormControl>
            {piBoard && (
              <Stack direction="row" spacing={1}>
                {Object.entries(piBoard.status_counts || {}).map(([k, v]) => (
                  <Chip
                    key={k}
                    label={k + ': ' + v}
                    size="small"
                    variant={piStatusFilter === k ? 'filled' : 'outlined'}
                    color={STATUS_CHIP_COLOR[k] || 'default'}
                    onClick={() => setPiStatusFilter(piStatusFilter === k ? 'All' : k)}
                    sx={{ cursor: 'pointer' }}
                  />
                ))}
              </Stack>
            )}
          </Stack>

          {loading && !piBoard ? (
            <SkeletonTable rows={8} cols={6} />
          ) : !piBoard || (piBoard.items || []).length === 0 ? (
            <EmptyState message="No payment intents found for the selected filter." />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Practice</TableCell>
                    <TableCell align="right">Amount</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Provider</TableCell>
                    <TableCell>Created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {piBoard.items.map((pi) => (
                    <TableRow key={pi.id}>
                      <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.75rem' }}>{pi.id.slice(0, 8)}</TableCell>
                      <TableCell>{pi.practice_name}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(pi.amount_cents)}</TableCell>
                      <TableCell>
                        <Chip label={pi.status} size="small" color={STATUS_CHIP_COLOR[pi.status] || 'default'} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>{pi.provider}</Typography>
                      </TableCell>
                      <TableCell>{new Date(pi.created_at).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {piBoard && piBoard.total > (piBoard.items?.length || 0) && (
            <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
              Showing {piBoard.items?.length || 0} of {piBoard.total} payment intents
            </Typography>
          )}
        </Stack>
      )}

      {subTab === 1 && (
        <Stack spacing={3}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" sx={{ fontWeight: 600 }}>Exposure by Practice</Typography>
            <Typography variant="caption" color="text.secondary">
              {sortedExposure.length} practice{sortedExposure.length !== 1 ? 's' : ''} with active funding
            </Typography>
          </Stack>

          {loading && !exposure ? (
            <SkeletonTable rows={5} cols={4} />
          ) : sortedExposure.length === 0 ? (
            <EmptyState message="No exposure data available." />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Practice</TableCell>
                    <TableCell>ID</TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={exposureSort.field === 'payment_count'}
                        direction={exposureSort.field === 'payment_count' ? exposureSort.dir : 'desc'}
                        onClick={() => handleExposureSort('payment_count')}
                      >
                        Payments
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={exposureSort.field === 'total_funded_cents'}
                        direction={exposureSort.field === 'total_funded_cents' ? exposureSort.dir : 'desc'}
                        onClick={() => handleExposureSort('total_funded_cents')}
                      >
                        Total Funded
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedExposure.map((row) => (
                    <TableRow key={row.practice_id}>
                      <TableCell sx={{ fontWeight: 500 }}>{row.practice_name}</TableCell>
                      <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.75rem', color: tokens.colors.text.muted }}>#{row.practice_id}</TableCell>
                      <TableCell align="right">{row.payment_count}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(row.total_funded_cents)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          <Typography variant="h6" sx={{ fontWeight: 600 }}>Aging Buckets</Typography>
          <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
            {loading && !exposure ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Paper key={i} sx={{ p: 2, minWidth: 150, textAlign: 'center' }}>
                  <Skeleton variant="text" width={60} sx={{ mx: 'auto' }} />
                  <Skeleton variant="text" width={40} height={32} sx={{ mx: 'auto' }} />
                  <Skeleton variant="text" width={80} sx={{ mx: 'auto' }} />
                </Paper>
              ))
            ) : (
              (exposure?.aging_buckets || []).map((b) => (
                <Paper key={b.bucket} sx={{ p: 2, minWidth: 150, textAlign: 'center', flex: 1 }}>
                  <Typography variant="caption" sx={{ textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>{b.bucket}</Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5 }}>{b.claim_count}</Typography>
                  <Typography variant="body2" sx={{ color: tokens.colors.text.secondary }}>{fmt(b.total_cents)}</Typography>
                </Paper>
              ))
            )}
          </Stack>

          <Typography variant="h6" sx={{ fontWeight: 600 }}>Top Payers (Concentration)</Typography>
          {loading && !exposure ? (
            <SkeletonTable rows={5} cols={3} />
          ) : (exposure?.concentration || []).length === 0 ? (
            <EmptyState message="No payer concentration data available." />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Payer</TableCell>
                    <TableCell align="right">Claims</TableCell>
                    <TableCell align="right">Total</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {exposure.concentration.map((row, i) => (
                    <TableRow key={row.payer}>
                      <TableCell>
                        <Stack direction="row" spacing={1} alignItems="center">
                          {i < 3 && (
                            <Chip label={'#' + (i + 1)} size="small" sx={{ height: 20, fontSize: '0.65rem', minWidth: 28, bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[700] }} />
                          )}
                          <span>{row.payer}</span>
                        </Stack>
                      </TableCell>
                      <TableCell align="right">{row.claim_count}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(row.total_cents)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}

      {subTab === 2 && (
        <Stack spacing={3}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" sx={{ fontWeight: 600 }}>Exception Claims</Typography>
            <Chip
              label={(exceptions?.exception_claims?.length || 0) + ' exception' + ((exceptions?.exception_claims?.length || 0) !== 1 ? 's' : '')}
              size="small"
              color={(exceptions?.exception_claims?.length || 0) > 0 ? 'error' : 'default'}
            />
          </Stack>

          {loading && !exceptions ? (
            <SkeletonTable rows={4} cols={6} />
          ) : (exceptions?.exception_claims || []).length === 0 ? (
            <EmptyState message="No exception claims. All claims are processing normally." />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Claim</TableCell>
                    <TableCell>Practice</TableCell>
                    <TableCell>Payer</TableCell>
                    <TableCell align="right">Amount</TableCell>
                    <TableCell>Code</TableCell>
                    <TableCell>Updated</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {exceptions.exception_claims.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.8rem' }}>{c.claim_token}</TableCell>
                      <TableCell>
                        <Tooltip title={'Practice ID: ' + c.practice_id}>
                          <span>#{c.practice_id}</span>
                        </Tooltip>
                      </TableCell>
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

          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6" sx={{ fontWeight: 600 }}>Failed Payments</Typography>
            <Chip
              label={(exceptions?.failed_payments?.length || 0) + ' failed'}
              size="small"
              color={(exceptions?.failed_payments?.length || 0) > 0 ? 'error' : 'default'}
            />
          </Stack>

          {loading && !exceptions ? (
            <SkeletonTable rows={3} cols={6} />
          ) : (exceptions?.failed_payments || []).length === 0 ? (
            <EmptyState message="No failed payments." />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Payment ID</TableCell>
                    <TableCell>Claim</TableCell>
                    <TableCell align="right">Amount</TableCell>
                    <TableCell>Failure Code</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Created</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {exceptions.failed_payments.map((fp) => (
                    <TableRow key={fp.id}>
                      <TableCell sx={{ fontFamily: tokens.typography.mono, fontSize: '0.75rem' }}>{fp.id.slice(0, 8)}</TableCell>
                      <TableCell>#{fp.claim_id}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(fp.amount_cents)}</TableCell>
                      <TableCell><Chip label={fp.failure_code || 'N/A'} size="small" color="error" /></TableCell>
                      <TableCell sx={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <Tooltip title={fp.failure_message || ''}>
                          <span>{fp.failure_message || '-'}</span>
                        </Tooltip>
                      </TableCell>
                      <TableCell>{fp.created_at ? new Date(fp.created_at).toLocaleDateString() : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}
    </Stack>
  )
}
