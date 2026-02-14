import { useState, useEffect, useRef, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import {
  getOntologyContext, generateOntologyBrief, adjustPracticeLimit,
  getOntologyCohorts, getCfo360, getOntologyRisks, getOntologyGraph,
} from '../api';

const fmt = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A';

const SectionTitle = ({ children }) => (
  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', color: '#374151' }}>
    {children}
  </Typography>
);

const Card = ({ children, sx, ...props }) => (
  <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', ...sx }} {...props}>{children}</Paper>
);

function CfoSnapshot({ cfo }) {
  if (!cfo) return null;
  const { capital, revenue } = cfo;
  const cards = [
    { label: 'Total Funded', value: fmt(capital?.total_funded_cents ?? 0) },
    { label: 'Utilization', value: pct(capital?.utilization), color: capital?.utilization > 0.85 ? '#dc2626' : '#059669' },
    { label: 'Available Capacity', value: fmt(capital?.available_capacity_cents ?? 0) },
    { label: 'Billed MTD', value: fmt(revenue?.billed_mtd_cents ?? 0) },
    { label: 'Reimbursed MTD', value: fmt(revenue?.reimbursed_mtd_cents ?? 0) },
    { label: '90d Avg Monthly', value: fmt(revenue?.trailing_90d_avg_monthly_cents ?? 0) },
  ];

  return (
    <Box sx={{ mb: 3 }}>
      <SectionTitle>CFO 360 Snapshot</SectionTitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 1.5 }}>
        {cards.map((c) => (
          <Card key={c.label} sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: c.color || 'inherit' }}>{c.value}</Typography>
            <Typography variant="caption" color="text.secondary">{c.label}</Typography>
          </Card>
        ))}
      </Box>
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

function TimeSeriesPanel({ cohorts }) {
  if (!cohorts || !cohorts.timeseries) return null;
  const ts = cohorts.timeseries;
  const metrics = Object.keys(ts).filter(k => ['billed_30d', 'funded_30d', 'billed_cumulative', 'funded_cumulative'].includes(k));
  if (metrics.length === 0) return null;

  const labels = { billed_30d: 'Billed (30d Rolling)', funded_30d: 'Funded (30d Rolling)', billed_cumulative: 'Billed (Cumulative)', funded_cumulative: 'Funded (Cumulative)', confirmed_cumulative: 'Confirmed (Cumulative)' };
  const colors = { billed_30d: '#2563eb', funded_30d: '#059669', billed_cumulative: '#6366f1', funded_cumulative: '#10b981', confirmed_cumulative: '#8b5cf6' };

  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Time-Series Trends</SectionTitle>
      {metrics.map(metric => {
        const data = ts[metric] || [];
        if (data.length < 2) return null;
        const vals = data.map(d => d.value).filter(v => v != null);
        const maxVal = Math.max(...vals, 1);
        const minVal = Math.min(...vals, 0);
        const range = maxVal - minVal || 1;
        const height = 60;
        const width = 100;

        const points = data.map((d, i) => {
          const x = (i / Math.max(data.length - 1, 1)) * width;
          const y = height - ((d.value - minVal) / range) * height;
          return `${x},${y}`;
        }).join(' ');

        return (
          <Box key={metric} sx={{ mb: 1.5 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: colors[metric] || '#374151' }}>{labels[metric] || metric}</Typography>
              <Typography variant="caption" color="text.secondary">{data.length > 0 ? fmt(data[data.length - 1].value) : 'N/A'}</Typography>
            </Box>
            <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 48 }} preserveAspectRatio="none">
              <polyline points={points} fill="none" stroke={colors[metric] || '#6b7280'} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            </svg>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>{data[0]?.date}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>{data[data.length - 1]?.date}</Typography>
            </Box>
          </Box>
        );
      })}
    </Card>
  );
}

function CohortAgingPanel({ cohorts }) {
  if (!cohorts) return null;
  const { aging_buckets, lag_curve, submission_cohorts } = cohorts;

  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Cohort Analysis</SectionTitle>
      {aging_buckets && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>AGING BUCKETS (Open Claims)</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, mt: 0.5 }}>
            {[['0-30d', aging_buckets['0_30']], ['30-60d', aging_buckets['30_60']], ['60-90d', aging_buckets['60_90']], ['90+d', aging_buckets['90_plus']]].map(([label, val]) => (
              <Box key={label} sx={{ textAlign: 'center', p: 1, bgcolor: label === '90+d' && val > 0 ? '#fef2f2' : '#f9fafb', borderRadius: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 700, color: label === '90+d' && val > 0 ? '#dc2626' : 'inherit' }}>{val}</Typography>
                <Typography variant="caption" color="text.secondary">{label}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      )}
      {lag_curve && lag_curve.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>REIMBURSEMENT LAG CURVE</Typography>
          <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5, flexWrap: 'wrap' }}>
            {lag_curve.map(p => (
              <Box key={p.percentile} sx={{ textAlign: 'center' }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.days}d</Typography>
                <Typography variant="caption" color="text.secondary">P{p.percentile}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      )}
      {submission_cohorts && submission_cohorts.length > 0 && (
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>MONTHLY COHORTS</Typography>
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', mt: 0.5 }}>
            <Box component="thead">
              <Box component="tr" sx={{ borderBottom: '1px solid #e5e7eb' }}>
                {['Month', 'Claims', 'Billed', 'Funded', 'Reimb %'].map(h => (
                  <Box key={h} component="th" sx={{ textAlign: h === 'Month' ? 'left' : 'right', py: 0.5, fontSize: '0.7rem', color: '#6b7280' }}>{h}</Box>
                ))}
              </Box>
            </Box>
            <Box component="tbody">
              {submission_cohorts.slice(-6).map(c => (
                <Box component="tr" key={c.month} sx={{ borderBottom: '1px solid #f3f4f6' }}>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem' }}>{c.month}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right' }}>{c.claims}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right' }}>{fmt(c.billed_cents)}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right' }}>{fmt(c.funded_cents)}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right' }}>{pct(c.reimbursement_pct)}</Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      )}
    </Card>
  );
}

function PatientMixPanel({ patientDynamics, cfo }) {
  const pd = patientDynamics || cfo?.patient_dynamics;
  if (!pd) return null;

  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Patient Dynamics</SectionTitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5, mb: 2 }}>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{pd.total_patients}</Typography>
          <Typography variant="caption" color="text.secondary">Total Patients</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{fmt(pd.revenue_per_patient_cents || 0)}</Typography>
          <Typography variant="caption" color="text.secondary">Rev / Patient</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{pct(pd.repeat_visit_rate)}</Typography>
          <Typography variant="caption" color="text.secondary">Repeat Rate</Typography>
        </Box>
      </Box>
      {pd.age_mix && Object.keys(pd.age_mix).length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>AGE MIX</Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            {Object.entries(pd.age_mix).map(([bucket, count]) => (
              <Chip key={bucket} label={`${bucket}: ${count}`} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
            ))}
          </Box>
        </Box>
      )}
      {pd.insurance_mix && Object.keys(pd.insurance_mix).length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>INSURANCE MIX</Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            {Object.entries(pd.insurance_mix).map(([type, count]) => (
              <Chip key={type} label={`${type}: ${count}`} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
            ))}
          </Box>
        </Box>
      )}
      {cfo?.patient_dynamics && (
        <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">New (30d)</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{cfo.patient_dynamics.new_patients_30d}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Returning (30d)</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{cfo.patient_dynamics.returning_patients_30d}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">New:Returning</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{cfo.patient_dynamics.new_vs_returning_ratio}:1</Typography>
          </Box>
        </Box>
      )}
    </Card>
  );
}

function RiskIntelligencePanel({ risks }) {
  if (!risks || risks.length === 0) {
    return (
      <Card sx={{ mb: 2 }}>
        <SectionTitle>Risk Intelligence</SectionTitle>
        <Typography variant="body2" color="text.secondary">No active risk signals detected.</Typography>
      </Card>
    );
  }

  const severityColors = { high: '#dc2626', medium: '#d97706', low: '#059669' };
  const severityBg = { high: '#fef2f2', medium: '#fffbeb', low: '#f0fdf4' };

  return (
    <Card sx={{ mb: 2, border: risks.some(r => r.severity === 'high') ? '1px solid #fca5a5' : '1px solid #e5e7eb' }}>
      <SectionTitle>Risk Intelligence ({risks.length} signals)</SectionTitle>
      {risks.map((r, i) => (
        <Box key={i} sx={{ p: 1, mb: 0.5, bgcolor: severityBg[r.severity] || '#f9fafb', borderRadius: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
            <Chip
              label={r.severity?.toUpperCase()}
              size="small"
              sx={{ bgcolor: (severityColors[r.severity] || '#6b7280') + '20', color: severityColors[r.severity] || '#6b7280', fontWeight: 700, fontSize: '0.65rem', height: 20 }}
            />
            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{r.type}</Typography>
          </Box>
          <Typography variant="body2" sx={{ fontSize: '0.8rem', color: '#374151' }}>{r.explanation}</Typography>
          <Typography variant="caption" color="text.secondary">{r.metric}: {typeof r.value === 'number' ? (r.value < 1 ? pct(r.value) : r.value.toFixed(2)) : r.value}</Typography>
        </Box>
      ))}
    </Card>
  );
}

function GraphExplorer({ graph }) {
  const canvasRef = useRef(null);
  const [selectedNode, setSelectedNode] = useState(null);

  const nodeColors = {
    Practice: '#111827', Payer: '#2563eb', Patient: '#7c3aed',
    Procedure: '#059669', Claim: '#6b7280', PaymentIntent: '#d97706',
  };

  useEffect(() => {
    if (!graph || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    if (nodes.length === 0) return;

    const positions = {};
    const typeGroups = {};
    nodes.forEach(n => {
      if (!typeGroups[n.type]) typeGroups[n.type] = [];
      typeGroups[n.type].push(n);
    });

    const types = Object.keys(typeGroups);
    types.forEach((type, ti) => {
      const group = typeGroups[type];
      const angle0 = (ti / types.length) * Math.PI * 2;
      const radius = Math.min(w, h) * 0.32;
      const cx = w / 2 + Math.cos(angle0) * radius * 0.5;
      const cy = h / 2 + Math.sin(angle0) * radius * 0.5;
      group.forEach((n, ni) => {
        const subAngle = (ni / Math.max(group.length, 1)) * Math.PI * 2;
        const subR = Math.min(50, group.length * 8);
        positions[n.id] = { x: cx + Math.cos(subAngle) * subR, y: cy + Math.sin(subAngle) * subR, node: n };
      });
    });

    ctx.strokeStyle = '#d1d5db';
    ctx.lineWidth = 0.5;
    edges.forEach(e => {
      const from = positions[e.from];
      const to = positions[e.to];
      if (from && to) {
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();
      }
    });

    nodes.forEach(n => {
      const pos = positions[n.id];
      if (!pos) return;
      const r = n.type === 'Practice' ? 8 : 5;
      ctx.fillStyle = nodeColors[n.type] || '#6b7280';
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [graph]);

  const handleCanvasClick = useCallback((e) => {
    if (!graph || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = canvasRef.current.width / rect.width;
    const scaleY = canvasRef.current.height / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    const nodes = graph.nodes || [];
    const typeGroups = {};
    nodes.forEach(n => {
      if (!typeGroups[n.type]) typeGroups[n.type] = [];
      typeGroups[n.type].push(n);
    });
    const types = Object.keys(typeGroups);
    const w = canvasRef.current.width;
    const h = canvasRef.current.height;

    for (const [ti, type] of types.entries()) {
      const group = typeGroups[type];
      const angle0 = (ti / types.length) * Math.PI * 2;
      const radius = Math.min(w, h) * 0.32;
      const cx = w / 2 + Math.cos(angle0) * radius * 0.5;
      const cy = h / 2 + Math.sin(angle0) * radius * 0.5;
      for (const [ni, n] of group.entries()) {
        const subAngle = (ni / Math.max(group.length, 1)) * Math.PI * 2;
        const subR = Math.min(50, group.length * 8);
        const nx = cx + Math.cos(subAngle) * subR;
        const ny = cy + Math.sin(subAngle) * subR;
        if (Math.hypot(mx - nx, my - ny) < 10) {
          setSelectedNode(n);
          return;
        }
      }
    }
    setSelectedNode(null);
  }, [graph]);

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <Card sx={{ mb: 2 }}>
        <SectionTitle>Relationship Explorer</SectionTitle>
        <Typography variant="body2" color="text.secondary">No graph data available. Rebuild ontology first.</Typography>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Relationship Explorer ({graph.nodes.length} nodes, {graph.edges.length} edges)</SectionTitle>
      <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
        {Object.entries(nodeColors).map(([type, color]) => (
          <Box key={type} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
            <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>{type}</Typography>
          </Box>
        ))}
      </Box>
      <canvas
        ref={canvasRef}
        width={600}
        height={400}
        onClick={handleCanvasClick}
        style={{ width: '100%', height: 'auto', border: '1px solid #e5e7eb', borderRadius: 4, cursor: 'pointer' }}
      />
      {selectedNode && (
        <Box sx={{ mt: 1, p: 1, bgcolor: '#f9fafb', borderRadius: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{selectedNode.type}: {selectedNode.key}</Typography>
          {selectedNode.properties && Object.entries(selectedNode.properties).slice(0, 6).map(([k, v]) => (
            <Typography key={k} variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {k}: {typeof v === 'number' && v > 100 ? fmt(v) : String(v)}
            </Typography>
          ))}
        </Box>
      )}
    </Card>
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
  const [cfo, setCfo] = useState(null);
  const [cohorts, setCohorts] = useState(null);
  const [risks, setRisks] = useState(null);
  const [graph, setGraph] = useState(null);
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ctxData, cfoData, cohortData, riskData, graphData] = await Promise.all([
        getOntologyContext(practiceId),
        getCfo360(practiceId).catch(() => null),
        getOntologyCohorts(practiceId).catch(() => null),
        getOntologyRisks(practiceId).catch(() => null),
        getOntologyGraph(practiceId).catch(() => null),
      ]);
      setContext(ctxData);
      setCfo(cfoData);
      setCohorts(cohortData);
      setRisks(riskData);
      setGraph(graphData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (practiceId) {
      fetchAll();
    }
  }, [practiceId]);

  if (loading) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <CircularProgress size={32} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Loading practice intelligence...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
        <Button size="small" onClick={fetchAll} sx={{ ml: 2 }}>Retry</Button>
      </Alert>
    );
  }

  if (!context) return null;

  const { snapshot } = context;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Practice Intelligence
          <Chip label={context.version} size="small" sx={{ ml: 1, fontSize: '0.7rem' }} />
        </Typography>
        <Button variant="text" size="small" onClick={fetchAll} sx={{ textTransform: 'none' }}>
          Refresh
        </Button>
      </Box>

      <CfoSnapshot cfo={cfo} />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <TimeSeriesPanel cohorts={cohorts} />
        <CohortAgingPanel cohorts={cohorts} />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <PatientMixPanel patientDynamics={snapshot.patient_dynamics} cfo={cfo} />
        <RiskIntelligencePanel risks={risks} />
      </Box>

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

      <GraphExplorer graph={graph} />

      <Divider sx={{ my: 2 }} />

      <BriefPanel
        practiceId={practiceId}
        brief={brief}
        onBriefGenerated={(b) => setBrief(b)}
        onLimitAdjusted={() => fetchAll()}
      />
    </Box>
  );
}
