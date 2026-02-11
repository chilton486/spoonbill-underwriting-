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
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'

import { theme } from './theme.js'
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

const STATUSES = ['NEW', 'NEEDS_REVIEW', 'APPROVED', 'PAID', 'COLLECTING', 'CLOSED', 'DECLINED']
const MAIN_TABS = ['Claims', 'Applications', 'Practices']

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
          <Container maxWidth="lg" sx={{ py: 8, textAlign: 'center' }}>
            <CircularProgress />
            <Typography sx={{ mt: 2 }}>Loading...</Typography>
          </Container>
        </ThemeProvider>
      )
    }

    if (!user) {
      return (
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <LoginPage onLogin={handleLogin} />
        </ThemeProvider>
      )
    }

    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={3}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Stack spacing={0.5}>
              <Typography variant="h4" sx={{ fontWeight: 900 }}>Spoonbill Internal Console</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Claim lifecycle management with audit trail
              </Typography>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Chip 
                label={user.role === 'ADMIN' ? 'Admin' : 'Ops'} 
                size="small" 
                sx={{ bgcolor: '#1a1a1a', color: '#ffffff', fontWeight: 600 }}
              />
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {user.email}
              </Typography>
              <Button variant="outlined" onClick={() => setCreateOpen(true)}>
                Create Claim
              </Button>
              <Button variant="outlined" color="inherit" onClick={handleLogout}>
                Logout
              </Button>
            </Stack>
          </Stack>

                    {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

                    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                      <Tabs value={mainTab} onChange={(e, v) => setMainTab(v)}>
                        {MAIN_TABS.map((tab) => (
                          <Tab key={tab} label={tab} />
                        ))}
                      </Tabs>
                    </Box>

                    {mainTab === 0 && (
                      <>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                          <Box sx={{ flex: 1 }} />
                          <TextField
                            size="small"
                            placeholder="Search claims by ID, token, patient, payer, practice..."
                            value={claimSearchInput}
                            onChange={(e) => setClaimSearchInput(e.target.value)}
                            sx={{ width: 400 }}
                            InputProps={{
                              startAdornment: (
                                <InputAdornment position="start">
                                  <SearchIcon sx={{ color: 'text.secondary' }} />
                                </InputAdornment>
                              ),
                            }}
                          />
                        </Stack>

                        {!claimSearchQuery && (
                          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                            <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} variant="scrollable" scrollButtons="auto">
                              {STATUSES.map((status) => (
                                <Tab 
                                  key={status} 
                                  label={`${status.replace('_', ' ')} (${claimCounts[status]})`}
                                />
                              ))}
                            </Tabs>
                          </Box>
                        )}

                        {claimSearchQuery && (
                          <Alert severity="info" sx={{ mb: 2 }}>
                            Showing {claims.length} result(s) for "{claimSearchQuery}"
                            <Button size="small" sx={{ ml: 2 }} onClick={() => { setClaimSearchInput(''); setClaimSearchQuery(''); }}>
                              Clear search
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

                    {mainTab === 1 && (
                      <ApplicationsQueue />
                    )}

                    {mainTab === 2 && (
                      <PracticesList />
                    )}
        </Stack>

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
      </Container>
    </ThemeProvider>
  )
}
