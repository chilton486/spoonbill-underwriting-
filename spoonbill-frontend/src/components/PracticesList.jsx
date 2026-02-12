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
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import InputAdornment from '@mui/material/InputAdornment';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';

import { getPractices, getPractice, reissueInvite } from '../api.js';

const statusColors = {
  ACTIVE: { bg: '#d1fae5', color: '#065f46' },
  INACTIVE: { bg: '#fee2e2', color: '#991b1b' },
  SUSPENDED: { bg: '#fef3c7', color: '#92400e' },
};

const inviteStatusColors = {
  ACTIVE: { bg: '#d1fae5', color: '#065f46' },
  USED: { bg: '#dbeafe', color: '#1e40af' },
  EXPIRED: { bg: '#f3f4f6', color: '#6b7280' },
};

function formatDate(dateString) {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatDateTime(dateString) {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}


function PracticeDetailDialog({ open, onClose, practiceId, onInviteReissued }) {
  const [practice, setPractice] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [reissuing, setReissuing] = React.useState(false);
  const [reissueResult, setReissueResult] = React.useState(null);
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    if (open && practiceId) {
      setLoading(true);
      setError(null);
      setReissueResult(null);
      getPractice(practiceId)
        .then(setPractice)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, [open, practiceId]);

  const handleReissue = async (userId = null) => {
    setReissuing(true);
    setError(null);
    try {
      const result = await reissueInvite(practiceId, userId);
      setReissueResult(result);
      // Refresh practice data to show new invite
      const updated = await getPractice(practiceId);
      setPractice(updated);
      if (onInviteReissued) onInviteReissued();
    } catch (e) {
      setError(e.message);
    } finally {
      setReissuing(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeInvite = practice?.invites?.find(i => i.status === 'ACTIVE');

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Practice Details
      </DialogTitle>
      <DialogContent dividers>
        {loading && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}
        
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        
        {reissueResult && (
          <Alert severity="success" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>New Invite Created</Typography>
            <Typography variant="body2">{reissueResult.message}</Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: '#f0fdf4', borderRadius: 1, border: '1px solid #86efac' }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Invite Link (expires {formatDateTime(reissueResult.expires_at)}):
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
                {reissueResult.invite_url}
              </Typography>
              <Button
                size="small"
                variant="outlined"
                sx={{ mt: 1 }}
                onClick={() => copyToClipboard(reissueResult.invite_url)}
                startIcon={<ContentCopyIcon />}
              >
                {copied ? 'Copied!' : 'Copy Invite Link'}
              </Button>
            </Box>
          </Alert>
        )}
        
        {practice && !loading && (
          <Stack spacing={3}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6">{practice.name}</Typography>
                <Chip
                  label={practice.status}
                  size="small"
                  sx={{
                    bgcolor: statusColors[practice.status]?.bg || '#f3f4f6',
                    color: statusColors[practice.status]?.color || '#374151',
                    fontWeight: 600,
                  }}
                />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Practice ID: {practice.id}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Created: {formatDateTime(practice.created_at)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Claims: {practice.claim_count}
              </Typography>
            </Box>

            <Divider />

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Practice Managers
              </Typography>
              {practice.managers?.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No managers</Typography>
              ) : (
                <Stack spacing={1}>
                  {practice.managers?.map((manager) => (
                    <Box key={manager.id} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2">{manager.email}</Typography>
                      <Chip
                        label={manager.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        sx={{
                          bgcolor: manager.is_active ? '#d1fae5' : '#fee2e2',
                          color: manager.is_active ? '#065f46' : '#991b1b',
                          fontSize: '0.7rem',
                        }}
                      />
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>

            <Divider />

            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary">
                  Invite History
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleReissue()}
                  disabled={reissuing}
                  startIcon={<RefreshIcon />}
                >
                  {reissuing ? 'Reissuing...' : 'Reissue Invite'}
                </Button>
              </Stack>
              
              {activeInvite && !reissueResult && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    Active Invite Link:
                  </Typography>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontFamily: 'monospace', 
                      wordBreak: 'break-all',
                      bgcolor: '#fff',
                      p: 1,
                      borderRadius: 0.5,
                      border: '1px solid #e5e7eb',
                      mb: 1
                    }}
                  >
                    {activeInvite.invite_url}
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => copyToClipboard(activeInvite.invite_url)}
                      startIcon={<ContentCopyIcon />}
                    >
                      {copied ? 'Copied!' : 'Copy'}
                    </Button>
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                    Expires: {formatDateTime(activeInvite.expires_at)}
                  </Typography>
                </Alert>
              )}

              {practice.invites?.length === 0 ? (
                <Typography variant="body2" color="text.secondary">No invites</Typography>
              ) : (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Email</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Expires</TableCell>
                        <TableCell>Used</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {practice.invites?.map((invite) => (
                        <TableRow key={invite.id}>
                          <TableCell>{invite.user_email}</TableCell>
                          <TableCell>
                            <Chip
                              label={invite.status}
                              size="small"
                              sx={{
                                bgcolor: inviteStatusColors[invite.status]?.bg || '#f3f4f6',
                                color: inviteStatusColors[invite.status]?.color || '#374151',
                                fontSize: '0.7rem',
                              }}
                            />
                          </TableCell>
                          <TableCell>{formatDate(invite.created_at)}</TableCell>
                          <TableCell>{formatDate(invite.expires_at)}</TableCell>
                          <TableCell>{invite.used_at ? formatDate(invite.used_at) : '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function PracticesList() {
  const [practices, setPractices] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [selectedId, setSelectedId] = React.useState(null);
  const [detailOpen, setDetailOpen] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [searchInput, setSearchInput] = React.useState('');
  const [copied, setCopied] = React.useState(null);

  const fetchPractices = React.useCallback(async (query = null) => {
    try {
      setLoading(true);
      const data = await getPractices(query);
      setPractices(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchPractices(searchQuery || null);
  }, [fetchPractices, searchQuery]);

  // Debounced search
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const openDetail = (id) => {
    setSelectedId(id);
    setDetailOpen(true);
  };

  const copyInviteLink = async (practice) => {
    try {
      // Fetch practice details to get the active invite token
      const details = await getPractice(practice.id);
      const activeInvite = details.invites?.find(i => i.status === 'ACTIVE');
      if (activeInvite) {
        navigator.clipboard.writeText(activeInvite.invite_url);
        setCopied(practice.id);
        setTimeout(() => setCopied(null), 2000);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h6">
          Approved Practices
          <Chip
            label={practices.length}
            size="small"
            sx={{ ml: 1, bgcolor: '#e5e7eb', color: '#374151' }}
          />
        </Typography>
        <TextField
          size="small"
          placeholder="Search by name, ID, or email..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          sx={{ width: 300 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
        />
      </Stack>

      {loading ? (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : practices.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {searchQuery ? 'No practices match your search' : 'No practices yet'}
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Practice Name</TableCell>
                <TableCell>Primary Manager</TableCell>
                <TableCell>Claims</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Invite</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {practices.map((practice) => (
                <TableRow key={practice.id} hover>
                  <TableCell>#{practice.id}</TableCell>
                  <TableCell>{practice.name}</TableCell>
                  <TableCell>
                    {practice.primary_manager_email || (
                      <Typography variant="body2" color="text.secondary">-</Typography>
                    )}
                  </TableCell>
                  <TableCell>{practice.claim_count}</TableCell>
                  <TableCell>
                    <Chip
                      label={practice.status}
                      size="small"
                      sx={{
                        bgcolor: statusColors[practice.status]?.bg || '#f3f4f6',
                        color: statusColors[practice.status]?.color || '#374151',
                        fontWeight: 600,
                      }}
                    />
                  </TableCell>
                  <TableCell>{formatDate(practice.created_at)}</TableCell>
                  <TableCell>
                    {practice.has_active_invite ? (
                      <Tooltip title={copied === practice.id ? 'Copied!' : 'Copy invite link'}>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyInviteLink(practice);
                          }}
                          sx={{ color: '#065f46' }}
                        >
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <Chip
                        label="No active invite"
                        size="small"
                        sx={{ bgcolor: '#f3f4f6', color: '#6b7280', fontSize: '0.7rem' }}
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => openDetail(practice.id)}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <PracticeDetailDialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        practiceId={selectedId}
        onInviteReissued={() => fetchPractices(searchQuery || null)}
      />
    </Box>
  );
}
