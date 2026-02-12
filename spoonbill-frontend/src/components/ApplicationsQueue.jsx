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
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';

import { getApplications, getApplication, reviewApplication } from '../api.js';

const statusColors = {
  SUBMITTED: { bg: '#fef3c7', color: '#92400e' },
  APPROVED: { bg: '#d1fae5', color: '#065f46' },
  DECLINED: { bg: '#fee2e2', color: '#991b1b' },
  NEEDS_INFO: { bg: '#dbeafe', color: '#1e40af' },
};

const urgencyColors = {
  LOW: { bg: '#f3f4f6', color: '#374151' },
  MEDIUM: { bg: '#fef3c7', color: '#92400e' },
  HIGH: { bg: '#fed7aa', color: '#c2410c' },
  CRITICAL: { bg: '#fee2e2', color: '#991b1b' },
};

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


function ApplicationDetailDialog({ open, onClose, applicationId, onReviewComplete }) {
  const [application, setApplication] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [reviewNotes, setReviewNotes] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [approvalResult, setApprovalResult] = React.useState(null);

  React.useEffect(() => {
    if (open && applicationId) {
      setLoading(true);
      setError(null);
      setApprovalResult(null);
      getApplication(applicationId)
        .then(setApplication)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, [open, applicationId]);

  const handleReview = async (action) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await reviewApplication(applicationId, action, reviewNotes || null);
      if (action === 'APPROVE') {
        setApprovalResult(result);
      } else {
        onReviewComplete();
        onClose();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const canReview = application && ['SUBMITTED', 'NEEDS_INFO'].includes(application.status);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Practice Application #{applicationId}
      </DialogTitle>
      <DialogContent dividers>
        {loading && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}
        
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        
        {approvalResult && (
          <Alert severity="success" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>Application Approved</Typography>
            <Typography variant="body2">Practice ID: {approvalResult.practice_id}</Typography>
            <Typography variant="body2">Manager Email: {approvalResult.manager_email}</Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: '#f0fdf4', borderRadius: 1, border: '1px solid #86efac' }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Invite Link (expires in 7 days):
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  fontFamily: 'monospace', 
                  wordBreak: 'break-all',
                  bgcolor: '#fff',
                  p: 1,
                  borderRadius: 0.5,
                  border: '1px solid #e5e7eb'
                }}
              >
                {approvalResult.invite_url}
              </Typography>
              <Button
                size="small"
                variant="outlined"
                sx={{ mt: 1 }}
                onClick={() => {
                  navigator.clipboard.writeText(approvalResult.invite_url);
                }}
              >
                Copy Invite Link
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
              Share this link with the practice manager. They will use it to set their password and activate their account.
            </Typography>
          </Alert>
        )}
        
        {application && !loading && (
          <Stack spacing={3}>
            <Box>
              <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                <Chip
                  label={application.status}
                  size="small"
                  sx={{
                    bgcolor: statusColors[application.status]?.bg || '#f3f4f6',
                    color: statusColors[application.status]?.color || '#374151',
                    fontWeight: 600,
                  }}
                />
                <Chip
                  label={`Urgency: ${application.urgency_level}`}
                  size="small"
                  sx={{
                    bgcolor: urgencyColors[application.urgency_level]?.bg || '#f3f4f6',
                    color: urgencyColors[application.urgency_level]?.color || '#374151',
                  }}
                />
              </Stack>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Practice Information
              </Typography>
              <Typography variant="h6">{application.legal_name}</Typography>
              <Typography variant="body2">{application.address}</Typography>
              <Typography variant="body2">Phone: {application.phone}</Typography>
              {application.website && (
                <Typography variant="body2">Website: {application.website}</Typography>
              )}
              {application.tax_id && (
                <Typography variant="body2">Tax ID: {application.tax_id}</Typography>
              )}
              <Typography variant="body2">Type: {application.practice_type.replace(/_/g, ' ')}</Typography>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Operations
              </Typography>
              <Typography variant="body2">Years in Operation: {application.years_in_operation}</Typography>
              <Typography variant="body2">Providers: {application.provider_count}</Typography>
              <Typography variant="body2">Operatories: {application.operatory_count}</Typography>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Financial
              </Typography>
              <Typography variant="body2">Monthly Collections: {application.avg_monthly_collections_range}</Typography>
              <Typography variant="body2">Insurance Mix: {application.insurance_vs_self_pay_mix}</Typography>
              {application.top_payers && (
                <Typography variant="body2">Top Payers: {application.top_payers}</Typography>
              )}
              {application.avg_ar_days && (
                <Typography variant="body2">Avg AR Days: {application.avg_ar_days}</Typography>
              )}
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Billing
              </Typography>
              <Typography variant="body2">Billing Model: {application.billing_model}</Typography>
              {application.follow_up_frequency && (
                <Typography variant="body2">Follow-up Frequency: {application.follow_up_frequency}</Typography>
              )}
              {application.practice_management_software && (
                <Typography variant="body2">Software: {application.practice_management_software}</Typography>
              )}
              {application.claims_per_month && (
                <Typography variant="body2">Claims/Month: {application.claims_per_month}</Typography>
              )}
              <Typography variant="body2">
                Electronic Claims: {application.electronic_claims ? 'Yes' : 'No'}
              </Typography>
            </Box>

            {application.stated_goal && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Stated Goal
                  </Typography>
                  <Typography variant="body2">{application.stated_goal}</Typography>
                </Box>
              </>
            )}

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Contact
              </Typography>
              <Typography variant="body2">Name: {application.contact_name}</Typography>
              <Typography variant="body2">Email: {application.contact_email}</Typography>
              {application.contact_phone && (
                <Typography variant="body2">Phone: {application.contact_phone}</Typography>
              )}
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Timeline
              </Typography>
              <Typography variant="body2">Submitted: {formatDate(application.created_at)}</Typography>
              {application.reviewed_at && (
                <Typography variant="body2">Reviewed: {formatDate(application.reviewed_at)}</Typography>
              )}
            </Box>

            {application.review_notes && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Review Notes
                  </Typography>
                  <Typography variant="body2">{application.review_notes}</Typography>
                </Box>
              </>
            )}

            {canReview && !approvalResult && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Review Decision
                  </Typography>
                  <TextField
                    label="Review Notes (optional)"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    fullWidth
                    multiline
                    rows={2}
                    sx={{ mb: 2 }}
                  />
                  <Stack direction="row" spacing={2}>
                    <Button
                      variant="contained"
                      color="success"
                      onClick={() => handleReview('APPROVE')}
                      disabled={submitting}
                    >
                      {submitting ? 'Processing...' : 'Approve'}
                    </Button>
                    <Button
                      variant="outlined"
                      color="warning"
                      onClick={() => handleReview('NEEDS_INFO')}
                      disabled={submitting}
                    >
                      Request Info
                    </Button>
                    <Button
                      variant="outlined"
                      color="error"
                      onClick={() => handleReview('DECLINE')}
                      disabled={submitting}
                    >
                      Decline
                    </Button>
                  </Stack>
                </Box>
              </>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function ApplicationsQueue() {
  const [applications, setApplications] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [selectedId, setSelectedId] = React.useState(null);
  const [detailOpen, setDetailOpen] = React.useState(false);

  const fetchApplications = React.useCallback(async () => {
    try {
      const data = await getApplications();
      setApplications(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchApplications();
    const interval = setInterval(fetchApplications, 10000);
    return () => clearInterval(interval);
  }, [fetchApplications]);

  const openDetail = (id) => {
    setSelectedId(id);
    setDetailOpen(true);
  };

  const handleReviewComplete = () => {
    fetchApplications();
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

  const pendingCount = applications.filter(a => ['SUBMITTED', 'NEEDS_INFO'].includes(a.status)).length;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h6">
          Practice Applications
          {pendingCount > 0 && (
            <Chip
              label={`${pendingCount} pending`}
              size="small"
              sx={{ ml: 1, bgcolor: '#fef3c7', color: '#92400e' }}
            />
          )}
        </Typography>
      </Stack>

      {applications.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">No applications yet</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Practice Name</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Contact</TableCell>
                <TableCell>Urgency</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Submitted</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {applications.map((app) => (
                <TableRow key={app.id} hover>
                  <TableCell>#{app.id}</TableCell>
                  <TableCell>{app.legal_name}</TableCell>
                  <TableCell>{app.practice_type.replace(/_/g, ' ')}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{app.contact_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {app.contact_email}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={app.urgency_level}
                      size="small"
                      sx={{
                        bgcolor: urgencyColors[app.urgency_level]?.bg || '#f3f4f6',
                        color: urgencyColors[app.urgency_level]?.color || '#374151',
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={app.status}
                      size="small"
                      sx={{
                        bgcolor: statusColors[app.status]?.bg || '#f3f4f6',
                        color: statusColors[app.status]?.color || '#374151',
                        fontWeight: 600,
                      }}
                    />
                  </TableCell>
                  <TableCell>{formatDate(app.created_at)}</TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openDetail(app.id)}
                    >
                      Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ApplicationDetailDialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        applicationId={selectedId}
        onReviewComplete={handleReviewComplete}
      />
    </Box>
  );
}
