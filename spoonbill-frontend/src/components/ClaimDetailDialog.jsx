import * as React from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'

import Box from '@mui/material/Box'
import LinearProgress from '@mui/material/LinearProgress'
import Tooltip from '@mui/material/Tooltip'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import PsychologyIcon from '@mui/icons-material/Psychology'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'

import { getClaim, getValidTransitions, transitionClaim, getPaymentForClaim, processPayment, retryPayment, getClaimCognitiveSummary } from '../api.js'

function formatCurrency(cents) {
  if (cents === null || cents === undefined) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(cents / 100)
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
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

export default function ClaimDetailDialog({ open, onClose, claim: initialClaim, onRefresh }) {
  const [claim, setClaim] = React.useState(null)
  const [validTransitions, setValidTransitions] = React.useState([])
  const [selectedTransition, setSelectedTransition] = React.useState('')
  const [reason, setReason] = React.useState('')
  const [loading, setLoading] = React.useState(false)
  const [transitioning, setTransitioning] = React.useState(false)
  const [error, setError] = React.useState(null)
  const [payment, setPayment] = React.useState(null)
  const [processingPayment, setProcessingPayment] = React.useState(false)
  const [cognitiveSummary, setCognitiveSummary] = React.useState(null)

  React.useEffect(() => {
    if (!open || !initialClaim) {
      setClaim(null)
      setValidTransitions([])
      setSelectedTransition('')
      setReason('')
      setError(null)
      setPayment(null)
      setCognitiveSummary(null)
      return
    }

    let mounted = true
    ;(async () => {
      setLoading(true)
      try {
        const [claimData, transitions, paymentData, cogData] = await Promise.all([
          getClaim(initialClaim.id),
          getValidTransitions(initialClaim.id),
          getPaymentForClaim(initialClaim.id).catch(() => null),
          getClaimCognitiveSummary(initialClaim.id).catch(() => null)
        ])
        if (mounted) {
          setClaim(claimData)
          setValidTransitions(transitions.valid_transitions || [])
          setPayment(paymentData)
          setCognitiveSummary(cogData)
        }
      } catch (e) {
        if (mounted) setError(e.message)
      } finally {
        if (mounted) setLoading(false)
      }
    })()

    return () => { mounted = false }
  }, [open, initialClaim])

  const handleTransition = async () => {
    if (!selectedTransition) return
    setTransitioning(true)
    setError(null)
    try {
      await transitionClaim(claim.id, selectedTransition, reason || null)
      const [claimData, transitions] = await Promise.all([
        getClaim(claim.id),
        getValidTransitions(claim.id)
      ])
      setClaim(claimData)
      setValidTransitions(transitions.valid_transitions || [])
      setSelectedTransition('')
      setReason('')
      if (onRefresh) onRefresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setTransitioning(false)
    }
  }

  const handleProcessPayment = async () => {
    setProcessingPayment(true)
    setError(null)
    try {
      const result = await processPayment(claim.id)
      setPayment(result.payment_intent)
      const [claimData, transitions] = await Promise.all([
        getClaim(claim.id),
        getValidTransitions(claim.id)
      ])
      setClaim(claimData)
      setValidTransitions(transitions.valid_transitions || [])
      if (onRefresh) onRefresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setProcessingPayment(false)
    }
  }

  const handleRetryPayment = async () => {
    if (!payment) return
    setProcessingPayment(true)
    setError(null)
    try {
      const result = await retryPayment(payment.id)
      setPayment(result.payment_intent)
      const [claimData, transitions] = await Promise.all([
        getClaim(claim.id),
        getValidTransitions(claim.id)
      ])
      setClaim(claimData)
      setValidTransitions(transitions.valid_transitions || [])
      if (onRefresh) onRefresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setProcessingPayment(false)
    }
  }

  if (!open) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        Claim Details {claim ? `#${claim.id}` : ''}
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Stack sx={{ py: 4, alignItems: 'center' }}>
            <CircularProgress />
          </Stack>
        ) : claim ? (
          <Stack spacing={3}>
            {error && <Alert severity="error">{error}</Alert>}

            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="h6">Status:</Typography>
              <Chip 
                label={claim.status.replace('_', ' ')} 
                color={STATUS_COLORS[claim.status] || 'default'}
              />
            </Stack>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Claim Information</Typography>
              <Stack spacing={1}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Claim Token:</Typography>
                  <Typography sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{claim.claim_token}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Payer:</Typography>
                  <Typography>{claim.payer}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Patient Name:</Typography>
                  <Typography>{claim.patient_name || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Amount:</Typography>
                  <Typography>{formatCurrency(claim.amount_cents)}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Procedure Date:</Typography>
                  <Typography>{claim.procedure_date || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Practice ID:</Typography>
                  <Typography>{claim.practice_id || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Procedure Codes:</Typography>
                  <Typography>{claim.procedure_codes || '-'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Created:</Typography>
                  <Typography>{formatDateTime(claim.created_at)}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Updated:</Typography>
                  <Typography>{formatDateTime(claim.updated_at)}</Typography>
                </Stack>
              </Stack>
            </Paper>

            {/* Cognitive Underwriting Intelligence Panel */}
            {cognitiveSummary && cognitiveSummary.has_cognitive_data && (
              <Paper variant="outlined" sx={{ p: 2, border: '1px solid', borderColor: 'primary.main', bgcolor: 'primary.50' }}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                  <PsychologyIcon color="primary" />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Cognitive Underwriting Intelligence</Typography>
                  <Chip label={cognitiveSummary.model_name || 'Anthropic'} size="small" variant="outlined" />
                  {cognitiveSummary.latency_ms && (
                    <Typography variant="caption" color="text.secondary">{cognitiveSummary.latency_ms}ms</Typography>
                  )}
                </Stack>

                {/* Recommendation + Merge Info */}
                <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
                  <Tooltip title="Model recommendation">
                    <Chip
                      icon={cognitiveSummary.recommendation === 'APPROVE' ? <CheckCircleOutlineIcon /> :
                            cognitiveSummary.recommendation === 'DECLINE' ? <ErrorOutlineIcon /> : <WarningAmberIcon />}
                      label={`Model: ${cognitiveSummary.recommendation}`}
                      color={cognitiveSummary.recommendation === 'APPROVE' ? 'success' :
                             cognitiveSummary.recommendation === 'DECLINE' ? 'error' : 'warning'}
                      size="small"
                    />
                  </Tooltip>
                  {cognitiveSummary.deterministic_recommendation && (
                    <Tooltip title="Deterministic rules recommendation">
                      <Chip
                        label={`Rules: ${cognitiveSummary.deterministic_recommendation}`}
                        size="small" variant="outlined"
                        color={cognitiveSummary.deterministic_recommendation === 'APPROVE' ? 'success' :
                               cognitiveSummary.deterministic_recommendation === 'DECLINE' ? 'error' : 'warning'}
                      />
                    </Tooltip>
                  )}
                  {cognitiveSummary.merged_recommendation && (
                    <Tooltip title="Final merged recommendation">
                      <Chip
                        label={`Final: ${cognitiveSummary.merged_recommendation}`}
                        size="small"
                        color={cognitiveSummary.merged_recommendation === 'APPROVE' ? 'success' :
                               cognitiveSummary.merged_recommendation === 'DECLINE' ? 'error' : 'warning'}
                        sx={{ fontWeight: 700 }}
                      />
                    </Tooltip>
                  )}
                </Stack>

                {/* Risk + Confidence Scores */}
                {(cognitiveSummary.risk_score !== null || cognitiveSummary.confidence_score !== null) && (
                  <Stack direction="row" spacing={4} sx={{ mb: 2 }}>
                    {cognitiveSummary.risk_score !== null && (
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="caption" color="text.secondary">Risk Score</Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <LinearProgress
                            variant="determinate"
                            value={cognitiveSummary.risk_score * 100}
                            color={cognitiveSummary.risk_score > 0.7 ? 'error' : cognitiveSummary.risk_score > 0.4 ? 'warning' : 'success'}
                            sx={{ flex: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 40 }}>
                            {(cognitiveSummary.risk_score * 100).toFixed(0)}%
                          </Typography>
                        </Stack>
                      </Box>
                    )}
                    {cognitiveSummary.confidence_score !== null && (
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="caption" color="text.secondary">Confidence</Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <LinearProgress
                            variant="determinate"
                            value={cognitiveSummary.confidence_score * 100}
                            color="info"
                            sx={{ flex: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 40 }}>
                            {(cognitiveSummary.confidence_score * 100).toFixed(0)}%
                          </Typography>
                        </Stack>
                      </Box>
                    )}
                  </Stack>
                )}

                {/* Rationale */}
                {cognitiveSummary.rationale_summary && (
                  <Alert severity="info" icon={<InfoOutlinedIcon />} sx={{ mb: 2 }}>
                    <Typography variant="body2"><strong>Summary:</strong> {cognitiveSummary.rationale_summary}</Typography>
                  </Alert>
                )}

                {/* Risk Factors */}
                {cognitiveSummary.key_risk_factors && cognitiveSummary.key_risk_factors.length > 0 && (
                  <Accordion defaultExpanded={false} variant="outlined" sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <WarningAmberIcon fontSize="small" color="warning" />
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          Key Risk Factors ({cognitiveSummary.key_risk_factors.length})
                        </Typography>
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={1}>
                        {cognitiveSummary.key_risk_factors.map((rf, idx) => (
                          <Stack key={idx} direction="row" spacing={1} alignItems="flex-start">
                            <Chip
                              label={rf.severity}
                              size="small"
                              color={rf.severity === 'HIGH' ? 'error' : rf.severity === 'MEDIUM' ? 'warning' : 'default'}
                              sx={{ minWidth: 70 }}
                            />
                            <Box>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{rf.factor}</Typography>
                              <Typography variant="caption" color="text.secondary">{rf.detail}</Typography>
                            </Box>
                          </Stack>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Required Documents */}
                {cognitiveSummary.required_documents && cognitiveSummary.required_documents.length > 0 && (
                  <Accordion defaultExpanded={false} variant="outlined" sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Required Documents ({cognitiveSummary.required_documents.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={0.5}>
                        {cognitiveSummary.required_documents.map((doc, idx) => (
                          <Typography key={idx} variant="body2">- {doc}</Typography>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Policy Flags */}
                {cognitiveSummary.policy_flags && cognitiveSummary.policy_flags.length > 0 && (
                  <Accordion defaultExpanded={false} variant="outlined" sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Policy Flags ({cognitiveSummary.policy_flags.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={0.5}>
                        {cognitiveSummary.policy_flags.map((pf, idx) => (
                          <Typography key={idx} variant="body2"><strong>{pf.flag}:</strong> {pf.detail}</Typography>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Ontology Observations */}
                {cognitiveSummary.ontology_observations && cognitiveSummary.ontology_observations.length > 0 && (
                  <Accordion defaultExpanded={false} variant="outlined" sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Ontology Observations ({cognitiveSummary.ontology_observations.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={0.5}>
                        {cognitiveSummary.ontology_observations.map((obs, idx) => (
                          <Stack key={idx} direction="row" spacing={1} alignItems="center">
                            <Chip label={obs.entity_type} size="small" variant="outlined" />
                            <Typography variant="body2">{obs.observation}</Typography>
                          </Stack>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Next Actions */}
                {cognitiveSummary.next_actions && cognitiveSummary.next_actions.length > 0 && (
                  <Accordion defaultExpanded={false} variant="outlined" sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Recommended Actions ({cognitiveSummary.next_actions.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={0.5}>
                        {cognitiveSummary.next_actions.map((na, idx) => (
                          <Stack key={idx} direction="row" spacing={1} alignItems="center">
                            {na.priority && (
                              <Chip
                                label={na.priority}
                                size="small"
                                color={na.priority === 'HIGH' ? 'error' : na.priority === 'MEDIUM' ? 'warning' : 'default'}
                              />
                            )}
                            <Typography variant="body2"><strong>{na.action}:</strong> {na.detail}</Typography>
                          </Stack>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Detailed Rationale */}
                {cognitiveSummary.rationale_detailed && (
                  <Accordion defaultExpanded={false} variant="outlined">
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>Detailed Rationale</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                        {cognitiveSummary.rationale_detailed}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Metadata footer */}
                <Stack direction="row" spacing={2} sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="caption" color="text.secondary">
                    Prompt: {cognitiveSummary.prompt_version}
                  </Typography>
                  {cognitiveSummary.created_at && (
                    <Typography variant="caption" color="text.secondary">
                      Run: {formatDateTime(cognitiveSummary.created_at)}
                    </Typography>
                  )}
                  {cognitiveSummary.fallback_used && (
                    <Chip label="Fallback Used" size="small" color="warning" variant="outlined" />
                  )}
                </Stack>
              </Paper>
            )}

            {/* Show message if cognitive is not enabled but available */}
            {cognitiveSummary && !cognitiveSummary.has_cognitive_data && cognitiveSummary.cognitive_enabled && (
              <Alert severity="info" icon={<PsychologyIcon />}>
                Cognitive underwriting is enabled but no data exists for this claim yet.
              </Alert>
            )}

            {claim.underwriting_decisions && claim.underwriting_decisions.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Underwriting Decisions</Typography>
                {claim.underwriting_decisions.map((decision, idx) => (
                  <Stack key={idx} spacing={1} sx={{ mb: idx < claim.underwriting_decisions.length - 1 ? 2 : 0 }}>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Chip 
                        label={decision.decision} 
                        size="small"
                        color={decision.decision === 'APPROVE' ? 'success' : decision.decision === 'DECLINE' ? 'error' : 'warning'}
                      />
                      <Typography variant="body2" color="text.secondary">
                        {formatDateTime(decision.decided_at)}
                      </Typography>
                    </Stack>
                    {decision.reasons && (
                      <Typography variant="body2" sx={{ pl: 1, fontStyle: 'italic' }}>
                        {decision.reasons}
                      </Typography>
                    )}
                  </Stack>
                ))}
              </Paper>
            )}

            {(claim.status === 'APPROVED' || payment) && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Payment Status</Typography>
                {payment ? (
                  <Stack spacing={1}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography color="text.secondary">Status:</Typography>
                      <Chip 
                        label={payment.status} 
                        size="small"
                        color={payment.status === 'CONFIRMED' ? 'success' : payment.status === 'FAILED' ? 'error' : 'warning'}
                      />
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography color="text.secondary">Amount:</Typography>
                      <Typography>{formatCurrency(payment.amount_cents)}</Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography color="text.secondary">Provider:</Typography>
                      <Typography>{payment.provider}</Typography>
                    </Stack>
                    {payment.provider_reference && (
                      <Stack direction="row" justifyContent="space-between">
                        <Typography color="text.secondary">Reference:</Typography>
                        <Typography sx={{ fontFamily: 'monospace' }}>{payment.provider_reference}</Typography>
                      </Stack>
                    )}
                    {payment.confirmed_at && (
                      <Stack direction="row" justifyContent="space-between">
                        <Typography color="text.secondary">Confirmed:</Typography>
                        <Typography>{formatDateTime(payment.confirmed_at)}</Typography>
                      </Stack>
                    )}
                    {payment.failure_code && (
                      <Alert severity="error" sx={{ mt: 1 }}>
                        {payment.failure_code}: {payment.failure_message}
                      </Alert>
                    )}
                    {payment.status === 'FAILED' && (
                      <Button
                        variant="outlined"
                        color="warning"
                        onClick={handleRetryPayment}
                        disabled={processingPayment}
                        startIcon={processingPayment ? <CircularProgress size={20} color="inherit" /> : null}
                        sx={{ mt: 1 }}
                      >
                        {processingPayment ? 'Retrying...' : 'Retry Payment'}
                      </Button>
                    )}
                  </Stack>
                ) : claim.status === 'APPROVED' ? (
                  <Stack spacing={2}>
                    <Typography color="text.secondary">
                      This claim is approved and ready for payment.
                    </Typography>
                    <Button
                      variant="contained"
                      onClick={handleProcessPayment}
                      disabled={processingPayment}
                      startIcon={processingPayment ? <CircularProgress size={20} color="inherit" /> : null}
                    >
                      {processingPayment ? 'Processing...' : 'Process Payment'}
                    </Button>
                  </Stack>
                ) : null}
              </Paper>
            )}

            {claim.payment_exception && (
              <Alert severity="warning">
                Payment Exception: {claim.exception_code || 'Unknown error'}
              </Alert>
            )}

            {claim.audit_events && claim.audit_events.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Audit Trail</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell>From</TableCell>
                      <TableCell>To</TableCell>
                      <TableCell>Actor</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {claim.audit_events.map((event, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{formatDateTime(event.created_at)}</TableCell>
                        <TableCell>{event.action}</TableCell>
                        <TableCell>{event.from_status || '-'}</TableCell>
                        <TableCell>{event.to_status || '-'}</TableCell>
                        <TableCell>{event.actor_email || 'system'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Paper>
            )}

            {validTransitions.length > 0 && (
              <>
                <Divider />
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>Transition Status</Typography>
                  <Stack spacing={2}>
                    <Select
                      value={selectedTransition}
                      onChange={(e) => setSelectedTransition(e.target.value)}
                      displayEmpty
                      fullWidth
                      size="small"
                    >
                      <MenuItem value="">Select new status...</MenuItem>
                      {validTransitions.map((status) => (
                        <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
                      ))}
                    </Select>
                    <TextField
                      label="Reason (optional)"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      fullWidth
                      size="small"
                      multiline
                      rows={2}
                    />
                    <Button
                      variant="contained"
                      onClick={handleTransition}
                      disabled={!selectedTransition || transitioning}
                      startIcon={transitioning ? <CircularProgress size={20} color="inherit" /> : null}
                    >
                      {transitioning ? 'Transitioning...' : 'Apply Transition'}
                    </Button>
                  </Stack>
                </Paper>
              </>
            )}
          </Stack>
        ) : (
          <Typography color="text.secondary">No claim selected</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
