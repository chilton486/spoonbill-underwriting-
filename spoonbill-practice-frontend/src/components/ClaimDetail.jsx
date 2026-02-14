import { useState, useEffect, useCallback } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DownloadIcon from '@mui/icons-material/Download';
import { getClaim, listDocuments, uploadDocument, getDocumentDownloadUrl, getAuthToken, getPaymentStatus } from '../api';

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

const LIFECYCLE_STEPS = ['NEW', 'NEEDS_REVIEW', 'APPROVED', 'PAID', 'COLLECTING', 'CLOSED'];

const stepColors = {
  completed: '#059669',
  current: '#2563eb',
  upcoming: '#d1d5db',
  exception: '#dc2626',
};

const whatHappensNext = {
  NEW: 'Your claim has been submitted and is being reviewed by our underwriting system.',
  NEEDS_REVIEW: 'Your claim requires additional review. You may be asked to provide supporting documents.',
  APPROVED: 'Your claim has been approved. Payment is being processed and will be sent shortly.',
  PAID: 'Payment has been sent. Spoonbill is now collecting from the payer on your behalf.',
  COLLECTING: 'Collection is in progress. Your claim will be closed once the payer has settled.',
  CLOSED: 'This claim is complete. No further action is needed.',
  DECLINED: 'This claim was declined. Contact your Spoonbill representative if you have questions.',
  PAYMENT_EXCEPTION: 'Funding delayed \u2014 Spoonbill is reviewing. No action needed from you at this time.',
};

function LifecycleTimeline({ status }) {
  const currentIdx = LIFECYCLE_STEPS.indexOf(status);
  const isException = status === 'PAYMENT_EXCEPTION';
  const isDeclined = status === 'DECLINED';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0, mb: 2, overflowX: 'auto' }}>
      {LIFECYCLE_STEPS.map((step, idx) => {
        let color = stepColors.upcoming;
        let fontWeight = 400;
        if (isException && step === 'APPROVED') {
          color = stepColors.exception;
          fontWeight = 700;
        } else if (isDeclined) {
          color = stepColors.upcoming;
        } else if (idx < currentIdx) {
          color = stepColors.completed;
        } else if (idx === currentIdx) {
          color = stepColors.current;
          fontWeight = 700;
        }

        return (
          <Box key={step} sx={{ display: 'flex', alignItems: 'center' }}>
            <Box sx={{ textAlign: 'center', minWidth: 70 }}>
              <Box
                sx={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  bgcolor: color,
                  mx: 'auto',
                  mb: 0.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {idx < currentIdx && !isDeclined && (
                  <Typography sx={{ color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>&#10003;</Typography>
                )}
              </Box>
              <Typography variant="caption" sx={{ fontSize: '0.65rem', fontWeight, color: color === stepColors.upcoming ? '#9ca3af' : color }}>
                {step.replace('_', ' ')}
              </Typography>
            </Box>
            {idx < LIFECYCLE_STEPS.length - 1 && (
              <Box sx={{ width: 24, height: 2, bgcolor: idx < currentIdx && !isDeclined ? stepColors.completed : stepColors.upcoming, mx: 0.5 }} />
            )}
          </Box>
        );
      })}
      {isException && (
        <Box sx={{ ml: 2, display: 'flex', alignItems: 'center' }}>
          <Chip label="PAYMENT EXCEPTION" size="small" sx={{ bgcolor: '#fee2e2', color: '#991b1b', fontWeight: 600 }} />
        </Box>
      )}
      {isDeclined && (
        <Box sx={{ ml: 2, display: 'flex', alignItems: 'center' }}>
          <Chip label="DECLINED" size="small" sx={{ bgcolor: '#fee2e2', color: '#991b1b', fontWeight: 600 }} />
        </Box>
      )}
    </Box>
  );
}

function ClaimDetail({ claimId, open, onClose }) {
  const [claim, setClaim] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [payment, setPayment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [claimData, docsData, paymentData] = await Promise.all([
        getClaim(claimId),
        listDocuments(claimId),
        getPaymentStatus(claimId).catch(() => null),
      ]);
      setClaim(claimData);
      setDocuments(docsData);
      setPayment(paymentData);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [claimId]);

  useEffect(() => {
    if (open && claimId) {
      fetchData();
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    }
  }, [open, claimId, fetchData]);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      await uploadDocument(claimId, file);
      const docsData = await listDocuments(claimId);
      setDocuments(docsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = (docId, filename) => {
    const url = getDocumentDownloadUrl(docId);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.target = '_blank';
    const token = getAuthToken();
    if (token) {
      fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.blob())
        .then((blob) => {
          const blobUrl = window.URL.createObjectURL(blob);
          link.href = blobUrl;
          link.click();
          window.URL.revokeObjectURL(blobUrl);
        });
    } else {
      link.click();
    }
  };

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
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  if (error) {
    const isSessionError = error.includes('Session expired');
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogContent>
          <Alert severity={isSessionError ? 'warning' : 'error'} sx={{ mb: 2 }}>{error}</Alert>
          {!isSessionError && (
            <Button variant="outlined" size="small" onClick={() => { setError(null); setLoading(true); fetchData(); }}>
              Try Again
            </Button>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h6">Claim #{claim.id}</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
              {claim.claim_token}
            </Typography>
          </Box>
          <Chip
            label={claim.status === 'PAYMENT_EXCEPTION' ? 'Funding Delayed' : claim.status}
            color={statusColors[claim.status] || 'default'}
          />
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <LifecycleTimeline status={claim.status} />

        <Alert
          severity={claim.status === 'DECLINED' || claim.status === 'PAYMENT_EXCEPTION' ? 'warning' : 'info'}
          sx={{ mb: 3 }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>What happens next?</Typography>
          <Typography variant="body2">{whatHappensNext[claim.status] || 'Your claim is being processed.'}</Typography>
        </Alert>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Claim Token</Typography>
            <Typography sx={{ fontFamily: 'monospace' }}>{claim.claim_token}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Patient Name</Typography>
            <Typography>{claim.patient_name || '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Payer</Typography>
            <Typography>{claim.payer}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Amount</Typography>
            <Typography>{formatAmount(claim.amount_cents)}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Procedure Date</Typography>
            <Typography>{claim.procedure_date || '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Procedure Codes</Typography>
            <Typography>{claim.procedure_codes || '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">External Claim ID</Typography>
            <Typography>{claim.external_claim_id || '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Submitted</Typography>
            <Typography>{formatDate(claim.created_at)}</Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 600 }}>
          Underwriting Decisions
        </Typography>
        {claim.underwriting_decisions && claim.underwriting_decisions.length > 0 ? (
          <List dense>
            {claim.underwriting_decisions.map((decision) => (
              <ListItem key={decision.id} sx={{ bgcolor: '#f5f5f5', mb: 1, borderRadius: 1 }}>
                <ListItemText
                  primary={
                    <Chip
                      label={decision.decision}
                      size="small"
                      color={decision.decision === 'APPROVE' ? 'success' : decision.decision === 'DECLINE' ? 'error' : 'warning'}
                    />
                  }
                  secondary={
                    <>
                      <Typography variant="body2" component="span">
                        {decision.reasons || 'No reasons provided'}
                      </Typography>
                      <br />
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(decision.decided_at)}
                      </Typography>
                    </>
                  }
                />
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography color="text.secondary">No underwriting decisions yet.</Typography>
        )}

        <Divider sx={{ my: 2 }} />

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Documents
          </Typography>
          <Button
            component="label"
            variant="outlined"
            size="small"
            startIcon={<CloudUploadIcon />}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload'}
            <input type="file" hidden onChange={handleFileUpload} />
          </Button>
        </Box>
        {documents.length > 0 ? (
          <List dense>
            {documents.map((doc) => (
              <ListItem
                key={doc.id}
                secondaryAction={
                  <IconButton edge="end" onClick={() => handleDownload(doc.id, doc.filename)}>
                    <DownloadIcon />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={doc.filename}
                  secondary={`${doc.content_type} - ${formatDate(doc.created_at)}`}
                />
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography color="text.secondary">No documents uploaded yet.</Typography>
        )}

        {payment && (
          <>
            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 600 }}>
              Payment Status
            </Typography>
            <Box sx={{ bgcolor: '#f5f5f5', p: 2, borderRadius: 1 }}>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Status</Typography>
                  <Box>
                    <Chip
                      label={payment.status}
                      size="small"
                      color={payment.status === 'CONFIRMED' ? 'success' : payment.status === 'FAILED' ? 'error' : 'warning'}
                    />
                  </Box>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Amount</Typography>
                  <Typography>{formatAmount(payment.amount_cents)}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Provider</Typography>
                  <Typography>{payment.provider}</Typography>
                </Box>
                {payment.provider_reference && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">Reference</Typography>
                    <Typography sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>{payment.provider_reference}</Typography>
                  </Box>
                )}
                {payment.confirmed_at && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">Confirmed</Typography>
                    <Typography>{formatDate(payment.confirmed_at)}</Typography>
                  </Box>
                )}
              </Box>
              {payment.failure_code && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {payment.failure_code}: {payment.failure_message}
                </Alert>
              )}
            </Box>
          </>
        )}

        <Divider sx={{ my: 2 }} />

        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 600 }}>
          Audit Trail
        </Typography>
        {claim.audit_events && claim.audit_events.length > 0 ? (
          <List dense>
            {claim.audit_events.map((event) => (
              <ListItem key={event.id} sx={{ bgcolor: '#f5f5f5', mb: 1, borderRadius: 1 }}>
                <ListItemText
                  primary={event.action}
                  secondary={
                    <>
                      {event.from_status && event.to_status && (
                        <Typography variant="body2" component="span">
                          {event.from_status} → {event.to_status}
                        </Typography>
                      )}
                      <br />
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(event.created_at)}
                      </Typography>
                    </>
                  }
                />
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography color="text.secondary">No audit events yet.</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default ClaimDetail;
