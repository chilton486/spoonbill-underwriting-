import { useState, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import { listPayments } from '../api';

const paymentStatusColors = {
  QUEUED: { bg: '#fef3c7', color: '#92400e' },
  SENT: { bg: '#dbeafe', color: '#1e40af' },
  CONFIRMED: { bg: '#d1fae5', color: '#065f46' },
  FAILED: { bg: '#fee2e2', color: '#991b1b' },
};

function PaymentsList() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPayments = useCallback(async () => {
    try {
      const data = await listPayments();
      setPayments(data);
    } catch (err) {
      console.error('Failed to fetch payments:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPayments();
    const interval = setInterval(fetchPayments, 5000);
    return () => clearInterval(interval);
  }, [fetchPayments]);

  const formatAmount = (cents) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (payments.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid #e0e0e0' }} elevation={0}>
        <Typography color="text.secondary">No payments yet.</Typography>
      </Paper>
    );
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>Payments</Typography>
      <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Claim</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Confirmed</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.map((p) => (
              <TableRow key={p.id}>
                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{p.claim_token}</TableCell>
                <TableCell>
                  <Chip
                    label={p.status}
                    size="small"
                    sx={{
                      bgcolor: paymentStatusColors[p.status]?.bg || '#f3f4f6',
                      color: paymentStatusColors[p.status]?.color || '#374151',
                      fontWeight: 600,
                    }}
                  />
                  {p.status === 'FAILED' && p.failure_message && (
                    <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
                      {p.failure_message}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">{formatAmount(p.amount_cents)}</TableCell>
                <TableCell>{formatDate(p.created_at)}</TableCell>
                <TableCell>{formatDate(p.confirmed_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default PaymentsList;
