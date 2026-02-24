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

import MenuItem from '@mui/material/MenuItem';

import { getApplications, getApplication, reviewApplication, computeUnderwritingScore, overrideUnderwritingScore } from '../api.js';

const gradeColors = {
  GREEN: { bg: '#d1fae5', color: '#065f46' },
  YELLOW: { bg: '#fef3c7', color: '#92400e' },
  RED: { bg: '#fee2e2', color: '#991b1b' },
};

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


function ScoreOverrideDialog({ open, onClose, applicationId, currentScore, currentGrade, onOverrideComplete }) {
  const [score, setScore] = React.useState(currentScore || '');
  const [grade, setGrade] = React.useState(currentGrade || 'GREEN');
  const [reason, setReason] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (open) {
      setScore(currentScore || '');
      setGrade(currentGrade || 'GREEN');
      setReason('');
      setError(null);
    }
  }, [open, currentScore, currentGrade]);

  const handleSubmit = async () => {
    if (!reason.trim()) { setError('Reason is required'); return; }
    const numScore = parseFloat(score);
    if (isNaN(numScore) || numScore < 0 || numScore > 100) { setError('Score must be 0-100'); return; }
    setSubmitting(true);
    setError(null);
    try {
      await overrideUnderwritingScore(applicationId, numScore, grade, reason);
      onOverrideComplete();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Override Underwriting Score</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField label="Score (0-100)" type="number" value={score} onChange={(e) => setScore(e.target.value)} fullWidth slotProps={{ htmlInput: { min: 0, max: 100, step: 0.1 } }} />
          <TextField select label="Grade" value={grade} onChange={(e) => setGrade(e.target.value)} fullWidth>
            <MenuItem value="GREEN">GREEN</MenuItem>
            <MenuItem value="YELLOW">YELLOW</MenuItem>
            <MenuItem value="RED">RED</MenuItem>
          </TextField>
          <TextField label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} fullWidth multiline rows={2} required />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={submitting}>{submitting ? 'Saving...' : 'Override'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function ApplicationDetailDialog({ open, onClose, applicationId, onReviewComplete }) {
  const [application, setApplication] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [reviewNotes, setReviewNotes] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [approvalResult, setApprovalResult] = React.useState(null);
  const [overrideOpen, setOverrideOpen] = React.useState(false);
  const [recomputing, setRecomputing] = React.useState(false);

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

  const handleRecompute = async () => {
    setRecomputing(true);
    try {
      await computeUnderwritingScore(applicationId);
      const updated = await getApplication(applicationId);
      setApplication(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setRecomputing(false);
    }
  };

  const handleOverrideComplete = async () => {
    const updated = await getApplication(applicationId);
    setApplication(updated);
    onReviewComplete();
  };

  const canReview = application && ['SUBMITTED', 'NEEDS_INFO'].includes(application.status);

  const fmtCents = (v) => v != null ? '$' + (v / 100).toLocaleString() : '\u2014';

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

            {application.underwriting_score != null && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Underwriting Score
                  </Typography>
                  <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>{application.underwriting_score}</Typography>
                    <Chip label={application.underwriting_grade} size="small" sx={{ bgcolor: gradeColors[application.underwriting_grade]?.bg, color: gradeColors[application.underwriting_grade]?.color, fontWeight: 600 }} />
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" variant="outlined" onClick={handleRecompute} disabled={recomputing}>{recomputing ? 'Computing...' : 'Recompute'}</Button>
                    <Button size="small" variant="outlined" color="warning" onClick={() => setOverrideOpen(true)}>Override</Button>
                  </Stack>
                </Box>
              </>
            )}
            {application.underwriting_score == null && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>Underwriting Score</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>No score computed yet.</Typography>
                  <Button size="small" variant="outlined" onClick={handleRecompute} disabled={recomputing}>{recomputing ? 'Computing...' : 'Compute Score'}</Button>
                </Box>
              </>
            )}

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Practice Identity
              </Typography>
              <Typography variant="h6">{application.legal_name}</Typography>
              {application.dba && <Typography variant="body2">DBA: {application.dba}</Typography>}
              {application.ein && <Typography variant="body2">EIN: {application.ein}</Typography>}
              <Typography variant="body2">Years in Operation: {application.years_in_operation}</Typography>
              {application.ownership_structure && <Typography variant="body2">Ownership: {application.ownership_structure.replace(/_/g, ' ')}</Typography>}
              {application.prior_bankruptcy && <Typography variant="body2" color="error">Prior Bankruptcy: Yes</Typography>}
              {application.pending_litigation && <Typography variant="body2" color="error">Pending Litigation: Yes</Typography>}
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Revenue & Production</Typography>
              <Typography variant="body2">Gross Production: {fmtCents(application.gross_production_cents)}</Typography>
              <Typography variant="body2">Net Collections: {fmtCents(application.net_collections_cents)}</Typography>
              {application.insurance_collections_cents != null && <Typography variant="body2">Insurance Collections: {fmtCents(application.insurance_collections_cents)}</Typography>}
              {application.patient_collections_cents != null && <Typography variant="body2">Patient Collections: {fmtCents(application.patient_collections_cents)}</Typography>}
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Payer & Claims</Typography>
              {application.pct_ppo != null && <Typography variant="body2">PPO: {application.pct_ppo}%</Typography>}
              {application.pct_medicaid != null && <Typography variant="body2">Medicaid: {application.pct_medicaid}%</Typography>}
              {application.avg_claim_size_cents != null && <Typography variant="body2">Avg Claim Size: {fmtCents(application.avg_claim_size_cents)}</Typography>}
              {application.avg_days_to_reimbursement != null && <Typography variant="body2">Days to Reimbursement: {application.avg_days_to_reimbursement}</Typography>}
              {application.estimated_denial_rate != null && <Typography variant="body2">Denial Rate: {application.estimated_denial_rate}%</Typography>}
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>Billing Operations</Typography>
              <Typography variant="body2">Billing Model: {application.billing_model}</Typography>
              {application.practice_management_software && <Typography variant="body2">PMS: {application.practice_management_software}</Typography>}
              {application.billing_staff_count != null && <Typography variant="body2">Billing Staff: {application.billing_staff_count}</Typography>}
              <Typography variant="body2">RCM Manager: {application.dedicated_rcm_manager ? 'Yes' : 'No'}</Typography>
              <Typography variant="body2">Written SOP: {application.written_billing_sop ? 'Yes' : 'No'}</Typography>
              {application.avg_ar_days != null && <Typography variant="body2">Avg AR Days: {application.avg_ar_days}</Typography>}
              {application.outstanding_ar_balance_cents != null && <Typography variant="body2">Outstanding AR: {fmtCents(application.outstanding_ar_balance_cents)}</Typography>}
            </Box>

            {application.why_spoonbill && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>Why Spoonbill</Typography>
                  <Typography variant="body2">{application.why_spoonbill}</Typography>
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
      {application && (
        <ScoreOverrideDialog
          open={overrideOpen}
          onClose={() => setOverrideOpen(false)}
          applicationId={applicationId}
          currentScore={application.underwriting_score}
          currentGrade={application.underwriting_grade}
          onOverrideComplete={handleOverrideComplete}
        />
      )}
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
                <TableCell>Contact</TableCell>
                <TableCell>Score</TableCell>
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
                  <TableCell>
                    <Typography variant="body2">{app.contact_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {app.contact_email}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {app.underwriting_score != null ? (
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{app.underwriting_score}</Typography>
                        <Chip label={app.underwriting_grade} size="small" sx={{ bgcolor: gradeColors[app.underwriting_grade]?.bg, color: gradeColors[app.underwriting_grade]?.color, fontWeight: 600, fontSize: '0.7rem' }} />
                      </Stack>
                    ) : (
                      <Typography variant="caption" color="text.secondary">—</Typography>
                    )}
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
