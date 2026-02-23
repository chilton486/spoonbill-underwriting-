import * as React from 'react'
import Container from '@mui/material/Container'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Skeleton from '@mui/material/Skeleton'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'

import { theme, themeTokens as tokens } from './theme.js'
import TextField from '@mui/material/TextField'
import InputAdornment from '@mui/material/InputAdornment'
import SearchIcon from '@mui/icons-material/Search'

import {
  getClaims,
  getCurrentUser,
  getAuthToken,
  logout,
  searchClaims,
} from './api.js'

import LoginPage from './components/LoginPage.jsx'
import ClaimsList from './components/ClaimsList.jsx'
import ClaimDetailDialog from './components/ClaimDetailDialog.jsx'
import CreateClaimDialog from './components/CreateClaimDialog.jsx'
import ApplicationsQueue from './components/ApplicationsQueue.jsx'
import PracticesList from './components/PracticesList.jsx'
import PaymentExceptions from './components/PaymentExceptions.jsx'

const STATUSES = ['NEW', 'NEEDS_REVIEW', 'APPROVED', 'PAID', 'COLLECTING', 'CLOSED', 'DECLINED', 'PAYMENT_EXCEPTION']
const MAIN_TABS = ['Claims', 'Applications', 'Practices', 'Payment Exceptions']

export default function App() {
  const [user, setUser] = React.useState(null)
  const [claims, setClaims] = React.useState([])
  const [error, setError] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [selectedClaim, setSelectedClaim] = React.useState(null)
  const [detailOpen, setDetailOpen] = React.useState(false)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState(0)
  const [mainTab, setMainTab] = React.useState(0)
  const [loadingClaimId, setLoadingClaimId] = React.useState(null)
  const [claimSearchInput, setClaimSearchInput] = React.useState('')
  const [claimSearchQuery, setClaimSearchQuery] = React.useState('')

  const refresh = React.useCallback(async (query = null) => {
    try {
      const allClaims = query ? await searchClaims(query) : await getClaims()
      setClaims(allClaims)
    } catch (e) {
      if (e.status === 401) {
        setUser(null)
        logout()
      } else {
        setError(e.message)
      }
    }
  }, [])

  // Debounced claim search
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setClaimSearchQuery(claimSearchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [claimSearchInput])

  // Refresh claims when search query changes
  React.useEffect(() => {
    if (user) {
      refresh(claimSearchQuery || null)
    }
  }, [claimSearchQuery, user, refresh])

  React.useEffect(() => {
    let mounted = true
    ;(async () => {
      const token = getAuthToken()
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const currentUser = await getCurrentUser()
        if (mounted) {
          setUser(currentUser)
          await refresh()
        }
      } catch (e) {
        if (mounted) {
          logout()
        }
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [refresh])

  React.useEffect(() => {
    if (!user) return
    const id = setInterval(() => {
      refresh().catch(() => {})
    }, 3000)
    return () => clearInterval(id)
  }, [user, refresh])

  const handleLogin = (loggedInUser) => {
    setUser(loggedInUser)
    setError(null)
    refresh()
  }

  const handleLogout = () => {
    logout()
    setUser(null)
    setClaims([])
  }

  const openClaimDetail = (claim) => {
    setSelectedClaim(claim)
    setDetailOpen(true)
  }

  const filteredClaims = React.useMemo(() => {
    const status = STATUSES[activeTab]
    return claims.filter(c => c.status === status)
  }, [claims, activeTab])

  const claimCounts = React.useMemo(() => {
    const counts = {}
    for (const s of STATUSES) counts[s] = 0
    for (const c of claims) {
      if (counts[c.status] !== undefined) counts[c.status]++
    }
    return counts
  }, [claims])

    if (loading) {
      return (
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Stack spacing={2} alignItems="center">
              <CircularProgress size={36} />
              <Typography variant="body2" color="text.secondary">Loading console...</Typography>
            </Stack>
          </Box>
        </ThemeProvider>
      )
    }

    if (!user) {
      return (
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
            <LoginPage onLogin={handleLogin} />
          </Box>
        </ThemeProvider>
      )
    }

    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
          <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: `1px solid ${tokens.colors.border.light}`, px: 3, py: 1.5 }}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', maxWidth: 1400, mx: 'auto' }}>
              <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.accent[700] }}>Spoonbill</Typography>
                <Chip label="Internal Console" size="small" sx={{ bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[700], fontWeight: 600, fontSize: '0.7rem' }} />
              </Stack>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Chip
                  label={user.role === 'ADMIN' ? 'Admin' : 'Ops'}
                  size="small"
                  sx={{ bgcolor: tokens.colors.text.primary, color: '#fff', fontWeight: 600, fontSize: '0.7rem' }}
                />
                <Typography variant="caption" color="text.secondary">{user.email}</Typography>
                <Button variant="contained" size="small" onClick={() => setCreateOpen(true)}>
                  + New Claim
                </Button>
                <Button variant="text" size="small" onClick={handleLogout} sx={{ color: tokens.colors.text.muted }}>
                  Logout
                </Button>
              </Stack>
            </Stack>
          </Box>

          <Box sx={{ maxWidth: 1400, mx: 'auto', px: 3, py: 3 }}>
            <Stack spacing={3}>
              {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

              <Paper sx={{ px: 0.5, py: 0 }}>
                <Tabs value={mainTab} onChange={(e, v) => setMainTab(v)}>
                  {MAIN_TABS.map((tab) => (
                    <Tab key={tab} label={tab} />
                  ))}
                </Tabs>
              </Paper>

              {mainTab === 0 && (
                <>
                  <Stack direction="row" justifyContent="flex-end" alignItems="center">
                    <TextField
                      size="small"
                      placeholder="Search claims..."
                      value={claimSearchInput}
                      onChange={(e) => setClaimSearchInput(e.target.value)}
                      sx={{ width: 360 }}
                      InputProps={{
                        startAdornment: (
                          <InputAdornment position="start">
                            <SearchIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                          </InputAdornment>
                        ),
                      }}
                    />
                  </Stack>

                  {!claimSearchQuery && (
                    <Paper sx={{ px: 0.5, py: 0 }}>
                      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} variant="scrollable" scrollButtons="auto">
                        {STATUSES.map((status) => (
                          <Tab
                            key={status}
                            label={
                              <Stack direction="row" spacing={0.75} alignItems="center">
                                <span>{status.replace(/_/g, ' ')}</span>
                                <Chip label={claimCounts[status]} size="small" sx={{ height: 20, fontSize: '0.7rem', minWidth: 24 }} />
                              </Stack>
                            }
                          />
                        ))}
                      </Tabs>
                    </Paper>
                  )}

                  {claimSearchQuery && (
                    <Alert severity="info">
                      Showing {claims.length} result(s) for &ldquo;{claimSearchQuery}&rdquo;
                      <Button size="small" sx={{ ml: 2 }} onClick={() => { setClaimSearchInput(''); setClaimSearchQuery(''); }}>
                        Clear
                      </Button>
                    </Alert>
                  )}

                  <ClaimsList
                    claims={claimSearchQuery ? claims : filteredClaims}
                    onOpenClaim={openClaimDetail}
                    loadingClaimId={loadingClaimId}
                  />
                </>
              )}

              {mainTab === 1 && <ApplicationsQueue />}
              {mainTab === 2 && <PracticesList />}
              {mainTab === 3 && <PaymentExceptions />}
            </Stack>
          </Box>

          <ClaimDetailDialog
            open={detailOpen}
            onClose={() => setDetailOpen(false)}
            claim={selectedClaim}
            onRefresh={refresh}
          />

          <CreateClaimDialog
            open={createOpen}
            onClose={() => setCreateOpen(false)}
            onCreated={() => {
              setCreateOpen(false)
              refresh()
            }}
          />
        </Box>
      </ThemeProvider>
    )
}
