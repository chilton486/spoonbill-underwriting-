import * as React from 'react'
import Stack from '@mui/material/Stack'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'
import CircularProgress from '@mui/material/CircularProgress'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'

const STAGES = [
  { key: 'submitted', title: 'Claim Submitted', color: '#9ca3af', description: 'Awaiting review' },
  { key: 'adjudicated', title: 'Adjudicated', color: '#6b7280', description: 'Payer approved' },
  { key: 'underwriting', title: 'Underwriting', color: '#4b5563', description: 'Risk assessment' },
  { key: 'funded', title: 'Funded', color: '#1a1a1a', description: 'Capital deployed' },
  { key: 'reimbursed', title: 'Reimbursed', color: '#374151', description: 'Capital returned' },
  { key: 'exception', title: 'Exception', color: '#6b7280', description: 'Requires attention' }
]

function formatMoney(value) {
  return `$${(value ?? 0).toLocaleString()}`
}

function getDaysOutstanding(submissionDate) {
  if (!submissionDate) return 0
  const submitted = new Date(submissionDate)
  const now = new Date()
  const diffTime = Math.abs(now - submitted)
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
}

function ClaimCard({ claim, practiceName, onOpen, onQuickAction, isLoading, justAdvanced }) {
  const isFunded = claim.status === 'funded'
  const isTerminal = claim.status === 'reimbursed' || claim.status === 'exception'
  const daysOut = isFunded ? getDaysOutstanding(claim.submission_date) : null

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderColor: justAdvanced ? '#1a1a1a' : '#e5e7eb',
        background: justAdvanced ? '#f9fafb' : '#ffffff',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        '&:hover': {
          borderColor: '#9ca3af',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }
      }}
      onClick={() => onOpen(claim)}
    >
      <Stack spacing={1}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>{claim.claim_id}</Typography>
          <Chip 
            size="small" 
            label={claim.status}
            sx={{
              backgroundColor: STAGES.find(s => s.key === claim.status)?.color || '#6b7280',
              color: '#ffffff',
              fontWeight: 600
            }}
          />
        </Stack>

        <Typography variant="body2" sx={{ color: '#6b7280' }}>
          {practiceName}
        </Typography>

        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Stack>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              {formatMoney(claim.expected_allowed_amount)}
            </Typography>
            {isFunded && (
              <Typography variant="caption" sx={{ color: '#6b7280', fontWeight: 600 }}>
                {daysOut} day{daysOut !== 1 ? 's' : ''} outstanding
              </Typography>
            )}
          </Stack>
          {!isTerminal && (
            <Button
              size="small"
              variant="contained"
              disabled={isLoading}
              endIcon={isLoading ? <CircularProgress size={14} color="inherit" /> : <ArrowForwardIcon sx={{ fontSize: 14 }} />}
              onClick={(e) => {
                e.stopPropagation()
                onQuickAction(claim)
              }}
              sx={{
                minWidth: 70,
                fontSize: '0.75rem',
                py: 0.5
              }}
            >
              {isLoading ? '' : 'Next'}
            </Button>
          )}
          {justAdvanced && (
            <CheckCircleIcon sx={{ color: '#1a1a1a', fontSize: 20 }} />
          )}
        </Stack>
      </Stack>
    </Paper>
  )
}

export default function KanbanBoard({ claims, practicesById, onOpenClaim, onAdvanceClaim, loadingClaimId, recentlyAdvanced }) {
  const grouped = React.useMemo(() => {
    const map = new Map(STAGES.map(s => [s.key, []]))
    for (const c of claims || []) {
      const key = map.has(c.status) ? c.status : 'submitted'
      map.get(key).push(c)
    }
    return map
  }, [claims])

  // Calculate total capital at each stage for investor visibility
  const stageTotals = React.useMemo(() => {
    const totals = {}
    for (const stage of STAGES) {
      const list = grouped.get(stage.key) || []
      totals[stage.key] = list.reduce((sum, c) => sum + (c.funded_amount || c.expected_allowed_amount || 0), 0)
    }
    return totals
  }, [grouped])

  return (
    <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ alignItems: 'stretch' }}>
      {STAGES.map(stage => {
        const list = grouped.get(stage.key) || []
        const stageTotal = stageTotals[stage.key]
        return (
          <Paper
            key={stage.key}
            variant="outlined"
            sx={{
              flex: 1,
              minWidth: 200,
              borderColor: '#e5e7eb',
              background: '#fafafa'
            }}
          >
            <Stack spacing={1.5} sx={{ p: 1.5 }}>
              <Stack spacing={0.5}>
                <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: '0.7rem' }}>
                    {stage.title}
                  </Typography>
                  <Chip size="small" label={list.length} sx={{ backgroundColor: stage.color, color: '#ffffff', fontWeight: 700, height: 20, fontSize: '0.7rem' }} />
                </Stack>
                <Typography variant="caption" sx={{ color: '#9ca3af', fontSize: '0.65rem' }}>
                  {stage.description}
                </Typography>
                {stageTotal > 0 && (
                  <Typography variant="caption" sx={{ color: '#1a1a1a', fontWeight: 700, fontSize: '0.75rem' }}>
                    {formatMoney(stageTotal)} total
                  </Typography>
                )}
              </Stack>
              <Divider sx={{ borderColor: '#e5e7eb' }} />
              <Stack spacing={1.25}>
                {list.map(claim => (
                  <ClaimCard
                    key={claim.claim_id}
                    claim={claim}
                    practiceName={practicesById?.[claim.practice_id]?.id || claim.practice_id}
                    onOpen={onOpenClaim}
                    onQuickAction={onAdvanceClaim}
                    isLoading={loadingClaimId === claim.claim_id}
                    justAdvanced={recentlyAdvanced === claim.claim_id}
                  />
                ))}
                {list.length === 0 ? (
                  <Typography variant="body2" sx={{ color: '#9ca3af', fontStyle: 'italic', py: 2, textAlign: 'center' }}>
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
