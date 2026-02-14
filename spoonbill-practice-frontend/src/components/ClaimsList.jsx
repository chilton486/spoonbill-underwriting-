import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';

const statusColors = {
  NEW: 'default',
  NEEDS_REVIEW: 'warning',
  APPROVED: 'success',
  PAID: 'info',
  COLLECTING: 'info',
  CLOSED: 'default',
  DECLINED: 'error',
  PAYMENT_EXCEPTION: 'error',
};

function ClaimsList({ claims, onClaimSelect, onSubmitClick, onFilterChange }) {
  const [filters, setFilters] = useState({
    claim_token: '',
    q: '',
    submitted_from: '',
    submitted_to: '',
  });

  const formatAmount = (cents) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const handleFilterChange = (field, value) => {
    const newFilters = { ...filters, [field]: value };
    setFilters(newFilters);
  };

  const handleApplyFilters = () => {
    if (onFilterChange) {
      const activeFilters = {};
      Object.entries(filters).forEach(([key, value]) => {
        if (value) activeFilters[key] = value;
      });
      onFilterChange(activeFilters);
    }
  };

  const handleResetFilters = () => {
    const emptyFilters = {
      claim_token: '',
      q: '',
      submitted_from: '',
      submitted_to: '',
    };
    setFilters(emptyFilters);
    if (onFilterChange) {
      onFilterChange({});
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Claims</Typography>
        <Button variant="contained" onClick={onSubmitClick}>
          Submit New Claim
        </Button>
      </Box>

      <Paper sx={{ p: 2, mb: 2, border: '1px solid #e0e0e0' }} elevation={0}>
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Filters</Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
          <TextField
            label="Claim Token"
            size="small"
            value={filters.claim_token}
            onChange={(e) => handleFilterChange('claim_token', e.target.value)}
            placeholder="SB-CLM-..."
            sx={{ minWidth: 150 }}
          />
          <TextField
            label="Search"
            size="small"
            value={filters.q}
            onChange={(e) => handleFilterChange('q', e.target.value)}
            placeholder="Patient, payer..."
            sx={{ minWidth: 150 }}
          />
          <TextField
            label="Submitted From"
            type="date"
            size="small"
            value={filters.submitted_from}
            onChange={(e) => handleFilterChange('submitted_from', e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />
          <TextField
            label="Submitted To"
            type="date"
            size="small"
            value={filters.submitted_to}
            onChange={(e) => handleFilterChange('submitted_to', e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />
          <Button variant="outlined" size="small" onClick={handleApplyFilters}>
            Apply
          </Button>
          <Button variant="text" size="small" onClick={handleResetFilters}>
            Reset
          </Button>
        </Stack>
      </Paper>

      {claims.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid #e0e0e0' }} elevation={0}>
          <Typography color="text.secondary">No claims yet. Submit your first claim to get started.</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Token</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>Payer</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Procedure Date</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {claims.map((claim) => (
                <TableRow
                  key={claim.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => onClaimSelect(claim)}
                >
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{claim.claim_token}</TableCell>
                  <TableCell>{claim.patient_name || '-'}</TableCell>
                  <TableCell>{claim.payer}</TableCell>
                  <TableCell align="right">{formatAmount(claim.amount_cents)}</TableCell>
                  <TableCell>{formatDate(claim.procedure_date)}</TableCell>
                  <TableCell>
                    <Chip
                      label={claim.status}
                      size="small"
                      color={statusColors[claim.status] || 'default'}
                    />
                  </TableCell>
                  <TableCell>{formatDate(claim.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

export default ClaimsList;
