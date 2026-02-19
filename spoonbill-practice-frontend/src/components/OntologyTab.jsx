import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import {
  getOntologyContext, generateOntologyBrief, adjustPracticeLimit,
  getOntologyCohorts, getCfo360, getOntologyRisks, getOntologyGraph,
  getPatientRetention, getReimbursementMetrics, getRcmOps,
} from '../api';

const fmt = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A';

const SectionTitle = ({ children }) => (
  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', color: '#374151' }}>
    {children}
  </Typography>
);

const Card = ({ children, sx, ...props }) => (
  <Paper elevation={0} sx={{ p: 2, border: '1px solid #e5e7eb', borderRadius: 2, ...sx }} {...props}>{children}</Paper>
);

function ErrorState({ status, message, onRetry }) {
  const msgs = {
    401: { title: 'Session Expired', detail: 'Your session has expired. Please log in again.', color: '#d97706' },
    404: { title: 'Not Found', detail: 'This practice was not found or you do not have access.', color: '#6b7280' },
    503: { title: 'Service Unavailable', detail: 'Ontology data is unavailable \u2014 a migration may be pending. Check /diag.', color: '#7c3aed' },
  };
  const info = msgs[status] || { title: 'Error', detail: message || 'An unexpected error occurred.', color: '#dc2626' };
  return (
    <Alert severity="error" sx={{ mb: 2, borderLeft: `4px solid ${info.color}` }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{info.title}</Typography>
      <Typography variant="body2">{info.detail}</Typography>
      {onRetry && <Button size="small" onClick={onRetry} sx={{ mt: 1, textTransform: 'none' }}>Retry</Button>}
    </Alert>
  );
}

function Cfo360Panels({ cfo, prevCfo }) {
  if (!cfo) return null;
  const { capital, revenue, operational_risk, growth, payer_risk, patient_dynamics } = cfo;

  const change = (curr, prev) => {
    if (curr == null || prev == null || prev === 0) return null;
    return ((curr - prev) / Math.abs(prev));
  };

  const panels = [
    { label: 'Total Funded', value: fmt(capital?.total_funded_cents ?? 0), delta: change(capital?.total_funded_cents, prevCfo?.capital?.total_funded_cents) },
    { label: 'Utilization', value: pct(capital?.utilization), delta: change(capital?.utilization, prevCfo?.capital?.utilization), color: capital?.utilization > 0.85 ? '#dc2626' : '#059669', invertDelta: true },
    { label: 'Available Capacity', value: fmt(capital?.available_capacity_cents ?? 0), delta: change(capital?.available_capacity_cents, prevCfo?.capital?.available_capacity_cents) },
    { label: 'Billed MTD', value: fmt(revenue?.billed_mtd_cents ?? 0), delta: change(revenue?.billed_mtd_cents, prevCfo?.revenue?.billed_mtd_cents) },
    { label: 'Reimbursed MTD', value: fmt(revenue?.reimbursed_mtd_cents ?? 0), delta: change(revenue?.reimbursed_mtd_cents, prevCfo?.revenue?.reimbursed_mtd_cents) },
    { label: '90d Avg Monthly', value: fmt(revenue?.trailing_90d_avg_monthly_cents ?? 0), delta: change(revenue?.trailing_90d_avg_monthly_cents, prevCfo?.revenue?.trailing_90d_avg_monthly_cents) },
    { label: 'Denial Rate', value: pct(operational_risk?.denial_rate), delta: change(operational_risk?.denial_rate, prevCfo?.operational_risk?.denial_rate), invertDelta: true, color: operational_risk?.denial_rate > 0.1 ? '#dc2626' : '#059669' },
    { label: 'Exception Rate', value: pct(operational_risk?.exception_rate), delta: change(operational_risk?.exception_rate, prevCfo?.operational_risk?.exception_rate), invertDelta: true, color: operational_risk?.exception_rate > 0.05 ? '#d97706' : '#059669' },
  ];

  const drivers = [];
  if (growth?.claim_volume_growth_rate != null) drivers.push({ label: 'Claim Volume', value: `${growth.claim_volume_growth_rate > 0 ? '+' : ''}${(growth.claim_volume_growth_rate * 100).toFixed(0)}% vs prior period` });
  if (payer_risk?.concentration > 0.6) drivers.push({ label: 'Payer Concentration', value: `Top payer (${payer_risk.top_payer}) at ${pct(payer_risk.concentration)}` });
  if (operational_risk?.denial_trend === 'worsening') drivers.push({ label: 'Denial Trend', value: 'Worsening \u2014 30d rate above lifetime average' });
  if (patient_dynamics?.new_patients_30d > 0) drivers.push({ label: 'New Patients', value: `${patient_dynamics.new_patients_30d} new in last 30d` });

  return (
    <Box sx={{ mb: 3 }}>
      <SectionTitle>CFO 360 Snapshot</SectionTitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 1.5, mb: 2 }}>
        {panels.map((c) => (
          <Card key={c.label} sx={{ textAlign: 'center', position: 'relative' }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: c.color || 'inherit', fontSize: '1.1rem' }}>{c.value}</Typography>
            <Typography variant="caption" color="text.secondary">{c.label}</Typography>
            {c.delta != null && (
              <Typography variant="caption" sx={{
                display: 'block', mt: 0.25, fontWeight: 600, fontSize: '0.65rem',
                color: (c.invertDelta ? c.delta < 0 : c.delta > 0) ? '#059669' : c.delta === 0 ? '#6b7280' : '#dc2626',
              }}>
                {c.delta > 0 ? '+' : ''}{(c.delta * 100).toFixed(1)}% vs prior
              </Typography>
            )}
          </Card>
        ))}
      </Box>
      {drivers.length > 0 && (
        <Card sx={{ bgcolor: '#f9fafb' }}>
          <Typography variant="caption" sx={{ fontWeight: 700, color: '#374151', textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: '0.05em' }}>Top Drivers</Typography>
          {drivers.map((d, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
              <Chip label={d.label} size="small" sx={{ fontSize: '0.65rem', fontWeight: 600, height: 20 }} />
              <Typography variant="caption" color="text.secondary">{d.value}</Typography>
            </Box>
          ))}
        </Card>
      )}
    </Box>
  );
}

function RetentionPanel({ retention }) {
  if (!retention) return null;
  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Patient Retention</SectionTitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 1.5 }}>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{retention.active_patients_12mo}</Typography>
          <Typography variant="caption" color="text.secondary">Active (12mo)</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{retention.new_patients}</Typography>
          <Typography variant="caption" color="text.secondary">New</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{retention.returning_patients}</Typography>
          <Typography variant="caption" color="text.secondary">Returning</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: retention.repeat_visit_rate_90d > 0.3 ? '#059669' : '#d97706' }}>{pct(retention.repeat_visit_rate_90d)}</Typography>
          <Typography variant="caption" color="text.secondary">Repeat (90d)</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{pct(retention.repeat_visit_rate_180d)}</Typography>
          <Typography variant="caption" color="text.secondary">Repeat (180d)</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: retention.reactivation_rate > 0 ? '#059669' : '#6b7280' }}>{pct(retention.reactivation_rate)}</Typography>
          <Typography variant="caption" color="text.secondary">Reactivated</Typography>
        </Box>
      </Box>
      {retention.overdue_recall_cohorts?.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#d97706' }}>OVERDUE RECALL ({retention.overdue_recall_cohorts.length} patients)</Typography>
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
            {retention.overdue_recall_cohorts.slice(0, 8).map((p, i) => (
              <Chip key={i} label={'...' + p.patient_hash.slice(-4) + ': ' + p.months_since_last_preventive + 'mo'} size="small" variant="outlined" sx={{ fontSize: '0.65rem', borderColor: '#d97706', color: '#92400e' }} />
            ))}
          </Box>
        </Box>
      )}
      {retention.patient_value_proxy?.length > 0 && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>TOP PATIENT VALUE (12mo)</Typography>
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
            {retention.patient_value_proxy.slice(0, 5).map((p, i) => (
              <Chip key={i} label={'...' + p.patient_hash.slice(-4) + ': ' + fmt(p.billed_12m_cents)} size="small" sx={{ fontSize: '0.65rem' }} />
            ))}
          </Box>
        </Box>
      )}
    </Card>
  );
}
function ReimbursementPanel({ reimbursement }) {
  if (!reimbursement) return null;
  const { by_payer, by_procedure_family, time_to_adjudication } = reimbursement;
  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>Reimbursement Performance</SectionTitle>
      {by_payer && Object.keys(by_payer).length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>BY PAYER</Typography>
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', mt: 0.5 }}>
            <Box component="thead">
              <Box component="tr" sx={{ borderBottom: '1px solid #e5e7eb' }}>
                {['Payer', 'Realized', 'Denial', 'Billed'].map(h => (
                  <Box key={h} component="th" sx={{ textAlign: h === 'Payer' ? 'left' : 'right', py: 0.5, fontSize: '0.7rem', color: '#6b7280' }}>{h}</Box>
                ))}
              </Box>
            </Box>
            <Box component="tbody">
              {Object.entries(by_payer).map(([payer, d]) => (
                <Box component="tr" key={payer} sx={{ borderBottom: '1px solid #f3f4f6' }}>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem' }}>{payer}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right', color: d.realized_rate === 'missing_data' ? '#6b7280' : d.realized_rate < 0.5 ? '#dc2626' : '#059669' }}>
                    {d.realized_rate === 'missing_data' ? 'N/A' : pct(d.realized_rate)}
                  </Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right', color: d.denial_rate > 0.1 ? '#dc2626' : 'inherit' }}>{pct(d.denial_rate)}</Box>
                  <Box component="td" sx={{ py: 0.5, fontSize: '0.8rem', textAlign: 'right' }}>{fmt(d.billed_cents)}</Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      )}
      {by_procedure_family && Object.keys(by_procedure_family).length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>BY PROCEDURE FAMILY</Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            {Object.entries(by_procedure_family).map(([fam, d]) => (
              <Card key={fam} sx={{ p: 1, minWidth: 100, textAlign: 'center' }}>
                <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.7rem' }}>{fam}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700, color: d.realized_rate === 'missing_data' ? '#6b7280' : d.realized_rate < 0.5 ? '#dc2626' : '#059669' }}>
                  {d.realized_rate === 'missing_data' ? 'N/A' : pct(d.realized_rate)}
                </Typography>
                <Typography variant="caption" color="text.secondary">Denial: {pct(d.denial_rate)}</Typography>
              </Card>
            ))}
          </Box>
        </Box>
      )}
      {time_to_adjudication && Object.keys(time_to_adjudication).length > 0 && (
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>TIME TO ADJUDICATION</Typography>
          <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
            {Object.entries(time_to_adjudication).map(([payer, d]) => (
              <Chip key={payer} label={d === 'missing_data' ? payer + ': N/A' : payer + ': P50 ' + d.p50_days + 'd / P90 ' + d.p90_days + 'd'} size="small" sx={{ fontSize: '0.65rem' }} />
            ))}
          </Box>
        </Box>
      )}
    </Card>
  );
}

function RcmOpsPanel({ rcm }) {
  if (!rcm) return null;
  const { claims_aging_buckets, exception_rate, exception_count, declined_count, total_claims } = rcm;
  return (
    <Card sx={{ mb: 2 }}>
      <SectionTitle>RCM Operations</SectionTitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, mb: 2 }}>
        {[['0-30d', claims_aging_buckets?.['0_30']], ['30-60d', claims_aging_buckets?.['30_60']], ['60-90d', claims_aging_buckets?.['60_90']], ['90+d', claims_aging_buckets?.['90_plus']]].map(([label, bucket]) => (
          <Box key={label} sx={{ textAlign: 'center', p: 1, bgcolor: label === '90+d' && bucket?.count > 0 ? '#fef2f2' : '#f9fafb', borderRadius: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: label === '90+d' && bucket?.count > 0 ? '#dc2626' : 'inherit' }}>{bucket?.count ?? 0}</Typography>
            <Typography variant="caption" color="text.secondary">{label}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6rem' }}>{fmt(bucket?.total_cents ?? 0)}</Typography>
          </Box>
        ))}
      </Box>
      <Box sx={{ display: 'flex', gap: 3 }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Exception Rate</Typography>
          <Typography variant="body2" sx={{ fontWeight: 700, color: exception_rate > 0.05 ? '#dc2626' : '#059669' }}>{pct(exception_rate)}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Exceptions</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{exception_count}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Declined</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{declined_count}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Total Claims</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{total_claims}</Typography>
        </Box>
      </Box>
      <Box sx={{ mt: 1.5 }}>
        <Typography variant="caption" color="text.secondary">Forecasted Cash-In: </Typography>
        <Chip label="7d: pending" size="small" sx={{ fontSize: '0.6rem', mr: 0.5 }} />
        <Chip label="14d: pending" size="small" sx={{ fontSize: '0.6rem', mr: 0.5 }} />
        <Chip label="30d: pending" size="small" sx={{ fontSize: '0.6rem' }} />
      </Box>
    </Card>
  );
}

const NODE_COLORS = {
  Practice: '#111827', Payer: '#2563eb', Patient: '#7c3aed',
  Procedure: '#059669', Claim: '#6b7280', PaymentIntent: '#d97706',
  ProcedureFamily: '#0d9488',
};

const NODE_RADIUS = { Practice: 24, Payer: 18, Patient: 14, ProcedureFamily: 20, Procedure: 12, Claim: 10, PaymentIntent: 12 };

function RelationshipExplorer({ practiceId, initialGraph }) {
  const canvasRef = useRef(null);
  const [graph, setGraph] = useState(initialGraph);
  const [mode, setMode] = useState('revenue_cycle');
  const [range, setRange] = useState('90d');
  const [payerFilter, setPayerFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [focusNodeId, setFocusNodeId] = useState(null);
  const [pinnedNodes, setPinnedNodes] = useState(new Set());
  const [showLabels, setShowLabels] = useState(true);
  const [loading, setLoading] = useState(false);
  const positionsRef = useRef({});

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getOntologyGraph(practiceId, {
        mode, range, payer: payerFilter || undefined, state: stateFilter || undefined,
        focus_node_id: focusNodeId || undefined,
      });
      setGraph(data);
    } catch (err) {
      console.error('Graph fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [practiceId, mode, range, payerFilter, stateFilter, focusNodeId]);

  useEffect(() => { fetchGraph(); }, [mode, range, payerFilter, stateFilter, focusNodeId]);

  const filteredNodes = useMemo(() => {
    if (!graph?.nodes) return [];
    if (!searchQuery) return graph.nodes;
    const q = searchQuery.toLowerCase();
    return graph.nodes.filter(n => {
      const label = (n.label || '').toLowerCase();
      const key = (n.key || '').toLowerCase();
      const props = n.properties || {};
      const payer = (props.payer || props.name || '').toLowerCase();
      const token = (props.claim_token || '').toLowerCase();
      const cdt = (props.cdt_code || '').toLowerCase();
      const hash = (props.patient_hash || '').toLowerCase();
      return label.includes(q) || key.includes(q) || payer.includes(q) || token.includes(q) || cdt.includes(q) || hash.includes(q);
    });
  }, [graph, searchQuery]);

  const filteredEdges = useMemo(() => {
    if (!graph?.edges) return [];
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return graph.edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));
  }, [graph, filteredNodes]);

  useEffect(() => {
    if (!canvasRef.current || filteredNodes.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const displayW = canvas.clientWidth;
    const displayH = 500;
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    canvas.style.height = displayH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, displayW, displayH);

    const w = displayW;
    const h = displayH;
    const positions = {};
    const typeGroups = {};
    filteredNodes.forEach(n => {
      if (!typeGroups[n.type]) typeGroups[n.type] = [];
      typeGroups[n.type].push(n);
    });

    const types = Object.keys(typeGroups);
    const centerX = w / 2;
    const centerY = h / 2;

    types.forEach((type, ti) => {
      const group = typeGroups[type];
      const angle0 = (ti / types.length) * Math.PI * 2 - Math.PI / 2;
      const orbitalR = Math.min(w, h) * 0.32;
      const cx = centerX + Math.cos(angle0) * orbitalR;
      const cy = centerY + Math.sin(angle0) * orbitalR;
      group.forEach((n, ni) => {
        if (pinnedNodes.has(n.id) && positionsRef.current[n.id]) {
          positions[n.id] = positionsRef.current[n.id];
        } else {
          const subAngle = (ni / Math.max(group.length, 1)) * Math.PI * 2;
          const subR = Math.min(70, Math.max(20, group.length * 6));
          positions[n.id] = { x: cx + Math.cos(subAngle) * subR, y: cy + Math.sin(subAngle) * subR };
        }
      });
    });
    positionsRef.current = positions;

    const highlightIds = new Set();
    if (hoveredNode || selectedNode) {
      const targetId = hoveredNode?.id || selectedNode?.id;
      highlightIds.add(targetId);
      filteredEdges.forEach(e => {
        if (e.from === targetId) highlightIds.add(e.to);
        if (e.to === targetId) highlightIds.add(e.from);
      });
    }

    filteredEdges.forEach(e => {
      const from = positions[e.from];
      const to = positions[e.to];
      if (!from || !to) return;
      const isHighlighted = highlightIds.size > 0 && highlightIds.has(e.from) && highlightIds.has(e.to);
      ctx.strokeStyle = isHighlighted ? '#2563eb' : (highlightIds.size > 0 ? '#e5e7eb' : '#cbd5e1');
      ctx.lineWidth = isHighlighted ? 1.5 : 0.5;
      ctx.globalAlpha = isHighlighted ? 1 : (highlightIds.size > 0 ? 0.15 : 0.6);
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();

      if (showLabels && e.type_label && (isHighlighted || (highlightIds.size === 0 && filteredNodes.length < 50))) {
        const mx = (from.x + to.x) / 2;
        const my = (from.y + to.y) / 2;
        ctx.globalAlpha = isHighlighted ? 0.9 : 0.5;
        ctx.font = '9px -apple-system, system-ui, sans-serif';
        ctx.fillStyle = '#6b7280';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(e.type_label, mx, my - 4);
      }
    });
    ctx.globalAlpha = 1;

    filteredNodes.forEach(n => {
      const pos = positions[n.id];
      if (!pos) return;
      const r = NODE_RADIUS[n.type] || 10;
      const isHighlighted = highlightIds.size === 0 || highlightIds.has(n.id);
      const isSelected = selectedNode?.id === n.id;
      const isPinned = pinnedNodes.has(n.id);

      ctx.globalAlpha = isHighlighted ? 1 : 0.15;

      if (isSelected) {
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r + 3, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (isPinned) {
        ctx.strokeStyle = '#d97706';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r + 2, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.fillStyle = NODE_COLORS[n.type] || '#6b7280';
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#fff';
      ctx.font = 'bold ' + Math.max(7, r * 0.6) + 'px -apple-system, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const typeAbbr = { Practice: 'P', Payer: 'PAY', Patient: 'PT', Procedure: 'CDT', Claim: 'C', PaymentIntent: '$', ProcedureFamily: 'FAM' };
      ctx.fillText(typeAbbr[n.type] || n.type[0], pos.x, pos.y);

      if (showLabels && isHighlighted) {
        ctx.fillStyle = '#111827';
        ctx.font = '10px -apple-system, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(n.label || '', pos.x, pos.y + r + 12);
        if (n.subtitle_stat) {
          ctx.fillStyle = '#6b7280';
          ctx.font = '9px -apple-system, system-ui, sans-serif';
          ctx.fillText(n.subtitle_stat, pos.x, pos.y + r + 22);
        }
      }
    });
    ctx.globalAlpha = 1;
  }, [filteredNodes, filteredEdges, selectedNode, hoveredNode, pinnedNodes, showLabels]);

  const findNodeAt = useCallback((mx, my) => {
    const positions = positionsRef.current;
    for (const n of filteredNodes) {
      const pos = positions[n.id];
      if (!pos) continue;
      const r = NODE_RADIUS[n.type] || 10;
      if (Math.hypot(mx - pos.x, my - pos.y) < r + 4) return n;
    }
    return null;
  }, [filteredNodes]);

  const getCanvasCoords = useCallback((e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const handleCanvasClick = useCallback((e) => {
    const { x, y } = getCanvasCoords(e);
    setSelectedNode(findNodeAt(x, y));
  }, [findNodeAt, getCanvasCoords]);

  const handleCanvasMouseMove = useCallback((e) => {
    const { x, y } = getCanvasCoords(e);
    const node = findNodeAt(x, y);
    setHoveredNode(node);
    if (canvasRef.current) canvasRef.current.style.cursor = node ? 'pointer' : 'default';
  }, [findNodeAt, getCanvasCoords]);

  const handleDoubleClick = useCallback((e) => {
    const { x, y } = getCanvasCoords(e);
    const node = findNodeAt(x, y);
    if (node) setFocusNodeId(node.id);
  }, [findNodeAt, getCanvasCoords]);

  const handlePinToggle = useCallback(() => {
    if (!selectedNode) return;
    setPinnedNodes(prev => {
      const next = new Set(prev);
      if (next.has(selectedNode.id)) next.delete(selectedNode.id);
      else next.add(selectedNode.id);
      return next;
    });
  }, [selectedNode]);

  const relatedEdges = useMemo(() => {
    if (!selectedNode || !graph?.edges) return [];
    return graph.edges.filter(e => e.from === selectedNode.id || e.to === selectedNode.id);
  }, [selectedNode, graph]);

  const relatedObjects = useMemo(() => {
    if (!selectedNode || !graph?.nodes) return {};
    const relIds = new Set();
    relatedEdges.forEach(e => {
      if (e.from !== selectedNode.id) relIds.add(e.from);
      if (e.to !== selectedNode.id) relIds.add(e.to);
    });
    const grouped = {};
    graph.nodes.filter(n => relIds.has(n.id)).forEach(n => {
      if (!grouped[n.type]) grouped[n.type] = [];
      grouped[n.type].push(n);
    });
    return grouped;
  }, [selectedNode, graph, relatedEdges]);

  if (!graph || (!graph.nodes?.length && !loading)) {
    return (
      <Card sx={{ mb: 2 }}>
        <SectionTitle>Relationship Explorer</SectionTitle>
        <Typography variant="body2" color="text.secondary">No graph data available. Rebuild ontology first.</Typography>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2, p: 0, overflow: 'hidden' }}>
      <Box sx={{ p: 2, borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <SectionTitle>Relationship Explorer</SectionTitle>
        <Chip label={filteredNodes.length + ' nodes'} size="small" sx={{ fontSize: '0.65rem' }} />
        <Chip label={filteredEdges.length + ' edges'} size="small" sx={{ fontSize: '0.65rem' }} />
        {graph.mode && <Chip label={graph.mode.replace(/_/g, ' ')} size="small" color="primary" sx={{ fontSize: '0.65rem' }} />}
        {loading && <CircularProgress size={16} />}
      </Box>

      <Box sx={{ p: 1.5, borderBottom: '1px solid #e5e7eb', display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', bgcolor: '#f9fafb' }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel sx={{ fontSize: '0.75rem' }}>Mode</InputLabel>
          <Select value={mode} onChange={(e) => setMode(e.target.value)} label="Mode" sx={{ fontSize: '0.8rem' }}>
            <MenuItem value="revenue_cycle">Revenue Cycle</MenuItem>
            <MenuItem value="patient_retention">Patient Retention</MenuItem>
            <MenuItem value="reimbursement_insights">Reimbursement</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 90 }}>
          <InputLabel sx={{ fontSize: '0.75rem' }}>Range</InputLabel>
          <Select value={range} onChange={(e) => setRange(e.target.value)} label="Range" sx={{ fontSize: '0.8rem' }}>
            <MenuItem value="30d">30 days</MenuItem>
            <MenuItem value="90d">90 days</MenuItem>
            <MenuItem value="12m">12 months</MenuItem>
          </Select>
        </FormControl>
        <TextField size="small" label="Payer" value={payerFilter} onChange={(e) => setPayerFilter(e.target.value)} sx={{ width: 120, '& .MuiInputBase-input': { fontSize: '0.8rem' } }} />
        <TextField size="small" label="State" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} sx={{ width: 100, '& .MuiInputBase-input': { fontSize: '0.8rem' } }} />
        <TextField size="small" label="Search" placeholder="payer, token, CDT, hash..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} sx={{ width: 180, '& .MuiInputBase-input': { fontSize: '0.8rem' } }} />
        <FormControlLabel control={<Switch size="small" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} />} label={<Typography variant="caption">Labels</Typography>} />
        {focusNodeId && (
          <Button size="small" variant="outlined" onClick={() => setFocusNodeId(null)} sx={{ textTransform: 'none', fontSize: '0.7rem' }}>Clear Focus</Button>
        )}
      </Box>

      <Box sx={{ display: 'flex' }}>
        <Box sx={{ flex: 1, position: 'relative' }}>
          <Box sx={{ display: 'flex', gap: 1, p: 1, flexWrap: 'wrap' }}>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <Box key={type} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
                <Typography variant="caption" sx={{ fontSize: '0.6rem' }}>{type}</Typography>
              </Box>
            ))}
          </Box>
          <canvas
            ref={canvasRef}
            onClick={handleCanvasClick}
            onMouseMove={handleCanvasMouseMove}
            onDoubleClick={handleDoubleClick}
            style={{ width: '100%', display: 'block', cursor: 'default' }}
          />
        </Box>

        {selectedNode && (
          <Box sx={{ width: 300, borderLeft: '1px solid #e5e7eb', p: 2, bgcolor: '#fafbfc', overflowY: 'auto', maxHeight: 560 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
              <Box>
                <Chip label={selectedNode.type} size="small" sx={{ bgcolor: NODE_COLORS[selectedNode.type] || '#6b7280', color: '#fff', fontWeight: 700, fontSize: '0.65rem', mb: 0.5 }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{selectedNode.label}</Typography>
                {selectedNode.subtitle_stat && <Typography variant="caption" color="text.secondary">{selectedNode.subtitle_stat}</Typography>}
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title={pinnedNodes.has(selectedNode.id) ? 'Unpin' : 'Pin'}>
                  <IconButton size="small" onClick={handlePinToggle} sx={{ border: '1px solid #e5e7eb' }}>
                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>{pinnedNodes.has(selectedNode.id) ? 'Unpin' : 'Pin'}</Typography>
                  </IconButton>
                </Tooltip>
                <Tooltip title="Focus (2 hops)">
                  <IconButton size="small" onClick={() => setFocusNodeId(selectedNode.id)} sx={{ border: '1px solid #e5e7eb' }}>
                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Focus</Typography>
                  </IconButton>
                </Tooltip>
                <IconButton size="small" onClick={() => setSelectedNode(null)} sx={{ border: '1px solid #e5e7eb' }}>
                  <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>X</Typography>
                </IconButton>
              </Box>
            </Box>

            <Divider sx={{ mb: 1.5 }} />
            <Typography variant="caption" sx={{ fontWeight: 700, color: '#374151', textTransform: 'uppercase', fontSize: '0.65rem' }}>Properties</Typography>
            <Box sx={{ mt: 0.5, mb: 1.5 }}>
              {selectedNode.properties && Object.entries(selectedNode.properties).map(([k, v]) => (
                <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.25 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>{k}</Typography>
                  <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.7rem', maxWidth: 140, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {typeof v === 'number' && v > 100 ? fmt(v) : String(v ?? 'N/A')}
                  </Typography>
                </Box>
              ))}
            </Box>

            {Object.keys(relatedObjects).length > 0 && (
              <>
                <Divider sx={{ mb: 1 }} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: '#374151', textTransform: 'uppercase', fontSize: '0.65rem' }}>Related Objects</Typography>
                {Object.entries(relatedObjects).map(([type, objs]) => (
                  <Box key={type} sx={{ mt: 0.5 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: NODE_COLORS[type] || '#6b7280', fontSize: '0.65rem' }}>{type} ({objs.length})</Typography>
                    {objs.slice(0, 5).map(o => (
                      <Box key={o.id} sx={{ py: 0.25, pl: 1, cursor: 'pointer', '&:hover': { bgcolor: '#f3f4f6' }, borderRadius: 0.5 }} onClick={() => setSelectedNode(o)}>
                        <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>{o.label}</Typography>
                      </Box>
                    ))}
                    {objs.length > 5 && <Typography variant="caption" color="text.secondary" sx={{ pl: 1, fontSize: '0.6rem' }}>+{objs.length - 5} more</Typography>}
                  </Box>
                ))}
              </>
            )}

            {relatedEdges.length > 0 && (
              <>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: '#374151', textTransform: 'uppercase', fontSize: '0.65rem' }}>Why Connected?</Typography>
                {relatedEdges.slice(0, 8).map((e, i) => (
                  <Box key={i} sx={{ py: 0.25, display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    <Chip label={e.type_label || e.type} size="small" sx={{ fontSize: '0.6rem', height: 18 }} />
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                      {e.from === selectedNode.id ? 'outgoing' : 'incoming'}
                    </Typography>
                  </Box>
                ))}
              </>
            )}

            {selectedNode.provenance && (
              <>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: '#374151', textTransform: 'uppercase', fontSize: '0.65rem' }}>Data Provenance</Typography>
                <Box sx={{ mt: 0.5 }}>
                  {Object.entries(selectedNode.provenance).map(([k, v]) => (
                    <Typography key={k} variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.65rem' }}>{k}: {String(v)}</Typography>
                  ))}
                </Box>
              </>
            )}
          </Box>
        )}
      </Box>
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
        <Button variant="outlined" size="small" onClick={handleGenerate} disabled={loading} sx={{ textTransform: 'none' }}>
          {loading ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
          {brief ? 'Regenerate Brief' : 'Generate Brief'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
      {brief && (
        <Box>
          <Typography variant="body2" sx={{ mb: 1.5 }}>{brief.summary}</Typography>
          {brief.key_drivers?.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>KEY DRIVERS</Typography>
              {brief.key_drivers.map((d, i) => <Typography key={i} variant="body2" sx={{ pl: 1 }}>{d}</Typography>)}
            </Box>
          )}
          {brief.risks?.length > 0 && (
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
          {brief.recommended_actions?.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#059669' }}>RECOMMENDED ACTIONS</Typography>
              {brief.recommended_actions.map((a, i) => (
                <Box key={i} sx={{ pl: 1, py: 0.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ flex: 1 }}>
                    <Chip label={a.action} size="small" sx={{ fontWeight: 600, fontSize: '0.7rem' }} />
                    <Typography variant="body2" sx={{ mt: 0.5 }}>{a.reason}</Typography>
                  </Box>
                  {a.action === 'ADJUST_LIMIT' && a.params?.new_limit && (
                    <Button variant="contained" size="small" onClick={() => handleAdjustLimit(a)} disabled={adjusting} sx={{ textTransform: 'none', bgcolor: '#111', '&:hover': { bgcolor: '#333' } }}>
                      {adjusting ? 'Applying...' : 'Apply (' + fmt(a.params.new_limit) + ')'}
                    </Button>
                  )}
                </Box>
              ))}
            </Box>
          )}
          {brief.missing_data?.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#6b7280' }}>MISSING DATA</Typography>
              {brief.missing_data.map((m, i) => <Typography key={i} variant="body2" color="text.secondary" sx={{ pl: 1 }}>{m}</Typography>)}
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
}

export default function OntologyTab({ practiceId }) {
  const [cfo, setCfo] = useState(null);
  const [retention, setRetention] = useState(null);
  const [reimbursement, setReimbursement] = useState(null);
  const [rcm, setRcm] = useState(null);
  const [risks, setRisks] = useState(null);
  const [graph, setGraph] = useState(null);
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [errorStatus, setErrorStatus] = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    try {
      const [cfoData, retentionData, reimbursementData, rcmData, riskData, graphData] = await Promise.all([
        getCfo360(practiceId).catch(() => null),
        getPatientRetention(practiceId).catch(() => null),
        getReimbursementMetrics(practiceId).catch(() => null),
        getRcmOps(practiceId).catch(() => null),
        getOntologyRisks(practiceId).catch(() => null),
        getOntologyGraph(practiceId).catch(() => null),
      ]);
      setCfo(cfoData);
      setRetention(retentionData);
      setReimbursement(reimbursementData);
      setRcm(rcmData);
      setRisks(riskData);
      setGraph(graphData);
    } catch (err) {
      if (err.message?.includes('401') || err.message?.includes('Session expired')) setErrorStatus(401);
      else if (err.message?.includes('404')) setErrorStatus(404);
      else if (err.message?.includes('503')) setErrorStatus(503);
      else setErrorStatus(500);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (practiceId) fetchAll();
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
    return <ErrorState status={errorStatus} message={error} onRetry={fetchAll} />;
  }

  const riskSeverityColors = { high: '#dc2626', medium: '#d97706', low: '#059669' };
  const riskSeverityBg = { high: '#fef2f2', medium: '#fffbeb', low: '#f0fdf4' };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Practice Intelligence
          <Chip label="ontology-v2.1" size="small" sx={{ ml: 1, fontSize: '0.7rem' }} />
        </Typography>
        <Button variant="text" size="small" onClick={fetchAll} sx={{ textTransform: 'none' }}>Refresh</Button>
      </Box>

      <Cfo360Panels cfo={cfo} prevCfo={null} />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <RetentionPanel retention={retention} />
        <ReimbursementPanel reimbursement={reimbursement} />
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, mb: 2 }}>
        <RcmOpsPanel rcm={rcm} />
        {risks && risks.length > 0 ? (
          <Card sx={{ mb: 2, border: risks.some(r => r.severity === 'high') ? '1px solid #fca5a5' : '1px solid #e5e7eb' }}>
            <SectionTitle>Risk Intelligence ({risks.length} signals)</SectionTitle>
            {risks.map((r, i) => (
              <Box key={i} sx={{ p: 1, mb: 0.5, bgcolor: riskSeverityBg[r.severity] || '#f9fafb', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                  <Chip label={r.severity?.toUpperCase()} size="small" sx={{ bgcolor: (riskSeverityColors[r.severity] || '#6b7280') + '20', color: riskSeverityColors[r.severity] || '#6b7280', fontWeight: 700, fontSize: '0.65rem', height: 20 }} />
                  <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{r.type}</Typography>
                </Box>
                <Typography variant="body2" sx={{ fontSize: '0.8rem', color: '#374151' }}>{r.explanation}</Typography>
              </Box>
            ))}
          </Card>
        ) : (
          <Card sx={{ mb: 2 }}>
            <SectionTitle>Risk Intelligence</SectionTitle>
            <Typography variant="body2" color="text.secondary">No active risk signals detected.</Typography>
          </Card>
        )}
      </Box>

      <Divider sx={{ my: 2 }} />

      <RelationshipExplorer practiceId={practiceId} initialGraph={graph} />

      <Divider sx={{ my: 2 }} />

      <BriefPanel practiceId={practiceId} brief={brief} onBriefGenerated={(b) => setBrief(b)} onLimitAdjusted={() => fetchAll()} />
    </Box>
  );
}
