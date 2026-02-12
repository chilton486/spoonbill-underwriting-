import { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';

import LoginPage from './components/LoginPage';
import ClaimsList from './components/ClaimsList';
import ClaimDetail from './components/ClaimDetail';
import SubmitClaimDialog from './components/SubmitClaimDialog';
import SetPasswordPage from './components/SetPasswordPage';
import { getCurrentUser, getAuthToken, logout, listClaims } from './api';

function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [claims, setClaims] = useState([]);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({});
  const filtersRef = useRef({});

  const fetchClaims = useCallback(async (currentFilters = {}) => {
    try {
      const data = await listClaims(currentFilters);
      setClaims(data);
    } catch (err) {
      console.error('Failed to fetch claims:', err);
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
      const interval = setInterval(() => fetchClaims(filtersRef.current), 5000);
      return () => clearInterval(interval);
    }
  }, [user, fetchClaims]);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    filtersRef.current = newFilters;
    fetchClaims(newFilters);
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
  };

  const handleClaimSubmitted = () => {
    fetchClaims();
    setSubmitDialogOpen(false);
  };

  const handleClaimSelect = (claim) => {
    setSelectedClaim(claim);
  };

  const handleClaimClose = () => {
    setSelectedClaim(null);
    fetchClaims();
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

        <ClaimsList
          claims={claims}
          onClaimSelect={handleClaimSelect}
          onSubmitClick={() => setSubmitDialogOpen(true)}
          onFilterChange={handleFilterChange}
        />

        {selectedClaim && (
          <ClaimDetail
            claimId={selectedClaim.id}
            open={!!selectedClaim}
            onClose={handleClaimClose}
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
