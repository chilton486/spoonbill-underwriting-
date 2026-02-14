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

import LoginPage from './components/LoginPage';
import ClaimsList from './components/ClaimsList';
import ClaimDetail from './components/ClaimDetail';
import SubmitClaimDialog from './components/SubmitClaimDialog';
import SetPasswordPage from './components/SetPasswordPage';
import PaymentsList from './components/PaymentsList';
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
  if (!dashboard) return null;

  const { status_counts, action_required, recent_claims } = dashboard;

  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 1.5, mb: 3 }}>
        {STATUS_ORDER.map((s) => {
          const count = status_counts[s] || 0;
          if (s === 'PAYMENT_EXCEPTION' && count === 0) return null;
          return (
            <Paper
              key={s}
              elevation={0}
              sx={{
                p: 2,
                textAlign: 'center',
                border: '1px solid #e5e7eb',
                cursor: 'pointer',
                '&:hover': { borderColor: statusColors[s], bgcolor: '#fafafa' },
              }}
              onClick={() => onStatusClick(s)}
            >
              <Typography variant="h5" sx={{ fontWeight: 700, color: statusColors[s] }}>
                {count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {statusLabels[s]}
              </Typography>
            </Paper>
          );
        })}
      </Box>

      {action_required.length > 0 && (
        <Paper elevation={0} sx={{ p: 2, mb: 2, border: '1px solid #fbbf24', bgcolor: '#fffbeb' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, color: '#92400e' }}>
            Action Required ({action_required.length})
          </Typography>
          {action_required.slice(0, 5).map((c) => (
            <Box
              key={c.id}
              sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: '#fef3c7' }, px: 1, borderRadius: 1 }}
              onClick={() => onClaimSelect(c)}
            >
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{c.claim_token}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">{c.payer}</Typography>
                <Chip label={c.status === 'PAYMENT_EXCEPTION' ? 'Funding Delayed' : c.status.replace('_', ' ')} size="small" color="warning" />
              </Box>
            </Box>
          ))}
        </Paper>
      )}

      {recent_claims.length > 0 && (
        <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
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
                px: 1,
                cursor: 'pointer',
                '&:hover': { bgcolor: '#f9fafb' },
                borderBottom: '1px solid #f3f4f6',
              }}
              onClick={() => onClaimSelect(c)}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  {c.claim_token}
                </Typography>
                <Typography variant="body2" color="text.secondary">{c.payer}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2">
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(c.amount_cents / 100)}
                </Typography>
                <Chip
                  label={c.status === 'PAYMENT_EXCEPTION' ? 'Funding Delayed' : c.status.replace('_', ' ')}
                  size="small"
                  sx={{ bgcolor: (statusColors[c.status] || '#6b7280') + '20', color: statusColors[c.status] || '#6b7280', fontWeight: 600, fontSize: '0.7rem' }}
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
      <Container maxWidth="lg">
        <Box sx={{ mt: 4, textAlign: 'center' }}>
          <Typography>Loading...</Typography>
        </Box>
      </Container>
    );
  }

  if (!user) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ mt: 8 }}>
          <Typography variant="h4" component="h1" gutterBottom align="center" sx={{ fontWeight: 600 }}>
            Spoonbill Practice Portal
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <LoginPage onLogin={handleLogin} />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
            Practice Portal
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Chip
              label="Practice Manager"
              size="small"
              sx={{ bgcolor: '#e5e7eb', color: '#374151', fontWeight: 600 }}
            />
            <Typography variant="body2" color="text.secondary">
              {user.email}
            </Typography>
            <Typography
              variant="body2"
              sx={{ cursor: 'pointer', textDecoration: 'underline' }}
              onClick={handleLogout}
            >
              Logout
            </Typography>
          </Box>
        </Box>

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
          <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
            <Tab label="Dashboard" />
            <Tab label="Claims" />
            <Tab label="Payments" />
          </Tabs>
        </Box>

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
    </Container>
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
