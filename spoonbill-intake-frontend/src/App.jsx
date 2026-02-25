import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useParams, useNavigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import Slider from '@mui/material/Slider';
import IconButton from '@mui/material/IconButton';
import Divider from '@mui/material/Divider';
import LinearProgress from '@mui/material/LinearProgress';

import { createSpoonbillTheme, tokens } from './theme.js';

const theme = createSpoonbillTheme();
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const PRACTICE_PORTAL_URL = import.meta.env.VITE_PRACTICE_PORTAL_URL || 'http://localhost:5174';

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE_URL) {
  console.warn('[Spoonbill Intake] VITE_API_BASE_URL is not set.');
}

const STORAGE_KEY = 'spoonbill_intake_draft';

const steps = [
  'Identity & Compliance',
  'Revenue & Production',
  'Payer & Claims',
  'Billing Operations',
  'Financial Stability',
  'Spoonbill Fit',
];

const ownershipOptions = [
  { value: 'SOLE_PROPRIETOR', label: 'Sole Proprietor' },
  { value: 'PARTNERSHIP', label: 'Partnership' },
  { value: 'LLC', label: 'LLC' },
  { value: 'S_CORP', label: 'S-Corp' },
  { value: 'C_CORP', label: 'C-Corp' },
  { value: 'DSO_AFFILIATED', label: 'DSO-Affiliated' },
  { value: 'OTHER', label: 'Other' },
];

const billingModels = [
  { value: 'IN_HOUSE', label: 'In-House' },
  { value: 'OUTSOURCED', label: 'Outsourced' },
  { value: 'HYBRID', label: 'Hybrid' },
];

const pmsOptions = [
  { value: 'Open Dental', label: 'Open Dental' },
  { value: 'Open Dental Cloud', label: 'Open Dental Cloud' },
  { value: 'Dentrix', label: 'Dentrix' },
  { value: 'Eaglesoft', label: 'Eaglesoft' },
  { value: 'Curve Dental', label: 'Curve Dental' },
  { value: 'Denticon', label: 'Denticon' },
  { value: 'Other', label: 'Other' },
];

const cashRangeOptions = [
  { value: 'UNDER_25K', label: 'Under $25,000' },
  { value: '25K_50K', label: '$25,000 \u2013 $50,000' },
  { value: '50K_100K', label: '$50,000 \u2013 $100,000' },
  { value: '100K_250K', label: '$100,000 \u2013 $250,000' },
  { value: '250K_500K', label: '$250,000 \u2013 $500,000' },
  { value: 'OVER_500K', label: 'Over $500,000' },
];


const initialFormData = {
  legal_name: '',
  dba: '',
  ein: '',
  npi_individual: '',
  npi_group: '',
  years_in_operation: '',
  ownership_structure: '',
  prior_bankruptcy: false,
  pending_litigation: false,
  gross_production: '',
  net_collections: '',
  insurance_collections: '',
  patient_collections: '',
  seasonality_swings: false,
  top_payers: [{ name: '', pct_revenue: '' }],
  pct_ppo: '',
  pct_medicaid: '',
  pct_ffs: '',
  pct_capitation: '',
  avg_claim_size: '',
  avg_monthly_claim_count: '',
  avg_days_to_reimbursement: '',
  estimated_denial_rate: '',
  practice_management_software: '',
  billing_model: 'IN_HOUSE',
  billing_staff_count: '',
  dedicated_rcm_manager: false,
  written_billing_sop: false,
  avg_ar_days: '',
  outstanding_ar_balance: '',
  primary_bank: '',
  cash_on_hand_range: '',
  existing_loc: '',
  monthly_debt_payments: '',
  missed_loan_payments_24m: false,
  expected_monthly_funding: '',
  urgency_scale: 3,
  willing_to_integrate_api: false,
  why_spoonbill: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
};

function dollarsToCents(val) {
  if (!val && val !== 0) return null;
  const num = parseFloat(String(val).replace(/[,$]/g, ''));
  return isNaN(num) ? null : Math.round(num * 100);
}

function formatWithCommas(val) {
  if (!val && val !== '0') return '';
  const raw = String(val).replace(/[^0-9]/g, '');
  if (!raw) return '';
  return Number(raw).toLocaleString('en-US');
}

function formatEIN(val) {
  if (!val) return '';
  const raw = String(val).replace(/[^0-9]/g, '');
  if (raw.length <= 2) return raw;
  return raw.slice(0, 2) + '-' + raw.slice(2);
}

function SectionTitle({ children }) {
  return (
    <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5, color: tokens.colors.text.primary }}>
      {children}
    </Typography>
  );
}

function SectionSubtitle({ children }) {
  return (
    <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
      {children}
    </Typography>
  );
}

function DollarField({ label, value, onChange, required, error, helperText, ...props }) {
  const handleChange = (e) => {
    const raw = e.target.value.replace(/[^0-9]/g, '');
    onChange({ target: { value: raw } });
  };
  return (
    <TextField
      label={label}
      value={formatWithCommas(value)}
      onChange={handleChange}
      required={required}
      fullWidth
      error={error}
      helperText={helperText}
      slotProps={{ input: { startAdornment: <Typography sx={{ mr: 0.5, color: tokens.colors.text.muted }}>$</Typography> } }}
      {...props}
    />
  );
}

function PercentField({ label, value, onChange, ...props }) {
  return (
    <TextField
      label={label}
      value={value}
      onChange={onChange}
      fullWidth
      type="number"
      slotProps={{ input: { endAdornment: <Typography sx={{ ml: 0.5, color: tokens.colors.text.muted }}>%</Typography> }, htmlInput: { min: 0, max: 100, step: 0.1 } }}
      {...props}
    />
  );
}

function Step1Identity({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Practice Identity & Compliance</SectionTitle>
      <SectionSubtitle>Legal details and compliance information about your practice.</SectionSubtitle>
      <TextField label="Legal Entity Name" value={formData.legal_name} onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })} required fullWidth error={!!errors.legal_name} helperText={errors.legal_name} />
      <TextField label="DBA (Doing Business As)" value={formData.dba} onChange={(e) => setFormData({ ...formData, dba: e.target.value })} fullWidth />
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <TextField label="EIN" value={formatEIN(formData.ein)} onChange={(e) => { const raw = e.target.value.replace(/[^0-9]/g, '').slice(0, 9); setFormData({ ...formData, ein: raw }); }} placeholder="XX-XXXXXXX" slotProps={{ htmlInput: { maxLength: 10 } }} />
        <TextField label="Years in Operation" type="number" value={formData.years_in_operation} onChange={(e) => setFormData({ ...formData, years_in_operation: e.target.value })} required error={!!errors.years_in_operation} helperText={errors.years_in_operation} slotProps={{ htmlInput: { min: 0 } }} />
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <TextField label="NPI (Individual)" value={formData.npi_individual} onChange={(e) => setFormData({ ...formData, npi_individual: e.target.value })} />
        <TextField label="NPI (Group)" value={formData.npi_group} onChange={(e) => setFormData({ ...formData, npi_group: e.target.value })} />
      </Box>
      <TextField select label="Ownership Structure" value={formData.ownership_structure} onChange={(e) => setFormData({ ...formData, ownership_structure: e.target.value })} fullWidth>
        <MenuItem value="">Select...</MenuItem>
        {ownershipOptions.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
      </TextField>
      <Box sx={{ display: 'flex', gap: 4 }}>
        <FormControlLabel control={<Switch checked={formData.prior_bankruptcy} onChange={(e) => setFormData({ ...formData, prior_bankruptcy: e.target.checked })} />} label="Prior bankruptcy?" />
        <FormControlLabel control={<Switch checked={formData.pending_litigation} onChange={(e) => setFormData({ ...formData, pending_litigation: e.target.checked })} />} label="Pending litigation?" />
      </Box>
    </Box>
  );
}

function Step2Revenue({ formData, setFormData, errors }) {
  const gross = parseFloat(String(formData.gross_production).replace(/[,$]/g, '')) || 0;
  const avgMonthly = gross > 0 ? (gross / 12).toFixed(0) : null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Revenue & Production</SectionTitle>
      <SectionSubtitle>Last 12 months of production and collections data.</SectionSubtitle>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <DollarField label="Gross Production (12mo)" value={formData.gross_production} onChange={(e) => setFormData({ ...formData, gross_production: e.target.value })} error={!!errors.gross_production} helperText={errors.gross_production} />
        <DollarField label="Net Collections (12mo)" value={formData.net_collections} onChange={(e) => setFormData({ ...formData, net_collections: e.target.value })} error={!!errors.net_collections} helperText={errors.net_collections} />
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <DollarField label="Insurance Collections" value={formData.insurance_collections} onChange={(e) => setFormData({ ...formData, insurance_collections: e.target.value })} />
        <DollarField label="Patient Collections" value={formData.patient_collections} onChange={(e) => setFormData({ ...formData, patient_collections: e.target.value })} />
      </Box>
      {avgMonthly && (
        <Box sx={{ p: 1.5, bgcolor: tokens.colors.accent[50], borderRadius: 1, border: '1px solid ' + tokens.colors.accent[200] }}>
          <Typography variant="body2" sx={{ color: tokens.colors.accent[700] }}>
            Avg. Monthly Production: <strong>${Number(avgMonthly).toLocaleString()}</strong>
          </Typography>
        </Box>
      )}
      <FormControlLabel control={<Switch checked={formData.seasonality_swings} onChange={(e) => setFormData({ ...formData, seasonality_swings: e.target.checked })} />} label="Seasonality swings > 20%?" />
    </Box>
  );
}

function Step3Payer({ formData, setFormData }) {
  const payers = formData.top_payers || [{ name: '', pct_revenue: '' }];

  const updatePayer = (idx, field, val) => {
    const updated = [...payers];
    updated[idx] = { ...updated[idx], [field]: val };
    setFormData({ ...formData, top_payers: updated });
  };
  const addPayer = () => {
    if (payers.length < 5) setFormData({ ...formData, top_payers: [...payers, { name: '', pct_revenue: '' }] });
  };
  const removePayer = (idx) => {
    const updated = payers.filter((_, i) => i !== idx);
    setFormData({ ...formData, top_payers: updated.length ? updated : [{ name: '', pct_revenue: '' }] });
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Payer & Claims Profile</SectionTitle>
      <SectionSubtitle>Payer mix, claim volume, and reimbursement speed.</SectionSubtitle>
      <Typography variant="subtitle2" sx={{ mb: -1 }}>Top Payers (up to 5)</Typography>
      {payers.map((p, idx) => (
        <Box key={idx} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField label={'Payer ' + (idx + 1)} value={p.name} onChange={(e) => updatePayer(idx, 'name', e.target.value)} sx={{ flex: 2 }} size="small" />
          <PercentField label="% Revenue" value={p.pct_revenue} onChange={(e) => updatePayer(idx, 'pct_revenue', e.target.value)} sx={{ flex: 1 }} size="small" />
          {payers.length > 1 && (
            <IconButton size="small" onClick={() => removePayer(idx)} sx={{ color: tokens.colors.text.muted }}>
              <Typography>x</Typography>
            </IconButton>
          )}
        </Box>
      ))}
      {payers.length < 5 && (
        <Button size="small" onClick={addPayer} sx={{ alignSelf: 'flex-start' }}>+ Add Payer</Button>
      )}
      <Divider sx={{ my: 1 }} />
      <Typography variant="subtitle2" sx={{ mb: -1 }}>Payer Mix (%)</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <PercentField label="PPO" value={formData.pct_ppo} onChange={(e) => setFormData({ ...formData, pct_ppo: e.target.value })} />
        <PercentField label="Medicaid" value={formData.pct_medicaid} onChange={(e) => setFormData({ ...formData, pct_medicaid: e.target.value })} />
        <PercentField label="Fee-for-Service" value={formData.pct_ffs} onChange={(e) => setFormData({ ...formData, pct_ffs: e.target.value })} />
        <PercentField label="Capitation" value={formData.pct_capitation} onChange={(e) => setFormData({ ...formData, pct_capitation: e.target.value })} />
      </Box>
      <Divider sx={{ my: 1 }} />
      <Typography variant="subtitle2" sx={{ mb: -1 }}>Claims</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <DollarField label="Avg Claim Size" value={formData.avg_claim_size} onChange={(e) => setFormData({ ...formData, avg_claim_size: e.target.value })} />
        <TextField label="Avg Monthly Claim Count" type="number" value={formData.avg_monthly_claim_count} onChange={(e) => setFormData({ ...formData, avg_monthly_claim_count: e.target.value })} slotProps={{ htmlInput: { min: 0 } }} />
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <TextField label="Avg Days to Reimbursement" type="number" value={formData.avg_days_to_reimbursement} onChange={(e) => setFormData({ ...formData, avg_days_to_reimbursement: e.target.value })} slotProps={{ htmlInput: { min: 0 } }} />
        <PercentField label="Est. Denial Rate" value={formData.estimated_denial_rate} onChange={(e) => setFormData({ ...formData, estimated_denial_rate: e.target.value })} />
      </Box>
    </Box>
  );
}

function Step4Billing({ formData, setFormData }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Billing Operations</SectionTitle>
      <SectionSubtitle>How your practice manages billing and collections.</SectionSubtitle>
      <TextField select label="Practice Management Software" value={formData.practice_management_software} onChange={(e) => setFormData({ ...formData, practice_management_software: e.target.value })} fullWidth>
        <MenuItem value="">Select...</MenuItem>
        {pmsOptions.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
      </TextField>
      <TextField select label="Billing Model" value={formData.billing_model} onChange={(e) => setFormData({ ...formData, billing_model: e.target.value })} fullWidth>
        {billingModels.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
      </TextField>
      <TextField label="Billing Staff Count" type="number" value={formData.billing_staff_count} onChange={(e) => setFormData({ ...formData, billing_staff_count: e.target.value })} fullWidth slotProps={{ htmlInput: { min: 0 } }} />
      <Box sx={{ display: 'flex', gap: 4 }}>
        <FormControlLabel control={<Switch checked={formData.dedicated_rcm_manager} onChange={(e) => setFormData({ ...formData, dedicated_rcm_manager: e.target.checked })} />} label="Dedicated RCM manager?" />
        <FormControlLabel control={<Switch checked={formData.written_billing_sop} onChange={(e) => setFormData({ ...formData, written_billing_sop: e.target.checked })} />} label="Written billing SOP?" />
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <TextField label="Average AR Days" type="number" value={formData.avg_ar_days} onChange={(e) => setFormData({ ...formData, avg_ar_days: e.target.value })} slotProps={{ htmlInput: { min: 0 } }} />
        <DollarField label="Outstanding AR Balance" value={formData.outstanding_ar_balance} onChange={(e) => setFormData({ ...formData, outstanding_ar_balance: e.target.value })} />
      </Box>
    </Box>
  );
}

function Step5Financial({ formData, setFormData }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Financial Stability</SectionTitle>
      <SectionSubtitle>Banking, cash reserves, and credit information.</SectionSubtitle>
      <TextField label="Primary Bank" value={formData.primary_bank} onChange={(e) => setFormData({ ...formData, primary_bank: e.target.value })} fullWidth />
      <TextField select label="Average Operating Cash on Hand" value={formData.cash_on_hand_range} onChange={(e) => setFormData({ ...formData, cash_on_hand_range: e.target.value })} fullWidth>
        <MenuItem value="">Select...</MenuItem>
        {cashRangeOptions.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
      </TextField>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <DollarField label="Existing Line of Credit" value={formData.existing_loc} onChange={(e) => setFormData({ ...formData, existing_loc: e.target.value })} />
        <DollarField label="Monthly Debt Payments" value={formData.monthly_debt_payments} onChange={(e) => setFormData({ ...formData, monthly_debt_payments: e.target.value })} />
      </Box>
      <FormControlLabel control={<Switch checked={formData.missed_loan_payments_24m} onChange={(e) => setFormData({ ...formData, missed_loan_payments_24m: e.target.checked })} />} label="Missed loan payments in last 24 months?" />
    </Box>
  );
}

function Step6Fit({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <SectionTitle>Spoonbill Fit</SectionTitle>
      <SectionSubtitle>Tell us about your funding needs and contact information.</SectionSubtitle>
      <Box sx={{ p: 1.5, bgcolor: tokens.colors.accent[50], borderRadius: 1, border: '1px solid ' + tokens.colors.accent[200] }}>
        <Typography variant="body2" sx={{ color: tokens.colors.accent[700], fontWeight: 500 }}>All claims are funded same day.</Typography>
      </Box>
      <DollarField label="Expected Monthly Funding Volume" value={formData.expected_monthly_funding} onChange={(e) => setFormData({ ...formData, expected_monthly_funding: e.target.value })} />
      <Box>
        <Typography variant="body2" sx={{ mb: 1, fontWeight: 500 }}>Urgency (1 = Low, 5 = Critical)</Typography>
        <Slider value={formData.urgency_scale} onChange={(_, v) => setFormData({ ...formData, urgency_scale: v })} min={1} max={5} step={1} marks={[{ value: 1, label: '1' }, { value: 2, label: '2' }, { value: 3, label: '3' }, { value: 4, label: '4' }, { value: 5, label: '5' }]} sx={{ color: tokens.colors.accent[600] }} />
      </Box>
      <FormControlLabel control={<Switch checked={formData.willing_to_integrate_api} onChange={(e) => setFormData({ ...formData, willing_to_integrate_api: e.target.checked })} />} label="Willing to integrate via API?" />
      <TextField label="Why Spoonbill?" value={formData.why_spoonbill} onChange={(e) => setFormData({ ...formData, why_spoonbill: e.target.value })} fullWidth multiline rows={3} placeholder="What drew you to Spoonbill? What problem are you trying to solve?" />
      <Divider sx={{ my: 1 }} />
      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>Contact Information</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1, mt: -1 }}>This person will receive login credentials upon approval.</Typography>
      <TextField label="Contact Name" value={formData.contact_name} onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })} required fullWidth error={!!errors.contact_name} helperText={errors.contact_name} />
      <TextField label="Contact Email" type="email" value={formData.contact_email} onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })} required fullWidth error={!!errors.contact_email} helperText={errors.contact_email} />
      <TextField label="Contact Phone (optional)" value={formData.contact_phone} onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })} fullWidth />
    </Box>
  );
}

function ReviewScreen({ formData }) {
  const dash = '\u2014';
  const fmt = (v) => v || dash;
  const fmtDollar = (v) => v ? '$' + Number(v).toLocaleString() : dash;
  const fmtPct = (v) => v ? v + '%' : dash;
  const fmtYN = (v) => v ? 'Yes' : 'No';

  const sections = [
    {
      title: 'Identity & Compliance',
      items: [
        ['Legal Name', formData.legal_name],
        ['DBA', fmt(formData.dba)],
        ['EIN', fmt(formData.ein)],
        ['Years in Operation', formData.years_in_operation],
        ['NPI (Individual)', fmt(formData.npi_individual)],
        ['NPI (Group)', fmt(formData.npi_group)],
        ['Ownership', ownershipOptions.find(o => o.value === formData.ownership_structure)?.label || dash],
        ['Prior Bankruptcy', fmtYN(formData.prior_bankruptcy)],
        ['Pending Litigation', fmtYN(formData.pending_litigation)],
      ],
    },
    {
      title: 'Revenue & Production',
      items: [
        ['Gross Production (12mo)', fmtDollar(formData.gross_production)],
        ['Net Collections (12mo)', fmtDollar(formData.net_collections)],
        ['Insurance Collections', fmtDollar(formData.insurance_collections)],
        ['Patient Collections', fmtDollar(formData.patient_collections)],
        ['Seasonality Swings > 20%', fmtYN(formData.seasonality_swings)],
      ],
    },
    {
      title: 'Payer & Claims',
      items: [
        ['Top Payers', (formData.top_payers || []).filter(p => p.name).map(p => p.name + ' (' + p.pct_revenue + '%)').join(', ') || dash],
        ['PPO %', fmtPct(formData.pct_ppo)],
        ['Medicaid %', fmtPct(formData.pct_medicaid)],
        ['FFS %', fmtPct(formData.pct_ffs)],
        ['Capitation %', fmtPct(formData.pct_capitation)],
        ['Avg Claim Size', fmtDollar(formData.avg_claim_size)],
        ['Monthly Claim Count', fmt(formData.avg_monthly_claim_count)],
        ['Days to Reimbursement', fmt(formData.avg_days_to_reimbursement)],
        ['Est. Denial Rate', fmtPct(formData.estimated_denial_rate)],
      ],
    },
    {
      title: 'Billing Operations',
      items: [
        ['PMS', fmt(formData.practice_management_software)],
        ['Billing Model', billingModels.find(b => b.value === formData.billing_model)?.label || dash],
        ['Billing Staff', fmt(formData.billing_staff_count)],
        ['RCM Manager', fmtYN(formData.dedicated_rcm_manager)],
        ['Written SOP', fmtYN(formData.written_billing_sop)],
        ['Avg AR Days', fmt(formData.avg_ar_days)],
        ['Outstanding AR', fmtDollar(formData.outstanding_ar_balance)],
      ],
    },
    {
      title: 'Financial Stability',
      items: [
        ['Primary Bank', fmt(formData.primary_bank)],
        ['Cash on Hand', cashRangeOptions.find(c => c.value === formData.cash_on_hand_range)?.label || dash],
        ['Existing LOC', fmtDollar(formData.existing_loc)],
        ['Monthly Debt', fmtDollar(formData.monthly_debt_payments)],
        ['Missed Payments (24m)', fmtYN(formData.missed_loan_payments_24m)],
      ],
    },
    {
      title: 'Spoonbill Fit & Contact',
      items: [
        ['Expected Monthly Volume', fmtDollar(formData.expected_monthly_funding)],
        ['Urgency', formData.urgency_scale + ' / 5'],
        ['API Integration', fmtYN(formData.willing_to_integrate_api)],
        ['Why Spoonbill', fmt(formData.why_spoonbill)],
        ['Contact Name', formData.contact_name],
        ['Contact Email', formData.contact_email],
        ['Contact Phone', fmt(formData.contact_phone)],
      ],
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <SectionTitle>Review Your Application</SectionTitle>
      <SectionSubtitle>Please review all information before submitting.</SectionSubtitle>
      {sections.map((section) => (
        <Paper key={section.title} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: tokens.colors.accent[700], mb: 1 }}>{section.title}</Typography>
          {section.items.map(([label, value]) => (
            <Box key={label} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.4 }}>
              <Typography variant="body2" color="text.secondary">{label}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 500, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-word' }}>{value}</Typography>
            </Box>
          ))}
        </Paper>
      ))}
    </Box>
  );
}

function SuccessScreen({ applicationId, email }) {
  return (
    <Box sx={{ textAlign: 'center', py: 6 }}>
      <Box sx={{ width: 64, height: 64, borderRadius: '50%', bgcolor: tokens.colors.status.successBg, border: '2px solid ' + tokens.colors.status.successBorder, display: 'flex', alignItems: 'center', justifyContent: 'center', mx: 'auto', mb: 3 }}>
        <Typography sx={{ fontSize: 28, color: tokens.colors.status.success }}>{'\u2713'}</Typography>
      </Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>Application Submitted</Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Thank you for applying to Spoonbill.
      </Typography>
      <Box sx={{ display: 'inline-block', bgcolor: tokens.colors.accent[50], border: '1px solid ' + tokens.colors.accent[200], borderRadius: 2, px: 3, py: 1.5, my: 2 }}>
        <Typography variant="caption" color="text.secondary">Application ID</Typography>
        <Typography variant="h5" sx={{ fontWeight: 700, color: tokens.colors.accent[600] }}>
          #{applicationId}
        </Typography>
      </Box>
      <Typography variant="body1" paragraph sx={{ mt: 2 }}>
        Our team will review your application and contact you at <strong>{email}</strong> within 2-3 business days.
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Your underwriting score is being computed automatically and will be available to our review team.
      </Typography>
    </Box>
  );
}

function SetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const validateToken = async () => {
      try {
        const response = await fetch(API_BASE + '/invite/' + token);
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Invalid invite link');
        }
        const data = await response.json();
        setEmail(data.email);
        setValidating(false);
      } catch (err) {
        setError(err.message);
        setValidating(false);
      } finally {
        setLoading(false);
      }
    };
    validateToken();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    setSubmitting(true);
    try {
      const response = await fetch(API_BASE + '/set-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to set password');
      }
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <CircularProgress />
            <Typography sx={{ mt: 2 }}>Validating invite link...</Typography>
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  if (validating && error) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Paper sx={{ p: 4 }}>
            <Typography variant="h5" gutterBottom color="error">Invalid Invite Link</Typography>
            <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
            <Typography variant="body2" color="text.secondary">Please contact support if you need assistance.</Typography>
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  if (success) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm" sx={{ py: 8 }}>
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h5" gutterBottom>Password Set Successfully</Typography>
            <Typography variant="body1" paragraph>You can now log in to the Practice Portal.</Typography>
            <Button variant="contained" size="large" href={PRACTICE_PORTAL_URL}>Go to Practice Portal</Button>
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="sm" sx={{ py: 8 }}>
        <Paper sx={{ p: 4 }}>
          <Typography variant="h5" gutterBottom>Set Your Password</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>Welcome! Set your password for <strong>{email}</strong></Typography>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField label="New Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required fullWidth />
            <TextField label="Confirm Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required fullWidth />
            <Button type="submit" variant="contained" size="large" disabled={submitting} fullWidth>
              {submitting ? 'Setting Password...' : 'Set Password'}
            </Button>
          </Box>
        </Paper>
      </Container>
    </ThemeProvider>
  );
}

function ApplicationForm() {
  const [activeStep, setActiveStep] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved).activeStep || 0;
    } catch (e) { return 0; }
    return 0;
  });
  const [formData, setFormData] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return { ...initialFormData, ...parsed.formData };
      }
    } catch (e) { return { ...initialFormData }; }
    return { ...initialFormData };
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [applicationId, setApplicationId] = useState(null);
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    if (!submitted) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ formData, activeStep }));
      } catch (e) { /* noop */ }
    }
  }, [formData, activeStep, submitted]);

  const validateStep = (step) => {
    const e = {};
    if (step === 0) {
      if (!formData.legal_name.trim()) e.legal_name = 'Required';
      if (!formData.years_in_operation && formData.years_in_operation !== 0) e.years_in_operation = 'Required';
    } else if (step === 1) {
      if (!formData.gross_production) e.gross_production = 'Required';
      if (!formData.net_collections) e.net_collections = 'Required';
    } else if (step === 5) {
      if (!formData.contact_name.trim()) e.contact_name = 'Required';
      if (!formData.contact_email.trim()) e.contact_email = 'Required';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.contact_email)) e.contact_email = 'Invalid email';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = () => {
    if (validateStep(activeStep)) {
      if (activeStep === steps.length - 1) {
        setShowReview(true);
      } else {
        setActiveStep((p) => p + 1);
      }
    }
  };

  const handleBack = () => {
    if (showReview) {
      setShowReview(false);
    } else {
      setActiveStep((p) => p - 1);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payersFiltered = (formData.top_payers || []).filter(p => p.name.trim());
      const payload = {
        legal_name: formData.legal_name,
        dba: formData.dba || null,
        ein: formData.ein || null,
        npi_individual: formData.npi_individual || null,
        npi_group: formData.npi_group || null,
        years_in_operation: parseInt(formData.years_in_operation, 10),
        ownership_structure: formData.ownership_structure || null,
        prior_bankruptcy: formData.prior_bankruptcy,
        pending_litigation: formData.pending_litigation,
        gross_production_cents: dollarsToCents(formData.gross_production),
        net_collections_cents: dollarsToCents(formData.net_collections),
        insurance_collections_cents: dollarsToCents(formData.insurance_collections),
        patient_collections_cents: dollarsToCents(formData.patient_collections),
        seasonality_swings: formData.seasonality_swings,
        top_payers_json: payersFiltered.length ? JSON.stringify(payersFiltered.map(p => ({ name: p.name, pct_revenue: parseFloat(p.pct_revenue) || 0 }))) : null,
        pct_ppo: formData.pct_ppo ? parseFloat(formData.pct_ppo) : null,
        pct_medicaid: formData.pct_medicaid ? parseFloat(formData.pct_medicaid) : null,
        pct_ffs: formData.pct_ffs ? parseFloat(formData.pct_ffs) : null,
        pct_capitation: formData.pct_capitation ? parseFloat(formData.pct_capitation) : null,
        avg_claim_size_cents: dollarsToCents(formData.avg_claim_size),
        avg_monthly_claim_count: formData.avg_monthly_claim_count ? parseInt(formData.avg_monthly_claim_count, 10) : null,
        avg_days_to_reimbursement: formData.avg_days_to_reimbursement ? parseInt(formData.avg_days_to_reimbursement, 10) : null,
        estimated_denial_rate: formData.estimated_denial_rate ? parseFloat(formData.estimated_denial_rate) : null,
        practice_management_software: formData.practice_management_software || null,
        billing_model: formData.billing_model,
        billing_staff_count: formData.billing_staff_count ? parseInt(formData.billing_staff_count, 10) : null,
        dedicated_rcm_manager: formData.dedicated_rcm_manager,
        written_billing_sop: formData.written_billing_sop,
        avg_ar_days: formData.avg_ar_days ? parseInt(formData.avg_ar_days, 10) : null,
        outstanding_ar_balance_cents: dollarsToCents(formData.outstanding_ar_balance),
        primary_bank: formData.primary_bank || null,
        cash_on_hand_range: formData.cash_on_hand_range || null,
        existing_loc_cents: dollarsToCents(formData.existing_loc),
        monthly_debt_payments_cents: dollarsToCents(formData.monthly_debt_payments),
        missed_loan_payments_24m: formData.missed_loan_payments_24m,
        desired_funding_cadence: null,
        expected_monthly_funding_cents: dollarsToCents(formData.expected_monthly_funding),
        urgency_scale: formData.urgency_scale,
        willing_to_integrate_api: formData.willing_to_integrate_api,
        why_spoonbill: formData.why_spoonbill || null,
        contact_name: formData.contact_name,
        contact_email: formData.contact_email,
        contact_phone: formData.contact_phone || null,
      };

      const response = await fetch(API_BASE + '/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit application');
      }
      const data = await response.json();
      setApplicationId(data.id);
      setSubmitted(true);
      try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* noop */ }
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const getStepContent = (step) => {
    switch (step) {
      case 0: return <Step1Identity formData={formData} setFormData={setFormData} errors={errors} />;
      case 1: return <Step2Revenue formData={formData} setFormData={setFormData} errors={errors} />;
      case 2: return <Step3Payer formData={formData} setFormData={setFormData} />;
      case 3: return <Step4Billing formData={formData} setFormData={setFormData} />;
      case 4: return <Step5Financial formData={formData} setFormData={setFormData} />;
      case 5: return <Step6Fit formData={formData} setFormData={setFormData} errors={errors} />;
      default: return null;
    }
  };

  if (submitted) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
          <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: '1px solid ' + tokens.colors.border.light, py: 2, px: 3, mb: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.text.primary, letterSpacing: '-0.01em' }}>Spoonbill</Typography>
          </Box>
          <Container maxWidth="sm" sx={{ py: 4 }}>
            <Paper sx={{ p: 5, borderRadius: 3 }}>
              <SuccessScreen applicationId={applicationId} email={formData.contact_email} />
            </Paper>
          </Container>
        </Box>
      </ThemeProvider>
    );
  }

  const progress = showReview ? 100 : ((activeStep / steps.length) * 100);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: tokens.colors.background }}>
        <Box sx={{ bgcolor: tokens.colors.surface, borderBottom: '1px solid ' + tokens.colors.border.light, py: 2, px: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: tokens.colors.text.primary, letterSpacing: '-0.01em' }}>Spoonbill</Typography>
        </Box>
        <LinearProgress variant="determinate" value={progress} sx={{ height: 3, bgcolor: tokens.colors.border.light, '& .MuiLinearProgress-bar': { bgcolor: tokens.colors.accent[600] } }} />

        <Container maxWidth="sm" sx={{ py: 3 }}>
          <Paper sx={{ p: { xs: 3, sm: 4 }, borderRadius: 3 }}>
            <Typography variant="h4" align="center" sx={{ fontWeight: 700, mb: 0.5 }}>
              Apply for Spoonbill
            </Typography>
            <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 3 }}>
              Structured underwriting for dental claims financing.
            </Typography>

            {!showReview && (
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                  {steps.map((label, i) => (
                    <Box key={label} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, cursor: i < activeStep ? 'pointer' : 'default' }} onClick={() => { if (i < activeStep) setActiveStep(i); }}>
                      <Box sx={{
                        width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 600,
                        bgcolor: i < activeStep ? tokens.colors.status.success : i === activeStep ? tokens.colors.accent[600] : tokens.colors.surfaceHover,
                        color: i <= activeStep ? '#fff' : tokens.colors.text.muted,
                        border: i === activeStep ? ('2px solid ' + tokens.colors.accent[700]) : i < activeStep ? ('2px solid ' + tokens.colors.status.success) : ('2px solid ' + tokens.colors.border.light),
                        transition: 'all 0.2s',
                      }}>
                        {i < activeStep ? '\u2713' : i + 1}
                      </Box>
                      <Typography variant="caption" sx={{ mt: 0.5, fontSize: '0.6rem', color: i === activeStep ? tokens.colors.accent[600] : tokens.colors.text.muted, fontWeight: i === activeStep ? 600 : 400, textAlign: 'center', lineHeight: 1.2, maxWidth: 60 }}>
                        {label}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {submitError && <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>}

            {showReview ? <ReviewScreen formData={formData} /> : getStepContent(activeStep)}

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 3, borderTop: '1px solid ' + tokens.colors.border.light }}>
              <Button disabled={activeStep === 0 && !showReview} onClick={handleBack} variant="outlined" size="large">
                Back
              </Button>
              {showReview ? (
                <Button variant="contained" onClick={handleSubmit} disabled={submitting} size="large" startIcon={submitting ? <CircularProgress size={20} /> : null}>
                  {submitting ? 'Submitting...' : 'Submit Application'}
                </Button>
              ) : (
                <Button variant="contained" onClick={handleNext} size="large">
                  {activeStep === steps.length - 1 ? 'Review' : 'Continue'}
                </Button>
              )}
            </Box>
          </Paper>

          <Typography variant="caption" align="center" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            Progress is saved automatically. No PHI is collected.
          </Typography>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ApplicationForm />} />
        <Route path="/set-password/:token" element={<SetPasswordPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
