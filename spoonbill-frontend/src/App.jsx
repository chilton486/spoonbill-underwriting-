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
  settleClaim,
  simulate,
  underwriteClaim
} from './api.js'

import KanbanBoard from './components/KanbanBoard.jsx'
import CapitalPoolPanel from './components/CapitalPoolPanel.jsx'
import ClaimDetailDialog from './components/ClaimDetailDialog.jsx'

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
      await simulate({ poolId: 'POOL', seedIfEmpty: true, advanceOneStep: true })
      await refresh()
    } catch (e) {
      setError(e?.body ? JSON.stringify(e.body) : e.message)
    }
  }

  async function advanceClaim(claim) {
    try {
      setError(null)
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
    } catch (e) {
      setError(e?.body ? JSON.stringify(e.body) : e.message)
      await refresh().catch(() => {})
    }
  }

  function openClaim(claim) {
    setSelectedClaim(claim)
    setDetailOpen(true)
  }

  return (
    <ThemeProvider theme={theme}>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={2.5}>
          <Stack direction={{ xs: 'column', md: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { md: 'center' }, gap: 2 }}>
            <Stack spacing={0.5}>
              <Typography variant="h4" sx={{ fontWeight: 900 }}>Spoonbill Claims Lifecycle</Typography>
              <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.7)' }}>
                Deterministic underwriting + atomic capital allocation (demo UI)
              </Typography>
            </Stack>

            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
              <Button variant="contained" onClick={runSimulationStep}>Run Simulation Step</Button>
              <Button
                variant="outlined"
                onClick={() => refresh().catch(() => {})}
              >
                Refresh
              </Button>
            </Stack>
          </Stack>

          {error ? <Alert severity="error">{error}</Alert> : null}

          <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ alignItems: 'flex-start' }}>
            <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
              <Paper variant="outlined" sx={{ p: 2, borderColor: 'rgba(148,163,184,0.22)' }}>
                <Typography variant="subtitle2" sx={{ color: 'rgba(226,232,240,0.75)' }}>
                  Backend: http://localhost:8000
                </Typography>
              </Paper>

              {loading ? (
                <Stack sx={{ py: 8, alignItems: 'center' }} spacing={2}>
                  <CircularProgress />
                  <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.7)' }}>Loading demo data…</Typography>
                </Stack>
              ) : (
                <KanbanBoard
                  claims={claims}
                  practicesById={practicesById}
                  onOpenClaim={openClaim}
                  onAdvanceClaim={advanceClaim}
                />
              )}
            </Stack>

            <Stack spacing={2} sx={{ width: { xs: '100%', lg: 340 }, flexShrink: 0 }}>
              <CapitalPoolPanel pool={pool} />
              <Paper variant="outlined" sx={{ p: 2.25, borderColor: 'rgba(148,163,184,0.22)' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 900, mb: 1.25 }}>Demo Controls</Typography>
                <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.7)' }}>
                  Click any claim card for details. Use “Next” on a card to push it through the lifecycle.
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
      </Container>
    </ThemeProvider>
  )
}
