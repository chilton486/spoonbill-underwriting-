import * as React from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'

function FieldRow({ label, value }) {
  return (
    <Stack direction="row" spacing={2} sx={{ justifyContent: 'space-between' }}>
      <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.75)' }}>{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{value}</Typography>
    </Stack>
  )
}

export default function ClaimDetailDialog({ open, onClose, claim, practice }) {
  if (!claim) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
        <span>Claim {claim.claim_id}</span>
        <Chip size="small" label={claim.status} />
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.25}>
          <FieldRow label="Practice" value={practice?.id || claim.practice_id} />
          <FieldRow label="Payer" value={claim.payer} />
          <FieldRow label="Procedure Code" value={claim.procedure_code} />
          <FieldRow label="Billed Amount" value={`$${claim.billed_amount.toLocaleString()}`} />
          <FieldRow label="Expected Allowed" value={`$${claim.expected_allowed_amount.toLocaleString()}`} />
          <FieldRow label="Funded Amount" value={`$${claim.funded_amount.toLocaleString()}`} />
          <FieldRow label="Submission Date" value={claim.submission_date} />
          <FieldRow label="Adjudication Status" value={claim.adjudication_status} />
          <FieldRow label="Underwriting Score" value={claim.underwriting_confidence_score} />
          <FieldRow label="Decline Reason" value={claim.decline_reason_code || '—'} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
