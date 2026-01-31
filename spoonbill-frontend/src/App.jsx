import * as React from 'react'
import Container from '@mui/material/Container'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import { ThemeProvider } from '@mui/material/styles'

import { theme } from './theme.js'
import {
  fundClaim,
  getCapitalPool,
  getClaims,
  getPractices,
  resetDemo,
  settleClaim,
  simulate,
  simulateAdjudication,
  submitClaim,
  underwriteClaim
} from './api.js'

import KanbanBoard from './components/KanbanBoard.jsx'
import CapitalPoolPanel from './components/CapitalPoolPanel.jsx'
import ClaimDetailDialog from './components/ClaimDetailDialog.jsx'
import SubmitClaimDialog from './components/SubmitClaimDialog.jsx'
import SimulateAdjudicationDialog from './components/SimulateAdjudicationDialog.jsx'

function toPracticeMap(practices) {
  const map = {}
  for (const p of practices || []) map[p.id] = p
  return map
}

export default function App() {
  const [claims, setClaims] = React.useState([])
  const [practices, setPractices] = React.useState([])
  const [pool, setPool] = React.useState(null)
  const [error, setError] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [selectedClaim, setSelectedClaim] = React.useState(null)
  const [detailOpen, setDetailOpen] = React.useState(false)
  const [loadingClaimId, setLoadingClaimId] = React.useState(null)
  const [recentlyAdvanced, setRecentlyAdvanced] = React.useState(null)
  const [simulating, setSimulating] = React.useState(false)
  const [resetting, setResetting] = React.useState(false)
  const [submitClaimOpen, setSubmitClaimOpen] = React.useState(false)
  const [adjudicationOpen, setAdjudicationOpen] = React.useState(false)

  const practicesById = React.useMemo(() => toPracticeMap(practices), [practices])

  const refresh = React.useCallback(async () => {
    const [c, p, poolData] = await Promise.all([
      getClaims(),
      getPractices(),
      getCapitalPool('POOL')
    ])
    setClaims(c)
    setPractices(p)
    setPool(poolData)
  }, [])

  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        setLoading(true)
        setError(null)
        // Ensure demo data exists at first load.
        await simulate({ poolId: 'POOL', seedIfEmpty: true, advanceOneStep: false })
        await refresh()
      } catch (e) {
        if (!mounted) return
        setError(e?.body ? JSON.stringify(e.body) : e.message)
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => {
      mounted = false
    }
  }, [refresh])

  React.useEffect(() => {
    const id = setInterval(() => {
      refresh().catch(() => {})
    }, 1500)
    return () => clearInterval(id)
  }, [refresh])

  async function runSimulationStep() {
    try {
      setError(null)
      setSimulating(true)
      await simulate({ poolId: 'POOL', seedIfEmpty: true, advanceOneStep: true })
      await refresh()
    } catch (e) {
      setError(e?.body ? JSON.stringify(e.body) : e.message)
    } finally {
      setSimulating(false)
    }
  }

  async function handleResetDemo() {
    try {
      setError(null)
      setResetting(true)
      await resetDemo({ poolId: 'POOL' })
      await refresh()
    } catch (e) {
      setError(e?.body ? JSON.stringify(e.body) : e.message)
    } finally {
      setResetting(false)
    }
  }

  async function advanceClaim(claim) {
    try {
      setError(null)
      setLoadingClaimId(claim.claim_id)
      if (claim.status === 'submitted') {
        await underwriteClaim(claim.claim_id, { poolId: 'POOL' })
      } else if (claim.status === 'underwriting') {
        await fundClaim(claim.claim_id, { poolId: 'POOL' })
      } else if (claim.status === 'funded') {
        await settleClaim(claim.claim_id, {
          poolId: 'POOL',
          settlementDate: new Date().toISOString().slice(0, 10),
          settlementAmount: claim.funded_amount
        })
      }
      await refresh()
      setRecentlyAdvanced(claim.claim_id)
      setTimeout(() => setRecentlyAdvanced(null), 2000)
    } catch (e) {
      setError(e?.body ? JSON.stringify(e.body) : e.message)
      await refresh().catch(() => {})
    } finally {
      setLoadingClaimId(null)
    }
  }

  function openClaim(claim) {
    setSelectedClaim(claim)
    setDetailOpen(true)
  }

  async function handleSubmitClaim(data) {
    await submitClaim(data)
    await refresh()
  }

  async function handleSimulateAdjudication(data) {
    await simulateAdjudication(data)
    await refresh()
  }

  return (
    <ThemeProvider theme={theme}>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={2.5}>
          <Stack direction={{ xs: 'column', md: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { md: 'center' }, gap: 2 }}>
            <Stack spacing={0.5}>
              <Typography variant="h4" sx={{ fontWeight: 900 }}>Spoonbill Claims Lifecycle</Typography>
              <Typography variant="body2" sx={{ color: '#6b7280' }}>
                Deterministic underwriting + atomic capital allocation (demo UI)
              </Typography>
            </Stack>

            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                onClick={() => setSubmitClaimOpen(true)}
              >
                Submit Claim
              </Button>
              <Button
                variant="outlined"
                onClick={() => setAdjudicationOpen(true)}
              >
                Simulate Adjudication
              </Button>
              <Button 
                variant="outlined" 
                onClick={runSimulationStep}
                disabled={simulating}
                startIcon={simulating ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {simulating ? 'Running...' : 'Run Simulation Step'}
              </Button>
              <Button
                variant="outlined"
                onClick={handleResetDemo}
                disabled={resetting}
                startIcon={resetting ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {resetting ? 'Resetting...' : 'Reset Demo'}
              </Button>
            </Stack>
          </Stack>

          {error ? <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert> : null}

          <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ alignItems: 'flex-start' }}>
            <Stack spacing={2} sx={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>
              {loading ? (
                <Stack sx={{ py: 8, alignItems: 'center' }} spacing={2}>
                  <CircularProgress />
                  <Typography variant="body2" sx={{ color: '#6b7280' }}>Loading demo data…</Typography>
                </Stack>
              ) : (
                <KanbanBoard
                  claims={claims}
                  practicesById={practicesById}
                  onOpenClaim={openClaim}
                  onAdvanceClaim={advanceClaim}
                  loadingClaimId={loadingClaimId}
                  recentlyAdvanced={recentlyAdvanced}
                />
              )}
            </Stack>

            <Stack spacing={2} sx={{ width: { xs: '100%', lg: 300 }, flexShrink: 0 }}>
              <CapitalPoolPanel pool={pool} />
              <Paper variant="outlined" sx={{ p: 2.25, borderColor: '#e5e7eb' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 900, mb: 1.25 }}>How It Works</Typography>
                <Stack spacing={1}>
                  <Typography variant="body2" sx={{ color: '#6b7280', fontSize: '0.8rem' }}>
                    1. Practices submit dental insurance claims
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#6b7280', fontSize: '0.8rem' }}>
                    2. Spoonbill underwrites risk instantly
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#6b7280', fontSize: '0.8rem' }}>
                    3. Capital is deployed same-day to practice
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#6b7280', fontSize: '0.8rem' }}>
                    4. Insurer reimburses Spoonbill days later
                  </Typography>
                </Stack>
                <Typography variant="caption" sx={{ color: '#9ca3af', display: 'block', mt: 1.5 }}>
                  Click "Next" on any claim to advance it through the lifecycle.
                </Typography>
              </Paper>
            </Stack>
          </Stack>
        </Stack>

        <ClaimDetailDialog
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          claim={selectedClaim}
          practice={selectedClaim ? practicesById[selectedClaim.practice_id] : null}
        />

        <SubmitClaimDialog
          open={submitClaimOpen}
          onClose={() => setSubmitClaimOpen(false)}
          practices={practices}
          onSubmit={handleSubmitClaim}
        />

        <SimulateAdjudicationDialog
          open={adjudicationOpen}
          onClose={() => setAdjudicationOpen(false)}
          claims={claims}
          onSubmit={handleSimulateAdjudication}
        />
      </Container>
    </ThemeProvider>
  )
}
