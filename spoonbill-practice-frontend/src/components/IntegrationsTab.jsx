import { useState, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import SyncIcon from '@mui/icons-material/Sync';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { getIntegrationStatus, uploadIntegrationCSV, runIntegrationSync } from '../api';

const statusColors = {
  ACTIVE: '#059669',
  INACTIVE: '#6b7280',
  ERROR: '#dc2626',
};

const runStatusColors = {
  SUCCEEDED: '#059669',
  FAILED: '#dc2626',
  RUNNING: '#2563eb',
};

function IntegrationsTab() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getIntegrationStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch integration status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleCSVUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      let claimsFile = null;
      let linesFile = null;

      for (const file of files) {
        const name = file.name.toLowerCase();
        if (name.includes('line')) {
          linesFile = file;
        } else {
          claimsFile = file;
        }
      }

      if (!claimsFile) {
        claimsFile = files[0];
      }

      const result = await uploadIntegrationCSV(claimsFile, linesFile);
      const s = result.summary;
      setSuccess(
        `Upload complete: ${s.created} created, ${s.updated} updated, ${s.skipped} unchanged` +
        (s.errors.length > 0 ? `, ${s.errors.length} errors` : '')
      );
      fetchStatus();
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await runIntegrationSync();
      const s = result.summary;
      setSuccess(
        `Sync complete: ${s.created} created, ${s.updated} updated, ${s.skipped} unchanged`
      );
      fetchStatus();
    } catch (err) {
      setError(err.message || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  const isConnected = status?.connected;
  const connectionStatus = status?.status || 'INACTIVE';

  return (
    <Box>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
        Integrations
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Paper elevation={0} sx={{ p: 3, border: '1px solid #e5e7eb', mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Open Dental Cloud
            </Typography>
            <Chip
              label={connectionStatus}
              size="small"
              icon={isConnected ? <CheckCircleIcon /> : <ErrorIcon />}
              sx={{
                bgcolor: (statusColors[connectionStatus] || '#6b7280') + '20',
                color: statusColors[connectionStatus] || '#6b7280',
                fontWeight: 600,
              }}
            />
          </Box>
        </Box>

        {status?.last_synced_at && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Last synced: {new Date(status.last_synced_at).toLocaleString()}
          </Typography>
        )}

        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={syncing ? <CircularProgress size={16} /> : <SyncIcon />}
            onClick={handleSync}
            disabled={syncing || uploading}
          >
            {syncing ? 'Syncing...' : 'Run Sync'}
          </Button>

          <Button
            variant="contained"
            component="label"
            startIcon={uploading ? <CircularProgress size={16} color="inherit" /> : <CloudUploadIcon />}
            disabled={uploading || syncing}
          >
            {uploading ? 'Uploading...' : 'Upload CSV Export'}
            <input
              type="file"
              hidden
              accept=".csv"
              multiple
              onChange={handleCSVUpload}
            />
          </Button>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Upload claims.csv (required) and optionally claim_lines.csv. File with &quot;line&quot; in the name is treated as lines.
        </Typography>
      </Paper>

      {status?.recent_runs && status.recent_runs.length > 0 && (
        <Paper elevation={0} sx={{ p: 3, border: '1px solid #e5e7eb' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
            Recent Sync Runs
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Pulled</TableCell>
                  <TableCell align="right">Upserted</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {status.recent_runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      {new Date(run.started_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={run.sync_type}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={run.status}
                        size="small"
                        sx={{
                          bgcolor: (runStatusColors[run.status] || '#6b7280') + '20',
                          color: runStatusColors[run.status] || '#6b7280',
                          fontWeight: 600,
                        }}
                      />
                    </TableCell>
                    <TableCell align="right">{run.pulled_count}</TableCell>
                    <TableCell align="right">{run.upserted_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}
    </Box>
  );
}

export default IntegrationsTab;
