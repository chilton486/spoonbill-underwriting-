import * as React from 'react'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import LinearProgress from '@mui/material/LinearProgress'
import Divider from '@mui/material/Divider'
import Tooltip from '@mui/material/Tooltip'

function formatMoney(value) {
  return `$${(value ?? 0).toLocaleString()}`
}

function MetricRow({ label, value, color, tooltip, highlight }) {
  const content = (
    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2, py: 0.5 }}>
      <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.75)', fontSize: '0.85rem' }}>{label}</Typography>
      <Typography 
        variant="body2" 
        sx={{ 
          fontWeight: 700, 
          color: highlight ? color : 'inherit',
          fontSize: '0.85rem'
        }}
      >
        {formatMoney(value)}
      </Typography>
    </Stack>
  )

  if (tooltip) {
    return <Tooltip title={tooltip} placement="left" arrow>{content}</Tooltip>
  }
  return content
}

function CapitalBar({ total, available, deployed, pending }) {
  if (!total || total === 0) return null

  const availablePercent = ((available || 0) / total) * 100
  const deployedPercent = ((deployed || 0) / total) * 100
  const pendingPercent = ((pending || 0) / total) * 100

  return (
    <Stack spacing={1}>
      <Box sx={{ position: 'relative', height: 24, borderRadius: 1, overflow: 'hidden', backgroundColor: 'rgba(100,116,139,0.2)' }}>
        {/* Available capital (green) */}
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${availablePercent}%`,
            backgroundColor: '#34d399',
            transition: 'width 0.5s ease'
          }}
        />
        {/* Deployed/Pending capital (orange) */}
        <Box
          sx={{
            position: 'absolute',
            left: `${availablePercent}%`,
            top: 0,
            height: '100%',
            width: `${deployedPercent}%`,
            backgroundColor: '#fb923c',
            transition: 'all 0.5s ease'
          }}
        />
      </Box>
      <Stack direction="row" spacing={2} sx={{ justifyContent: 'center' }}>
        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#34d399' }} />
          <Typography variant="caption" sx={{ color: 'rgba(226,232,240,0.7)', fontSize: '0.7rem' }}>Available</Typography>
        </Stack>
        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#fb923c' }} />
          <Typography variant="caption" sx={{ color: 'rgba(226,232,240,0.7)', fontSize: '0.7rem' }}>Deployed</Typography>
        </Stack>
      </Stack>
    </Stack>
  )
}

export default function CapitalPoolPanel({ pool }) {
  const utilizationRate = pool?.total_capital 
    ? (((pool.total_capital - pool.available_capital) / pool.total_capital) * 100).toFixed(1)
    : 0

  return (
    <Paper variant="outlined" sx={{ p: 2.25, borderColor: 'rgba(148,163,184,0.22)' }}>
      <Stack spacing={2}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 800, fontSize: '1rem' }}>Capital Pool</Typography>
          <Typography 
            variant="caption" 
            sx={{ 
              color: utilizationRate > 50 ? '#fb923c' : '#34d399',
              fontWeight: 700,
              backgroundColor: utilizationRate > 50 ? 'rgba(251,146,60,0.15)' : 'rgba(52,211,153,0.15)',
              px: 1,
              py: 0.25,
              borderRadius: 1
            }}
          >
            {utilizationRate}% deployed
          </Typography>
        </Stack>

        <CapitalBar 
          total={pool?.total_capital}
          available={pool?.available_capital}
          deployed={pool?.capital_allocated}
          pending={pool?.capital_pending_settlement}
        />

        <Divider sx={{ borderColor: 'rgba(148,163,184,0.18)' }} />

        <Stack spacing={0.5}>
          <MetricRow 
            label="Total Capital" 
            value={pool?.total_capital}
            tooltip="Total capital in the pool"
          />
          <MetricRow 
            label="Available" 
            value={pool?.available_capital}
            color="#34d399"
            highlight
            tooltip="Capital ready to deploy for new claims"
          />
          <MetricRow 
            label="Deployed" 
            value={pool?.capital_allocated}
            color="#fb923c"
            highlight
            tooltip="Capital currently advanced to practices"
          />
          <MetricRow 
            label="Pending Settlement" 
            value={pool?.capital_pending_settlement}
            color="#60a5fa"
            highlight
            tooltip="Deployed capital awaiting insurer reimbursement"
          />
        </Stack>

        <Divider sx={{ borderColor: 'rgba(148,163,184,0.18)' }} />

        <Stack spacing={0.5}>
          <Typography variant="caption" sx={{ color: 'rgba(226,232,240,0.5)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.65rem' }}>
            Lifetime Metrics
          </Typography>
          <MetricRow 
            label="Capital Returned" 
            value={pool?.capital_returned}
            color="#a78bfa"
            highlight
            tooltip="Total capital successfully returned from reimbursements"
          />
          {pool?.num_settled_claims > 0 && (
            <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2, py: 0.5 }}>
              <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.75)', fontSize: '0.85rem' }}>Claims Settled</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.85rem' }}>{pool.num_settled_claims}</Typography>
            </Stack>
          )}
        </Stack>
      </Stack>
    </Paper>
  )
}
