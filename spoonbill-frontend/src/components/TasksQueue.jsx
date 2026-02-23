import * as React from 'react'
import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import Skeleton from '@mui/material/Skeleton'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import TextField from '@mui/material/TextField'
import RefreshIcon from '@mui/icons-material/Refresh'
import AssignmentIcon from '@mui/icons-material/Assignment'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import { tokens } from '../theme.js'
import {
  getOpsTasks,
  updateOpsTask,
  runPlaybook,
  getPlaybookTemplates,
} from '../api.js'

const PRIORITY_COLOR = { high: 'error', medium: 'warning', low: 'info' }
const STATUS_COLOR = { OPEN: 'warning', IN_PROGRESS: 'info', RESOLVED: 'success', CANCELLED: 'default' }

function formatSla(seconds) {
  if (seconds == null) return '—'
  if (seconds <= 0) return 'OVERDUE'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function TasksQueue() {
  const [tasks, setTasks] = React.useState(null)
  const [statusCounts, setStatusCounts] = React.useState({})
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [statusFilter, setStatusFilter] = React.useState('OPEN')
  const [templates, setTemplates] = React.useState([])
  const [playbookDialog, setPlaybookDialog] = React.useState(false)
  const [selectedPlaybook, setSelectedPlaybook] = React.useState('')
  const [playbookPracticeId, setPlaybookPracticeId] = React.useState('')
  const [playbookClaimId, setPlaybookClaimId] = React.useState('')
  const [running, setRunning] = React.useState(false)
  const [resolveDialog, setResolveDialog] = React.useState(null)
  const [resolveNote, setResolveNote] = React.useState('')

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [taskData, tmpl] = await Promise.all([
        getOpsTasks({ status: statusFilter === 'All' ? undefined : statusFilter }),
        getPlaybookTemplates(),
      ])
      setTasks(taskData.items || [])
      setStatusCounts(taskData.status_counts || {})
      setTemplates(tmpl.templates || [])
    } catch (e) {
      setError(e.message || 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  React.useEffect(() => { load() }, [load])

  const handleStatusChange = async (taskId, newStatus) => {
    try {
      await updateOpsTask(taskId, { status: newStatus })
      load()
    } catch (e) {
      setError(e.message || 'Failed to update task')
    }
  }

  const handleResolve = async () => {
    if (!resolveDialog) return
    try {
      await updateOpsTask(resolveDialog.id, { status: 'RESOLVED', resolution_note: resolveNote })
      setResolveDialog(null)
      setResolveNote('')
      load()
    } catch (e) {
      setError(e.message || 'Failed to resolve task')
    }
  }

  const handleRunPlaybook = async () => {
    if (!selectedPlaybook) return
    setRunning(true)
    try {
      await runPlaybook({
        playbook_type: selectedPlaybook,
        practice_id: playbookPracticeId ? parseInt(playbookPracticeId) : undefined,
        claim_id: playbookClaimId ? parseInt(playbookClaimId) : undefined,
      })
      setPlaybookDialog(false)
      setSelectedPlaybook('')
      setPlaybookPracticeId('')
      setPlaybookClaimId('')
      load()
    } catch (e) {
      setError(e.message || 'Failed to run playbook')
    } finally {
      setRunning(false)
    }
  }

  const totalOpen = (statusCounts.OPEN || 0) + (statusCounts.IN_PROGRESS || 0)

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={2} alignItems="center">
          <AssignmentIcon sx={{ fontSize: 28, color: tokens.colors.accent[600] }} />
          <Stack>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>Exception Queue</Typography>
            <Typography variant="body2" color="text.secondary">
              Tasks with playbooks and SLA tracking
            </Typography>
          </Stack>
          {totalOpen > 0 && (
            <Chip label={`${totalOpen} open`} color="warning" size="small" sx={{ height: 22 }} />
          )}
        </Stack>
        <Stack direction="row" spacing={1}>
          <Button size="small" variant="outlined" startIcon={<PlayArrowIcon />} onClick={() => setPlaybookDialog(true)}>
            Run Playbook
          </Button>
          <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
            Refresh
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Stack direction="row" spacing={1} alignItems="center">
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Status</InputLabel>
          <Select value={statusFilter} label="Status" onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="All">All</MenuItem>
            <MenuItem value="OPEN">Open</MenuItem>
            <MenuItem value="IN_PROGRESS">In Progress</MenuItem>
            <MenuItem value="RESOLVED">Resolved</MenuItem>
            <MenuItem value="CANCELLED">Cancelled</MenuItem>
          </Select>
        </FormControl>
        <Stack direction="row" spacing={1}>
          {Object.entries(statusCounts).map(([k, v]) => (
            <Chip
              key={k}
              label={`${k}: ${v}`}
              size="small"
              variant={statusFilter === k ? 'filled' : 'outlined'}
              color={STATUS_COLOR[k] || 'default'}
              onClick={() => setStatusFilter(statusFilter === k ? 'All' : k)}
              sx={{ cursor: 'pointer' }}
            />
          ))}
        </Stack>
      </Stack>

      {loading && !tasks ? (
        <Stack spacing={2}>
          {[1,2,3].map(i => (
            <Paper key={i} sx={{ p: 2.5 }}>
              <Skeleton variant="text" width="60%" />
              <Skeleton variant="text" width="40%" />
            </Paper>
          ))}
        </Stack>
      ) : !tasks || tasks.length === 0 ? (
        <Paper sx={{ p: 5, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">No tasks found for the selected filter</Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {tasks.map((task) => (
            <Paper
              key={task.id}
              sx={{
                p: 2.5,
                borderLeft: `4px solid ${
                  task.overdue ? tokens.colors.status.error
                  : task.priority === 'high' ? tokens.colors.status.warning
                  : tokens.colors.border.DEFAULT
                }`,
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Stack spacing={0.5} sx={{ flex: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="body1" sx={{ fontWeight: 600 }}>{task.title}</Typography>
                    <Chip label={task.status} size="small" color={STATUS_COLOR[task.status] || 'default'} />
                    <Chip label={task.priority} size="small" color={PRIORITY_COLOR[task.priority] || 'default'} variant="outlined" />
                    {task.playbook_type && (
                      <Chip label={task.playbook_type.replace(/_/g, ' ')} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                    )}
                  </Stack>
                  {task.description && (
                    <Typography variant="body2" color="text.secondary">{task.description}</Typography>
                  )}
                  <Stack direction="row" spacing={2}>
                    {task.practice_id && (
                      <Typography variant="caption" color="text.secondary">Practice #{task.practice_id}</Typography>
                    )}
                    {task.claim_id && (
                      <Typography variant="caption" color="text.secondary">Claim #{task.claim_id}</Typography>
                    )}
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <AccessTimeIcon sx={{ fontSize: 12, color: task.overdue ? tokens.colors.status.error : tokens.colors.text.muted }} />
                      <Typography variant="caption" sx={{ color: task.overdue ? tokens.colors.status.error : tokens.colors.text.muted, fontWeight: task.overdue ? 700 : 400 }}>
                        SLA: {formatSla(task.sla_remaining_seconds)}
                      </Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      Created {new Date(task.created_at).toLocaleDateString()}
                    </Typography>
                  </Stack>
                </Stack>
                <Stack direction="row" spacing={1}>
                  {task.status === 'OPEN' && (
                    <Button size="small" variant="outlined" onClick={() => handleStatusChange(task.id, 'IN_PROGRESS')}>
                      Start
                    </Button>
                  )}
                  {(task.status === 'OPEN' || task.status === 'IN_PROGRESS') && (
                    <Button size="small" variant="contained" onClick={() => { setResolveDialog(task); setResolveNote('') }}>
                      Resolve
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}

      <Dialog open={playbookDialog} onClose={() => setPlaybookDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Run Playbook</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Playbook</InputLabel>
              <Select value={selectedPlaybook} label="Playbook" onChange={(e) => setSelectedPlaybook(e.target.value)}>
                {templates.map(t => (
                  <MenuItem key={t.type} value={t.type}>
                    <Stack>
                      <Typography variant="body2">{t.type.replace(/_/g, ' ')}</Typography>
                      <Typography variant="caption" color="text.secondary">{t.description}</Typography>
                    </Stack>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              size="small"
              label="Practice ID (optional)"
              value={playbookPracticeId}
              onChange={(e) => setPlaybookPracticeId(e.target.value)}
              type="number"
            />
            <TextField
              size="small"
              label="Claim ID (optional)"
              value={playbookClaimId}
              onChange={(e) => setPlaybookClaimId(e.target.value)}
              type="number"
            />
            {selectedPlaybook && templates.find(t => t.type === selectedPlaybook) && (
              <Alert severity="info" sx={{ mt: 1 }}>
                SLA: {templates.find(t => t.type === selectedPlaybook).sla_hours}h |
                Priority: {templates.find(t => t.type === selectedPlaybook).priority}
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPlaybookDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleRunPlaybook} disabled={running || !selectedPlaybook}>
            {running ? 'Running...' : 'Run Playbook'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!resolveDialog} onClose={() => setResolveDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Resolve Task</DialogTitle>
        <DialogContent>
          {resolveDialog && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>{resolveDialog.title}</Typography>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Resolution Note"
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResolveDialog(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleResolve} disabled={!resolveNote.trim()}>
            Resolve
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
