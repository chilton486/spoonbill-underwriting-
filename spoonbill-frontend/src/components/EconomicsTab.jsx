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
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import RefreshIcon from '@mui/icons-material/Refresh'
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

function LiquidityCard({ label, value, color, sub }) {
  return (
    <Paper sx={{ p: 2.5, flex: 1, minWidth: 180 }}>
      <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</Typography>
      <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: color || tokens.colors.text.primary }}>{value}</Typography>
      {sub && <Typography variant="caption" sx={{ mt: 0.5, display: 'block' }}>{sub}</Typography>}
    </Paper>
  )
}

const PI_STATUSES = ['All', 'QUEUED', 'SENT', 'CONFIRMED', 'FAILED']

export default function EconomicsTab() {
  const [liquidity, setLiquidity] = React.useState(null)
  const [exposure, setExposure] = React.useState(null)
  const [piBoard, setPiBoard] = React.useState(null)
  const [exceptions, setExceptions] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [subTab, setSubTab] = React.useState(0)
  const [piStatusFilter, setPiStatusFilter] = React.useState('All')

  const loadAll = React.useCallback(async () => {
    setLoading(true)
    setError(null)
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
      setError(e.message || 'Failed to load economics data')
    } finally {
      setLoading(false)
    }
  }, [piStatusFilter])

  React.useEffect(() => { loadAll() }, [loadAll])

  if (loading && !liquidity) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress size={32} />
      </Box>
    )
  }

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h5" sx={{ fontWeight: 700 }}>Economics</Typography>
        <Button size="small" startIcon={<RefreshIcon />} onClick={loadAll} disabled={loading}>Refresh</Button>
      </Stack>

      {liquidity && (
        <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2 }}>
          <LiquidityCard label="Available Cash" value={fmt(liquidity.available_cash_cents)} color={tokens.colors.status.success} />
          <LiquidityCard label="Reserved (Queued)" value={fmt(liquidity.reserved_cents)} color={tokens.colors.status.warning} />
          <LiquidityCard label="In-Flight (Sent)" value={fmt(liquidity.in_flight_cents)} color={tokens.colors.status.info} />
          <LiquidityCard label="Settled" value={fmt(liquidity.settled_cents)} color={tokens.colors.text.secondary} />
          <LiquidityCard label="Total Payable" value={fmt(liquidity.total_practice_payable_cents)} />
        </Stack>
      )}

      <Paper sx={{ px: 0.5, py: 0 }}>
        <Tabs value={subTab} onChange={(e, v) => setSubTab(v)}>
          <Tab label="Funding Pipeline" />
          <Tab label="Exposure" />
          <Tab label="Exceptions" />
        </Tabs>
      </Paper>

      {subTab === 0 && piBoard && (
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} alignItems="center">
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Status</InputLabel>
              <Select value={piStatusFilter} label="Status" onChange={(e) => setPiStatusFilter(e.target.value)}>
                {PI_STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </Select>
            </FormControl>
            <Stack direction="row" spacing={1}>
              {Object.entries(piBoard.status_counts || {}).map(([k, v]) => (
                <Chip key={k} label={`${k}: ${v}`} size="small" variant="outlined" />
              ))}
            </Stack>
          </Stack>

          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Practice</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Provider</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(piBoard.items || []).map((pi) => (
                  <TableRow key={pi.id}>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{pi.id.slice(0, 8)}</TableCell>
                    <TableCell>{pi.practice_name}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{fmt(pi.amount_cents)}</TableCell>
                    <TableCell>
                      <Chip
                        label={pi.status}
                        size="small"
                        color={pi.status === 'CONFIRMED' ? 'success' : pi.status === 'FAILED' ? 'error' : pi.status === 'SENT' ? 'info' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>{pi.provider}</TableCell>
                    <TableCell>{new Date(pi.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
                {(piBoard.items || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>No payment intents found</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      )}

      {subTab === 1 && exposure && (
        <Stack spacing={3}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>Exposure by Practice</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Practice</TableCell>
                  <TableCell>ID</TableCell>
                  <TableCell align="right">Payments</TableCell>
                  <TableCell align="right">Total Funded</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(exposure.by_practice || []).map((row) => (
                  <TableRow key={row.practice_id}>
                    <TableCell>{row.practice_name}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>#{row.practice_id}</TableCell>
                    <TableCell align="right">{row.payment_count}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(row.total_funded_cents)}</TableCell>
                  </TableRow>
                ))}
                {(exposure.by_practice || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>No exposure data</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <Typography variant="h6" sx={{ fontWeight: 600 }}>Aging Buckets</Typography>
          <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
            {(exposure.aging_buckets || []).map((b) => (
              <Paper key={b.bucket} sx={{ p: 2, minWidth: 140, textAlign: 'center' }}>
                <Typography variant="caption" sx={{ textTransform: 'uppercase' }}>{b.bucket}</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5 }}>{b.claim_count}</Typography>
                <Typography variant="body2">{fmt(b.total_cents)}</Typography>
              </Paper>
            ))}
          </Stack>

          <Typography variant="h6" sx={{ fontWeight: 600 }}>Top Payers (Concentration)</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Payer</TableCell>
                  <TableCell>Claims</TableCell>
                  <TableCell>Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(exposure.concentration || []).map((row) => (
                  <TableRow key={row.payer}>
                    <TableCell>{row.payer}</TableCell>
                    <TableCell>{row.claim_count}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{fmt(row.total_cents)}</TableCell>
                  </TableRow>
                ))}
                {(exposure.concentration || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>No concentration data</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      )}

      {subTab === 2 && exceptions && (
        <Stack spacing={3}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>Exception Claims</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Claim</TableCell>
                  <TableCell>Practice</TableCell>
                  <TableCell>Payer</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Code</TableCell>
                  <TableCell>Updated</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(exceptions.exception_claims || []).map((c) => (
                  <TableRow key={c.id}>
                    <TableCell sx={{ fontFamily: 'monospace' }}>{c.claim_token}</TableCell>
                    <TableCell>{c.practice_id}</TableCell>
                    <TableCell>{c.payer}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{fmt(c.amount_cents)}</TableCell>
                    <TableCell><Chip label={c.exception_code || 'N/A'} size="small" color="error" /></TableCell>
                    <TableCell>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : '-'}</TableCell>
                  </TableRow>
                ))}
                {(exceptions.exception_claims || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>No exceptions</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <Typography variant="h6" sx={{ fontWeight: 600 }}>Failed Payments</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Payment ID</TableCell>
                  <TableCell>Claim</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Failure Code</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(exceptions.failed_payments || []).map((fp) => (
                  <TableRow key={fp.id}>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{fp.id.slice(0, 8)}</TableCell>
                    <TableCell>{fp.claim_id}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{fmt(fp.amount_cents)}</TableCell>
                    <TableCell><Chip label={fp.failure_code || 'N/A'} size="small" color="error" /></TableCell>
                    <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fp.failure_message || '-'}</TableCell>
                    <TableCell>{fp.created_at ? new Date(fp.created_at).toLocaleDateString() : '-'}</TableCell>
                  </TableRow>
                ))}
                {(exceptions.failed_payments || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>No failed payments</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      )}
    </Stack>
  )
}
