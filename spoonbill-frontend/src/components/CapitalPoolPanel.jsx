import * as React from 'react'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

function Money({ value }) {
  return <>{`$${(value ?? 0).toLocaleString()}`}</>
}

function Row({ label, value }) {
  return (
    <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.75)' }}>{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 700 }}><Money value={value} /></Typography>
    </Stack>
  )
}

export default function CapitalPoolPanel({ pool }) {
  return (
    <Paper variant="outlined" sx={{ p: 2.25, borderColor: 'rgba(148,163,184,0.22)' }}>
      <Stack spacing={1.5}>
        <Typography variant="h6" sx={{ fontWeight: 800 }}>Capital Pool</Typography>
        <Row label="Total Capital" value={pool?.total_capital} />
        <Row label="Available Capital" value={pool?.available_capital} />
        <Row label="Capital Allocated" value={pool?.capital_allocated} />
        <Row label="Pending Settlement" value={pool?.capital_pending_settlement} />
      </Stack>
    </Paper>
  )
}
