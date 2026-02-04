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

const statusColors = {
  NEW: 'default',
  NEEDS_REVIEW: 'warning',
  APPROVED: 'success',
  PAID: 'info',
  COLLECTING: 'info',
  CLOSED: 'default',
  DECLINED: 'error',
};

function ClaimsList({ claims, onClaimSelect, onSubmitClick }) {
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Claims</Typography>
        <Button variant="contained" onClick={onSubmitClick}>
          Submit New Claim
        </Button>
      </Box>

      {claims.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center', border: '1px solid #e0e0e0' }} elevation={0}>
          <Typography color="text.secondary">No claims yet. Submit your first claim to get started.</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
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
                  <TableCell>{claim.id}</TableCell>
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
