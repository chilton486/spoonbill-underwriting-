import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';

import { getClaims, getPaymentForClaim, retryPayment, cancelPayment, resolvePayment } from '../api.js';

function formatDate(dateString) {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatAmount(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);
}

export default function PaymentExceptions() {
  const [claims, setClaims] = React.useState([]);
  const [payments, setPayments] = React.useState({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [actionLoading, setActionLoading] = React.useState(null);
  const [actionResult, setActionResult] = React.useState(null);

  const fetchData = React.useCallback(async () => {
    try {
      const allClaims = await getClaims('PAYMENT_EXCEPTION');
      setClaims(allClaims);

      const paymentMap = {};
      for (const claim of allClaims) {
        try {
          const payment = await getPaymentForClaim(claim.id);
          if (payment) {
            paymentMap[claim.id] = payment;
          }
        } catch (e) {
          // ignore
        }
      }
      setPayments(paymentMap);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRetry = async (claimId) => {
    const payment = payments[claimId];
    if (!payment) return;
    setActionLoading(claimId);
    setActionResult(null);
    try {
      await retryPayment(payment.id);
      setActionResult({ claimId, type: 'success', message: 'Payment retry initiated' });
      await fetchData();
    } catch (e) {
      setActionResult({ claimId, type: 'error', message: e.message });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (claimId) => {
    const payment = payments[claimId];
    if (!payment) return;
    setActionLoading(claimId);
    setActionResult(null);
    try {
      await cancelPayment(payment.id);
      setActionResult({ claimId, type: 'success', message: 'Payment cancelled' });
      await fetchData();
    } catch (e) {
      setActionResult({ claimId, type: 'error', message: e.message });
    } finally {
      setActionLoading(null);
    }
  };

  const handleResolve = async (claimId) => {
    const payment = payments[claimId];
    if (!payment) return;
    setActionLoading(claimId);
    setActionResult(null);
    try {
      await resolvePayment(payment.id);
      setActionResult({ claimId, type: 'success', message: 'Payment resolved' });
      await fetchData();
    } catch (e) {
      setActionResult({ claimId, type: 'error', message: e.message });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Payment Exceptions
        <Chip
          label={claims.length}
          size="small"
          sx={{ ml: 1, bgcolor: claims.length > 0 ? '#fee2e2' : '#e5e7eb', color: claims.length > 0 ? '#991b1b' : '#374151' }}
        />
      </Typography>

      {actionResult && (
        <Alert severity={actionResult.type} sx={{ mb: 2 }} onClose={() => setActionResult(null)}>
          {actionResult.message}
        </Alert>
      )}

      {claims.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">No payment exceptions</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Claim ID</TableCell>
                <TableCell>Token</TableCell>
                <TableCell>Practice</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Failure Reason</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {claims.map((claim) => {
                const payment = payments[claim.id];
                return (
                  <TableRow key={claim.id}>
                    <TableCell>#{claim.id}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                      {claim.claim_token}
                    </TableCell>
                    <TableCell>{claim.practice_name || `Practice #${claim.practice_id}`}</TableCell>
                    <TableCell align="right">{formatAmount(claim.amount_cents)}</TableCell>
                    <TableCell>
                      {payment ? (
                        <Box>
                          <Chip label={payment.failure_code || 'UNKNOWN'} size="small" color="error" />
                          {payment.failure_message && (
                            <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                              {payment.failure_message}
                            </Typography>
                          )}
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">-</Typography>
                      )}
                    </TableCell>
                    <TableCell>{formatDate(claim.created_at)}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size="small"
                          variant="contained"
                          color="primary"
                          disabled={actionLoading === claim.id || !payment}
                          onClick={() => handleRetry(claim.id)}
                        >
                          {actionLoading === claim.id ? '...' : 'Retry'}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="success"
                          disabled={actionLoading === claim.id || !payment}
                          onClick={() => handleResolve(claim.id)}
                        >
                          Resolve
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          disabled={actionLoading === claim.id || !payment}
                          onClick={() => handleCancel(claim.id)}
                        >
                          Cancel
                        </Button>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
