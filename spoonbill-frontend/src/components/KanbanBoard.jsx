import * as React from 'react'
import Stack from '@mui/material/Stack'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'

const STAGES = [
  { key: 'submitted', title: 'Claim Submitted', color: '#60a5fa' },
  { key: 'underwriting', title: 'Underwriting', color: '#fb923c' },
  { key: 'funded', title: 'Funded', color: '#34d399' },
  { key: 'reimbursed', title: 'Reimbursed', color: '#a78bfa' }
]

function formatMoney(value) {
  return `$${(value ?? 0).toLocaleString()}`
}

function ClaimCard({ claim, practiceName, onOpen, onQuickAction }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderColor: 'rgba(148,163,184,0.22)',
        background: 'rgba(15,23,42,0.8)',
        cursor: 'pointer'
      }}
      onClick={() => onOpen(claim)}
    >
      <Stack spacing={1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>{claim.claim_id}</Typography>
          <Chip size="small" label={claim.status} />
        </Stack>

        <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.75)' }}>
          {practiceName}
        </Typography>

        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            {formatMoney(claim.expected_allowed_amount)}
          </Typography>
          <Button
            size="small"
            variant="text"
            onClick={(e) => {
              e.stopPropagation()
              onQuickAction(claim)
            }}
          >
            Next
          </Button>
        </Stack>
      </Stack>
    </Paper>
  )
}

export default function KanbanBoard({ claims, practicesById, onOpenClaim, onAdvanceClaim }) {
  const grouped = React.useMemo(() => {
    const map = new Map(STAGES.map(s => [s.key, []]))
    for (const c of claims || []) {
      const key = map.has(c.status) ? c.status : 'submitted'
      map.get(key).push(c)
    }
    return map
  }, [claims])

  return (
    <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ alignItems: 'stretch' }}>
      {STAGES.map(stage => {
        const list = grouped.get(stage.key) || []
        return (
          <Paper
            key={stage.key}
            variant="outlined"
            sx={{
              flex: 1,
              minWidth: 260,
              borderColor: 'rgba(148,163,184,0.22)',
              background: 'rgba(2,6,23,0.35)'
            }}
          >
            <Stack spacing={1.5} sx={{ p: 2 }}>
              <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {stage.title}
                </Typography>
                <Chip size="small" label={list.length} sx={{ backgroundColor: stage.color, color: '#0b1220', fontWeight: 900 }} />
              </Stack>
              <Divider sx={{ borderColor: 'rgba(148,163,184,0.18)' }} />
              <Stack spacing={1.25}>
                {list.map(claim => (
                  <ClaimCard
                    key={claim.claim_id}
                    claim={claim}
                    practiceName={practicesById?.[claim.practice_id]?.id || claim.practice_id}
                    onOpen={onOpenClaim}
                    onQuickAction={onAdvanceClaim}
                  />
                ))}
                {list.length === 0 ? (
                  <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.55)' }}>
                    No claims
                  </Typography>
                ) : null}
              </Stack>
            </Stack>
          </Paper>
        )
      })}
    </Stack>
  )
}
