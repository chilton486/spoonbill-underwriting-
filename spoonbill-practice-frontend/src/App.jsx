import { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import Skeleton from '@mui/material/Skeleton';
import CircularProgress from '@mui/material/CircularProgress';
import { tokens } from './theme.js';

import LoginPage from './components/LoginPage';
import ClaimsList from './components/ClaimsList';
import ClaimDetail from './components/ClaimDetail';
import SubmitClaimDialog from './components/SubmitClaimDialog';
import SetPasswordPage from './components/SetPasswordPage';
import PaymentsList from './components/PaymentsList';
import OntologyTab from './components/OntologyTab';
import IntegrationsTab from './components/IntegrationsTab';
import { getCurrentUser, getAuthToken, logout, listClaims, getDashboard } from './api';

const STATUS_ORDER = ['NEW', 'NEEDS_REVIEW', 'APPROVED', 'PAID', 'COLLECTING', 'CLOSED', 'DECLINED', 'PAYMENT_EXCEPTION'];

const statusLabels = {
  NEW: 'New',
  NEEDS_REVIEW: 'Needs Review',
  APPROVED: 'Approved',
  PAID: 'Paid',
  COLLECTING: 'Collecting',
  CLOSED: 'Closed',
  DECLINED: 'Declined',
  PAYMENT_EXCEPTION: 'Payment Exception',
};

const statusColors = {
  NEW: '#6b7280',
  NEEDS_REVIEW: '#d97706',
  APPROVED: '#059669',
  PAID: '#2563eb',
  COLLECTING: '#7c3aed',
  CLOSED: '#374151',
  DECLINED: '#dc2626',
  PAYMENT_EXCEPTION: '#dc2626',
};

function DashboardSummary({ dashboard, onStatusClick, onClaimSelect }) {
  if (!dashboard) return (
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 2 }}>
      {[1,2,3,4].map(i => <Skeleton key={i} variant="rounded" height={80} />)}
    </Box>
  );

  const { status_counts, action_required, recent_claims } = dashboard;

  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 2, mb: 3 }}>
        {STATUS_ORDER.map((s) => {
          const count = status_counts[s] || 0;
          if (s === 'PAYMENT_EXCEPTION' && count === 0) return null;
          return (
            <Paper
              key={s}
              elevation={0}
              sx={{
                p: 2.5,
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s',
                '&:hover': { borderColor: statusColors[s], boxShadow: tokens.shadow.md, transform: 'translateY(-1px)' },
              }}
              onClick={() => onStatusClick(s)}
            >
              <Typography variant="h4" sx={{ fontWeight: 700, color: statusColors[s], mb: 0.5 }}>
                {count}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                {statusLabels[s]}
              </Typography>
            </Paper>
          );
        })}
      </Box>

      {action_required.length > 0 && (
        <Paper elevation={0} sx={{ p: 2.5, mb: 2, border: `1px solid ${tokens.colors.status.warningBorder}`, bgcolor: tokens.colors.status.warningBg }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5, color: '#92400e' }}>
            Action Required ({action_required.length})
          </Typography>
          {action_required.slice(0, 5).map((c) => (
            <Box
              key={c.id}
              sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 0.75, cursor: 'pointer', '&:hover': { bgcolor: 'rgba(0,0,0,0.03)' }, px: 1.5, borderRadius: 1, transition: 'background 0.15s' }}
              onClick={() => onClaimSelect(c)}
            >
              <Typography variant="body2" sx={{ fontFamily: tokens.typography.mono, fontWeight: 500, fontSize: '0.8rem' }}>{c.claim_token}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">{c.payer}</Typography>
                <Chip label={c.status === 'PAYMENT_EXCEPTION' ? 'Funding Delayed' : c.status.replace('_', ' ')} size="small" color="warning" />
              </Box>
            </Box>
          ))}
        </Paper>
      )}

      {recent_claims.length > 0 && (
        <Paper elevation={0} sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5 }}>
            Recent Claims
          </Typography>
          {recent_claims.map((c) => (
            <Box
              key={c.id}
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                py: 1,
                px: 1.5,
                cursor: 'pointer',
                '&:hover': { bgcolor: tokens.colors.surfaceHover },
                borderBottom: `1px solid ${tokens.colors.border.light}`,
                transition: 'background 0.15s',
                borderRadius: 1,
              }}
              onClick={() => onClaimSelect(c)}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" sx={{ fontFamily: tokens.typography.mono, fontWeight: 600, fontSize: '0.8rem' }}>
                  {c.claim_token}
                </Typography>
                <Typography variant="body2" color="text.secondary">{c.payer}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(c.amount_cents / 100)}
                </Typography>
                <Chip
                  label={c.status === 'PAYMENT_EXCEPTION' ? 'Funding Delayed' : c.status.replace('_', ' ')}
                  size="small"
                  sx={{ bgcolor: (statusColors[c.status] || '#6b7280') + '15', color: statusColors[c.status] || '#6b7280', fontWeight: 600, fontSize: '0.7rem' }}
                />
              </Box>
            </Box>
          ))}
        </Paper>
      )}
    </Box>
  );
}

function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [claims, setClaims] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({});
  const [activeTab, setActiveTab] = useState(0);
  const filtersRef = useRef({});

  const fetchClaims = useCallback(async (currentFilters = {}) => {
    try {
      const data = await listClaims(currentFilters);
      setClaims(data);
    } catch (err) {
      console.error('Failed to fetch claims:', err);
    }
  }, []);

  const fetchDashboard = useCallback(async () => {
    try {
      const data = await getDashboard();
      setDashboard(data);
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
    }
  }, []);

  useEffect(() => {
    const checkAuth = async () => {
      if (getAuthToken()) {
        try {
          const userData = await getCurrentUser();
          if (userData.role !== 'PRACTICE_MANAGER') {
            setError('This portal is only for Practice Managers');
            logout();
            setUser(null);
          } else {
            setUser(userData);
          }
        } catch (err) {
          logout();
          setUser(null);
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  useEffect(() => {
    if (user) {
      fetchClaims(filtersRef.current);
      fetchDashboard();
      const interval = setInterval(() => {
        fetchClaims(filtersRef.current);
        fetchDashboard();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [user, fetchClaims, fetchDashboard]);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    filtersRef.current = newFilters;
    fetchClaims(newFilters);
  };

  const handleStatusClick = (status) => {
    const newFilters = { status_filter: status };
    setFilters(newFilters);
    filtersRef.current = newFilters;
    fetchClaims(newFilters);
    setActiveTab(1);
  };

  const handleLogin = async (userData) => {
    if (userData.role !== 'PRACTICE_MANAGER') {
      setError('This portal is only for Practice Managers');
      logout();
      return;
    }
    setUser(userData);
    setError(null);
  };

  const handleLogout = () => {
    logout();
    setUser(null);
    setClaims([]);
    setSelectedClaim(null);
    setDashboard(null);
  };

  const handleClaimSubmitted = () => {
    fetchClaims(filtersRef.current);
    fetchDashboard();
    setSubmitDialogOpen(false);
  };

  if (loading) {
    return (
      <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress size={36} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Loading portal...</Typography>
        </Box>
      </Box>
    );
  }

  if (!user) {
    return (
      <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
        <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: `1px solid ${tokens.colors.border.light}`, py: 2, px: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.accent[700] }}>Spoonbill</Typography>
        </Box>
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Paper sx={{ p: 4 }}>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 700 }}>
                Practice Portal
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Sign in to manage your practice claims and payments.
              </Typography>
            </Box>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <LoginPage onLogin={handleLogin} />
          </Paper>
        </Container>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
      <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: `1px solid ${tokens.colors.border.light}`, px: 3, py: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', maxWidth: 1200, mx: 'auto' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.accent[700] }}>Spoonbill</Typography>
            <Chip label="Practice Portal" size="small" sx={{ bgcolor: tokens.colors.accent[50], color: tokens.colors.accent[700], fontWeight: 600, fontSize: '0.7rem' }} />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Chip
              label="Practice Manager"
              size="small"
              sx={{ bgcolor: tokens.colors.surfaceHover, color: tokens.colors.text.secondary, fontWeight: 600, fontSize: '0.7rem' }}
            />
            <Typography variant="caption" color="text.secondary">
              {user.email}
            </Typography>
            <Button variant="outlined" size="small" onClick={() => setSubmitDialogOpen(true)}>
              + Submit Claim
            </Button>
            <Button
              variant="text"
              size="small"
              sx={{ color: tokens.colors.text.muted }}
              onClick={handleLogout}
            >
              Logout
            </Button>
          </Box>
        </Box>
      </Box>

      <Box sx={{ maxWidth: 1200, mx: 'auto', px: 3, py: 3 }}>
        <Paper sx={{ px: 0.5, py: 0, mb: 3 }}>
          <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
            <Tab label="Dashboard" />
            <Tab label="Claims" />
            <Tab label="Payments" />
            <Tab label="Ontology" />
            <Tab label="Integrations" />
          </Tabs>
        </Paper>

        {activeTab === 0 && (
          <DashboardSummary
            dashboard={dashboard}
            onStatusClick={handleStatusClick}
            onClaimSelect={(claim) => setSelectedClaim(claim)}
          />
        )}

        {activeTab === 1 && (
          <ClaimsList
            claims={claims}
            onClaimSelect={(claim) => setSelectedClaim(claim)}
            onSubmitClick={() => setSubmitDialogOpen(true)}
            onFilterChange={handleFilterChange}
          />
        )}

        {activeTab === 2 && (
          <PaymentsList />
        )}

        {activeTab === 3 && user && (
          <OntologyTab practiceId={user.practice_id} />
        )}

        {activeTab === 4 && (
          <IntegrationsTab />
        )}

        {selectedClaim && (
          <ClaimDetail
            claimId={selectedClaim.id}
            open={!!selectedClaim}
            onClose={() => {
              setSelectedClaim(null);
              fetchClaims(filtersRef.current);
              fetchDashboard();
            }}
          />
        )}

        <SubmitClaimDialog
          open={submitDialogOpen}
          onClose={() => setSubmitDialogOpen(false)}
          onSubmitted={handleClaimSubmitted}
        />
      </Box>
    </Box>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/set-password/:token" element={<SetPasswordPage />} />
      <Route path="*" element={<Dashboard />} />
    </Routes>
  );
}

export default App;
