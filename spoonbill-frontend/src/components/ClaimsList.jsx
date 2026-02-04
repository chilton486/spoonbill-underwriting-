import * as React from 'react'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Typography from '@mui/material/Typography'
import Stack from '@mui/material/Stack'

function formatCurrency(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(cents / 100)
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

const STATUS_COLORS = {
  NEW: 'info',
  NEEDS_REVIEW: 'warning',
  APPROVED: 'success',
  PAID: 'success',
  COLLECTING: 'info',
  CLOSED: 'default',
  DECLINED: 'error'
}

export default function ClaimsList({ claims, onOpenClaim, onTransition, loadingClaimId }) {
  if (!claims || claims.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">No claims in this queue</Typography>
      </Paper>
    )
  }

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>ID</TableCell>
            <TableCell>Payer</TableCell>
            <TableCell>Patient</TableCell>
            <TableCell>Amount</TableCell>
            <TableCell>Procedure Date</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Created</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {claims.map((claim) => (
            <TableRow 
              key={claim.id} 
              hover 
              sx={{ cursor: 'pointer' }}
              onClick={() => onOpenClaim(claim)}
            >
              <TableCell>{claim.id}</TableCell>
              <TableCell>{claim.payer}</TableCell>
              <TableCell>{claim.patient_name || '-'}</TableCell>
              <TableCell>{formatCurrency(claim.amount_cents)}</TableCell>
              <TableCell>{formatDate(claim.procedure_date)}</TableCell>
              <TableCell>
                <Chip 
                  label={claim.status.replace('_', ' ')} 
                  size="small" 
                  color={STATUS_COLORS[claim.status] || 'default'}
                />
              </TableCell>
              <TableCell>{formatDate(claim.created_at)}</TableCell>
              <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                <Stack direction="row" spacing={1} justifyContent="flex-end">
                  <Button 
                    size="small" 
                    variant="outlined"
                    onClick={() => onOpenClaim(claim)}
                  >
                    View
                  </Button>
                  {loadingClaimId === claim.id && (
                    <CircularProgress size={24} />
                  )}
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
