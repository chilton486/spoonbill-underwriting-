import { useState } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import { submitClaim } from '../api';

function SubmitClaimDialog({ open, onClose, onSubmitted }) {
  const [formData, setFormData] = useState({
    patient_name: '',
    payer: '',
    amount_cents: '',
    procedure_date: '',
    procedure_codes: '',
    external_claim_id: '',
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const amountCents = Math.round(parseFloat(formData.amount_cents) * 100);
      if (isNaN(amountCents) || amountCents <= 0) {
        throw new Error('Amount must be a positive number');
      }

      await submitClaim({
        patient_name: formData.patient_name || null,
        payer: formData.payer,
        amount_cents: amountCents,
        procedure_date: formData.procedure_date || null,
        procedure_codes: formData.procedure_codes || null,
        external_claim_id: formData.external_claim_id || null,
      });

      setFormData({
        patient_name: '',
        payer: '',
        amount_cents: '',
        procedure_date: '',
        procedure_codes: '',
        external_claim_id: '',
      });
      onSubmitted();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Submit New Claim</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Patient Name"
              name="patient_name"
              value={formData.patient_name}
              onChange={handleChange}
              fullWidth
            />
            <TextField
              label="Payer"
              name="payer"
              value={formData.payer}
              onChange={handleChange}
              required
              fullWidth
            />
            <TextField
              label="Amount ($)"
              name="amount_cents"
              type="number"
              inputProps={{ step: '0.01', min: '0.01' }}
              value={formData.amount_cents}
              onChange={handleChange}
              required
              fullWidth
              helperText="Enter amount in dollars (e.g., 150.00)"
            />
            <TextField
              label="Procedure Date"
              name="procedure_date"
              type="date"
              value={formData.procedure_date}
              onChange={handleChange}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Procedure Codes"
              name="procedure_codes"
              value={formData.procedure_codes}
              onChange={handleChange}
              fullWidth
              helperText="Comma-separated codes (e.g., D0120, D1110)"
            />
            <TextField
              label="External Claim ID"
              name="external_claim_id"
              value={formData.external_claim_id}
              onChange={handleChange}
              fullWidth
              helperText="Your internal reference ID"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? 'Submitting...' : 'Submit Claim'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

export default SubmitClaimDialog;
