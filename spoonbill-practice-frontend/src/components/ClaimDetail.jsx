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
import { getClaim, listDocuments, uploadDocument, getDocumentDownloadUrl, getAuthToken } from '../api';

const statusColors = {
  NEW: 'default',
  NEEDS_REVIEW: 'warning',
  APPROVED: 'success',
  PAID: 'info',
  COLLECTING: 'info',
  CLOSED: 'default',
  DECLINED: 'error',
};

function ClaimDetail({ claimId, open, onClose }) {
  const [claim, setClaim] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [claimData, docsData] = await Promise.all([
        getClaim(claimId),
        listDocuments(claimId),
      ]);
      setClaim(claimData);
      setDocuments(docsData);
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
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogContent>
          <Alert severity="error">{error}</Alert>
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
          <Typography variant="h6">Claim #{claim.id}</Typography>
          <Chip
            label={claim.status}
            color={statusColors[claim.status] || 'default'}
          />
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3 }}>
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
