import { useState, useEffect } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import { getOntologyContext, generateOntologyBrief, adjustPracticeLimit } from '../api';

const fmt = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A';

function SnapshotCards({ totals, funding }) {
  const cards = [
    { label: 'Total Claims', value: totals?.total_claims ?? 0 },
    { label: 'Total Billed', value: fmt(totals?.total_billed_cents ?? 0) },
    { label: 'Total Funded', value: fmt(funding?.total_funded_cents ?? 0) },
    { label: 'Confirmed', value: fmt(funding?.total_confirmed_cents ?? 0) },
    { label: 'Utilization', value: pct(funding?.utilization) },
  ];

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 1.5, mb: 3 }}>
      {cards.map((c) => (
        <Paper key={c.label} elevation={0} sx={{ p: 2, textAlign: 'center', border: '1px solid #e5e7eb' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{c.value}</Typography>
          <Typography variant="caption" color="text.secondary">{c.label}</Typography>
        </Paper>
      ))}
    </Box>
  );
}

function PayerMixTable({ payerMix }) {
  if (!payerMix || payerMix.length === 0) return null;
  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Payer Mix (Top 5)</Typography>
      <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse' }}>
        <Box component="thead">
          <Box component="tr" sx={{ borderBottom: '1px solid #e5e7eb' }}>
            <Box component="th" sx={{ textAlign: 'left', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>Payer</Box>
            <Box component="th" sx={{ textAlign: 'right', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>Billed</Box>
            <Box component="th" sx={{ textAlign: 'right', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>Share</Box>
          </Box>
        </Box>
        <Box component="tbody">
          {payerMix.map((p) => (
            <Box component="tr" key={p.payer} sx={{ borderBottom: '1px solid #f3f4f6' }}>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem' }}>{p.payer}</Box>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem', textAlign: 'right' }}>{fmt(p.billed_cents)}</Box>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem', textAlign: 'right' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1 }}>
                  <Box sx={{ width: 60, height: 6, bgcolor: '#f3f4f6', borderRadius: 3, overflow: 'hidden' }}>
                    <Box sx={{ width: `${p.share * 100}%`, height: '100%', bgcolor: '#2563eb', borderRadius: 3 }} />
                  </Box>
                  {pct(p.share)}
                </Box>
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Paper>
  );
}

function ProcedureMixTable({ procedureMix }) {
  if (!procedureMix || procedureMix.length === 0) return null;
  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Procedure Mix (Top 5 CDT Codes)</Typography>
      <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse' }}>
        <Box component="thead">
          <Box component="tr" sx={{ borderBottom: '1px solid #e5e7eb' }}>
            <Box component="th" sx={{ textAlign: 'left', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>CDT Code</Box>
            <Box component="th" sx={{ textAlign: 'right', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>Count</Box>
            <Box component="th" sx={{ textAlign: 'right', py: 0.5, fontSize: '0.75rem', color: '#6b7280' }}>Share</Box>
          </Box>
        </Box>
        <Box component="tbody">
          {procedureMix.map((p) => (
            <Box component="tr" key={p.cdt_code} sx={{ borderBottom: '1px solid #f3f4f6' }}>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem', fontFamily: 'monospace' }}>{p.cdt_code}</Box>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem', textAlign: 'right' }}>{p.count}</Box>
              <Box component="td" sx={{ py: 0.75, fontSize: '0.875rem', textAlign: 'right' }}>{pct(p.share)}</Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Paper>
  );
}

function CohortMetrics({ cohorts }) {
  if (!cohorts) return null;
  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Reimbursement Lag</Typography>
      {cohorts.sample_size === 0 ? (
        <Typography variant="body2" color="text.secondary">No confirmed payments yet</Typography>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{cohorts.avg_lag_days ?? 'N/A'}</Typography>
            <Typography variant="caption" color="text.secondary">Avg (days)</Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{cohorts.p50_lag_days ?? 'N/A'}</Typography>
            <Typography variant="caption" color="text.secondary">P50 (days)</Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>{cohorts.p90_lag_days ?? 'N/A'}</Typography>
            <Typography variant="caption" color="text.secondary">P90 (days)</Typography>
          </Box>
        </Box>
      )}
    </Paper>
  );
}

function DenialMetrics({ denials }) {
  if (!denials) return null;
  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Denials & Exceptions</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
        <Box>
          <Typography variant="body2" color="text.secondary">Denial Rate</Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: denials.denial_rate > 0.1 ? '#dc2626' : '#059669' }}>
            {pct(denials.denial_rate)}
          </Typography>
          <Typography variant="caption" color="text.secondary">{denials.declined_count} declined</Typography>
        </Box>
        <Box>
          <Typography variant="body2" color="text.secondary">Exception Rate</Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: denials.exception_rate > 0.05 ? '#d97706' : '#059669' }}>
            {pct(denials.exception_rate)}
          </Typography>
          <Typography variant="caption" color="text.secondary">{denials.exception_count} exceptions</Typography>
        </Box>
      </Box>
    </Paper>
  );
}

function RiskFlags({ riskFlags }) {
  if (!riskFlags || riskFlags.length === 0) {
    return (
      <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Risk Flags</Typography>
        <Typography variant="body2" color="text.secondary">No active risk flags</Typography>
      </Paper>
    );
  }

  const flagColors = {
    PAYER_CONCENTRATION: '#d97706',
    HIGH_DENIAL_RATE: '#dc2626',
    HIGH_UTILIZATION: '#7c3aed',
    HIGH_EXCEPTION_RATE: '#dc2626',
  };

  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #fbbf24', bgcolor: '#fffbeb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, color: '#92400e' }}>
        Risk Flags ({riskFlags.length})
      </Typography>
      {riskFlags.map((flag, i) => (
        <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
          <Chip
            label={flag.flag}
            size="small"
            sx={{ bgcolor: (flagColors[flag.flag] || '#6b7280') + '20', color: flagColors[flag.flag] || '#6b7280', fontWeight: 600, fontSize: '0.7rem' }}
          />
          <Typography variant="body2">{flag.detail}</Typography>
        </Box>
      ))}
    </Paper>
  );
}

function MissingData({ missingData }) {
  if (!missingData || missingData.length === 0) return null;
  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>Missing Data</Typography>
      {missingData.map((item, i) => (
        <Typography key={i} variant="body2" color="text.secondary" sx={{ py: 0.25 }}>
          {item}
        </Typography>
      ))}
    </Paper>
  );
}

function BriefPanel({ practiceId, brief, onBriefGenerated, onLimitAdjusted }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [adjusting, setAdjusting] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await generateOntologyBrief(practiceId);
      onBriefGenerated(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAdjustLimit = async (action) => {
    setAdjusting(true);
    try {
      await adjustPracticeLimit(practiceId, action.params.new_limit, action.reason);
      onLimitAdjusted();
    } catch (err) {
      setError(err.message);
    } finally {
      setAdjusting(false);
    }
  };

  return (
    <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>Ontology Brief</Typography>
        <Button
          variant="outlined"
          size="small"
          onClick={handleGenerate}
          disabled={loading}
          sx={{ textTransform: 'none' }}
        >
          {loading ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
          {brief ? 'Regenerate Brief' : 'Generate Brief'}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {brief && (
        <Box>
          <Typography variant="body2" sx={{ mb: 1.5 }}>{brief.summary}</Typography>

          {brief.key_drivers && brief.key_drivers.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>KEY DRIVERS</Typography>
              {brief.key_drivers.map((d, i) => (
                <Typography key={i} variant="body2" sx={{ pl: 1 }}>{d}</Typography>
              ))}
            </Box>
          )}

          {brief.risks && brief.risks.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#dc2626' }}>RISKS</Typography>
              {brief.risks.map((r, i) => (
                <Box key={i} sx={{ pl: 1, py: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.risk}</Typography>
                  <Typography variant="caption" color="text.secondary">{r.why} ({r.metric}: {r.value})</Typography>
                </Box>
              ))}
            </Box>
          )}

          {brief.recommended_actions && brief.recommended_actions.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#059669' }}>RECOMMENDED ACTIONS</Typography>
              {brief.recommended_actions.map((a, i) => (
                <Box key={i} sx={{ pl: 1, py: 0.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ flex: 1 }}>
                    <Chip label={a.action} size="small" sx={{ fontWeight: 600, fontSize: '0.7rem' }} />
                    <Typography variant="body2" sx={{ mt: 0.5 }}>{a.reason}</Typography>
                  </Box>
                  {a.action === 'ADJUST_LIMIT' && a.params?.new_limit && (
                    <Button
                      variant="contained"
                      size="small"
                      onClick={() => handleAdjustLimit(a)}
                      disabled={adjusting}
                      sx={{ textTransform: 'none', bgcolor: '#111', '&:hover': { bgcolor: '#333' } }}
                    >
                      {adjusting ? 'Applying...' : `Apply (${fmt(a.params.new_limit)})`}
                    </Button>
                  )}
                </Box>
              ))}
            </Box>
          )}

          {brief.missing_data && brief.missing_data.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>MISSING DATA</Typography>
              {brief.missing_data.map((m, i) => (
                <Typography key={i} variant="body2" color="text.secondary" sx={{ pl: 1 }}>{m}</Typography>
              ))}
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
}

export default function OntologyTab({ practiceId }) {
  const [context, setContext] = useState(null);
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchContext = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOntologyContext(practiceId);
      setContext(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (practiceId) {
      fetchContext();
    }
  }, [practiceId]);

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CircularProgress size={32} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Loading ontology data...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
        <Button size="small" onClick={fetchContext} sx={{ ml: 2 }}>Retry</Button>
      </Alert>
    );
  }

  if (!context) return null;

  const { snapshot } = context;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Financial Ontology
          <Chip label={context.version} size="small" sx={{ ml: 1, fontSize: '0.7rem' }} />
        </Typography>
        <Button variant="text" size="small" onClick={fetchContext} sx={{ textTransform: 'none' }}>
          Refresh
        </Button>
      </Box>

      <SnapshotCards totals={snapshot.totals} funding={snapshot.funding} />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <PayerMixTable payerMix={snapshot.payer_mix} />
        <ProcedureMixTable procedureMix={snapshot.procedure_mix} />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <CohortMetrics cohorts={snapshot.cohorts} />
        <DenialMetrics denials={snapshot.denials} />
      </Box>

      <RiskFlags riskFlags={snapshot.risk_flags} />
      <MissingData missingData={snapshot.missing_data} />

      <Divider sx={{ my: 2 }} />

      <BriefPanel
        practiceId={practiceId}
        brief={brief}
        onBriefGenerated={(b) => setBrief(b)}
        onLimitAdjusted={() => fetchContext()}
      />
    </Box>
  );
}
