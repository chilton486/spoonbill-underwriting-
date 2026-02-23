import * as React from 'react'
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
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Divider from '@mui/material/Divider'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import TextField from '@mui/material/TextField'
import InputAdornment from '@mui/material/InputAdornment'
import SearchIcon from '@mui/icons-material/Search'
import DescriptionIcon from '@mui/icons-material/Description'
import InboxIcon from '@mui/icons-material/Inbox'
import BusinessIcon from '@mui/icons-material/Business'
import PaymentIcon from '@mui/icons-material/Payment'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import ExtensionIcon from '@mui/icons-material/Extension'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import AssignmentIcon from '@mui/icons-material/Assignment'

import { theme, themeTokens as tokens } from './theme.js'

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
import EconomicsTab from './components/EconomicsTab.jsx'
import PracticeRecord from './components/PracticeRecord.jsx'
import AgenticOpsPanel from './components/AgenticOpsPanel.jsx'
import ControlTowerPage from './components/ControlTowerPage.jsx'
import ReconciliationPage from './components/ReconciliationPage.jsx'
import TasksQueue from './components/TasksQueue.jsx'

const STATUSES = ['NEW', 'NEEDS_REVIEW', 'APPROVED', 'PAID', 'COLLECTING', 'CLOSED', 'DECLINED', 'PAYMENT_EXCEPTION']

const NAV_SECTIONS = [
  { key: 'control-tower', label: 'Control Tower', icon: AccountBalanceIcon },
  { divider: true },
  { key: 'claims', label: 'Claims', icon: DescriptionIcon },
  { key: 'applications', label: 'Applications', icon: InboxIcon },
  { key: 'practices', label: 'Practices', icon: BusinessIcon },
  { key: 'payments', label: 'Payments', icon: PaymentIcon },
  { key: 'integrations', label: 'Integrations', icon: ExtensionIcon },
  { key: 'exceptions', label: 'Exceptions', icon: WarningAmberIcon },
  { divider: true },
  { key: 'economics', label: 'Economics', icon: ShowChartIcon },
  { key: 'reconciliation', label: 'Reconciliation', icon: CompareArrowsIcon },
  { key: 'tasks', label: 'Tasks', icon: AssignmentIcon },
  { key: 'agentic', label: 'Agentic Ops', icon: SmartToyIcon },
]

const SIDEBAR_WIDTH = 220

export default function App() {
  const [user, setUser] = React.useState(null)
  const [claims, setClaims] = React.useState([])
  const [error, setError] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [selectedClaim, setSelectedClaim] = React.useState(null)
  const [detailOpen, setDetailOpen] = React.useState(false)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState(0)
  const [navSection, setNavSection] = React.useState('control-tower')
  const [loadingClaimId, setLoadingClaimId] = React.useState(null)
  const [claimSearchInput, setClaimSearchInput] = React.useState('')
  const [claimSearchQuery, setClaimSearchQuery] = React.useState('')
  const [selectedPracticeId, setSelectedPracticeId] = React.useState(null)

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

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setClaimSearchQuery(claimSearchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [claimSearchInput])

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
    }, 10000)
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

  const handlePracticeSelect = (practiceId) => {
    setSelectedPracticeId(practiceId)
  }

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
      <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: tokens.colors.background }}>
        <Box
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            bgcolor: tokens.colors.surface,
            borderRight: `1px solid ${tokens.colors.border.light}`,
            display: 'flex',
            flexDirection: 'column',
            position: 'fixed',
            top: 0,
            left: 0,
            bottom: 0,
            zIndex: 10,
          }}
        >
          <Box sx={{ px: 2, py: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.text.primary, letterSpacing: '-0.01em', fontSize: '1rem' }}>Spoonbill</Typography>
              <Chip label="Ops" size="small" sx={{ bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[600], fontWeight: 600, fontSize: '0.65rem', height: 20 }} />
            </Stack>
          </Box>

          <Divider />

          <List sx={{ flex: 1, py: 1, px: 1 }}>
            {NAV_SECTIONS.map((item, idx) => {
              if (item.divider) return <Divider key={`div-${idx}`} sx={{ my: 1 }} />
              const Icon = item.icon
              const isActive = navSection === item.key
              return (
                <ListItemButton
                  key={item.key}
                  selected={isActive}
                  onClick={() => {
                    setNavSection(item.key)
                    setSelectedPracticeId(null)
                  }}
                  sx={{
                    borderRadius: tokens.radius.sm,
                    mb: 0.25,
                    py: 0.75,
                    px: 1.5,
                    '&.Mui-selected': {
                      bgcolor: tokens.colors.accent[50],
                      color: tokens.colors.accent[700],
                      '&:hover': { bgcolor: tokens.colors.accent[100] },
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 32, color: isActive ? tokens.colors.accent[600] : tokens.colors.text.muted }}>
                    <Icon sx={{ fontSize: 18 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize: '0.8125rem',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  />
                </ListItemButton>
              )
            })}
          </List>

          <Divider />
          <Box sx={{ p: 1.5 }}>
            <Stack spacing={0.5}>
              <Typography variant="caption" sx={{ px: 0.5 }}>{user.email}</Typography>
              <Button variant="outlined" size="small" fullWidth onClick={handleLogout} sx={{ fontSize: '0.75rem' }}>Logout</Button>
            </Stack>
          </Box>
        </Box>

        <Box sx={{ flex: 1, ml: `${SIDEBAR_WIDTH}px`, overflow: 'auto' }}>
          <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: `1px solid ${tokens.colors.border.light}`, px: 3, py: 1.5 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h5" sx={{ fontWeight: 700, textTransform: 'capitalize' }}>
                {navSection === 'agentic' ? 'Agentic Ops' : navSection === 'control-tower' ? 'Control Tower' : navSection}
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  label={user.role === 'ADMIN' ? 'Admin' : 'Ops'}
                  size="small"
                  sx={{ bgcolor: tokens.colors.surfaceHover, color: tokens.colors.text.secondary, fontWeight: 600, fontSize: '0.7rem' }}
                />
                {navSection === 'claims' && (
                  <Button variant="contained" size="small" onClick={() => setCreateOpen(true)}>+ New Claim</Button>
                )}
              </Stack>
            </Stack>
          </Box>

          <Box sx={{ p: 3 }}>
            <Stack spacing={3}>
              {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

              {navSection === 'claims' && (
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

              {navSection === 'applications' && <ApplicationsQueue />}

              {navSection === 'practices' && !selectedPracticeId && (
                <PracticesList onSelectPractice={handlePracticeSelect} />
              )}
              {navSection === 'practices' && selectedPracticeId && (
                <PracticeRecord practiceId={selectedPracticeId} onBack={() => setSelectedPracticeId(null)} />
              )}

              {navSection === 'payments' && (
                <EconomicsTab initialTab={0} />
              )}

              {navSection === 'integrations' && (
                <Paper sx={{ p: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    Integration management is available on each Practice record page. Select a practice to view its integrations.
                  </Typography>
                </Paper>
              )}

              {navSection === 'exceptions' && <PaymentExceptions />}
              {navSection === 'economics' && <EconomicsTab />}
              {navSection === 'reconciliation' && <ReconciliationPage />}
              {navSection === 'tasks' && <TasksQueue />}
              {navSection === 'agentic' && <AgenticOpsPanel />}
              {navSection === 'control-tower' && <ControlTowerPage />}
            </Stack>
          </Box>
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
