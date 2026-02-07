import { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#000000' },
    secondary: { main: '#666666' },
    background: { default: '#ffffff', paper: '#f5f5f5' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

const API_BASE = 'http://localhost:8000';

const steps = ['Practice Info', 'Operations', 'Financial', 'Billing', 'Contact'];

const practiceTypes = [
  { value: 'GENERAL_DENTISTRY', label: 'General Dentistry' },
  { value: 'PEDIATRIC_DENTISTRY', label: 'Pediatric Dentistry' },
  { value: 'ORTHODONTICS', label: 'Orthodontics' },
  { value: 'PERIODONTICS', label: 'Periodontics' },
  { value: 'ENDODONTICS', label: 'Endodontics' },
  { value: 'ORAL_SURGERY', label: 'Oral Surgery' },
  { value: 'PROSTHODONTICS', label: 'Prosthodontics' },
  { value: 'MULTI_SPECIALTY', label: 'Multi-Specialty' },
  { value: 'OTHER', label: 'Other' },
];

const billingModels = [
  { value: 'IN_HOUSE', label: 'In-House' },
  { value: 'OUTSOURCED', label: 'Outsourced' },
  { value: 'HYBRID', label: 'Hybrid' },
];

const urgencyLevels = [
  { value: 'LOW', label: 'Low - No rush' },
  { value: 'MEDIUM', label: 'Medium - Within 30 days' },
  { value: 'HIGH', label: 'High - Within 2 weeks' },
  { value: 'CRITICAL', label: 'Critical - ASAP' },
];

const collectionsRanges = [
  { value: 'Under $50,000', label: 'Under $50,000' },
  { value: '$50,000 - $100,000', label: '$50,000 - $100,000' },
  { value: '$100,000 - $250,000', label: '$100,000 - $250,000' },
  { value: '$250,000 - $500,000', label: '$250,000 - $500,000' },
  { value: '$500,000 - $1,000,000', label: '$500,000 - $1,000,000' },
  { value: 'Over $1,000,000', label: 'Over $1,000,000' },
];

const insuranceMixOptions = [
  { value: '100% Insurance', label: '100% Insurance' },
  { value: '75% Insurance / 25% Self-Pay', label: '75% Insurance / 25% Self-Pay' },
  { value: '50% Insurance / 50% Self-Pay', label: '50% Insurance / 50% Self-Pay' },
  { value: '25% Insurance / 75% Self-Pay', label: '25% Insurance / 75% Self-Pay' },
  { value: '100% Self-Pay', label: '100% Self-Pay' },
];

const initialFormData = {
  legal_name: '',
  address: '',
  phone: '',
  website: '',
  tax_id: '',
  practice_type: 'GENERAL_DENTISTRY',
  years_in_operation: '',
  provider_count: '',
  operatory_count: '',
  avg_monthly_collections_range: '',
  insurance_vs_self_pay_mix: '',
  top_payers: '',
  avg_ar_days: '',
  billing_model: 'IN_HOUSE',
  follow_up_frequency: '',
  practice_management_software: '',
  claims_per_month: '',
  electronic_claims: true,
  stated_goal: '',
  urgency_level: 'MEDIUM',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
};

function PracticeInfoStep({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>Practice Information</Typography>
      <TextField
        label="Legal Practice Name"
        value={formData.legal_name}
        onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })}
        required
        fullWidth
        error={!!errors.legal_name}
        helperText={errors.legal_name}
      />
      <TextField
        label="Address"
        value={formData.address}
        onChange={(e) => setFormData({ ...formData, address: e.target.value })}
        required
        fullWidth
        multiline
        rows={2}
        error={!!errors.address}
        helperText={errors.address}
      />
      <TextField
        label="Phone"
        value={formData.phone}
        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
        required
        fullWidth
        error={!!errors.phone}
        helperText={errors.phone}
      />
      <TextField
        label="Website (optional)"
        value={formData.website}
        onChange={(e) => setFormData({ ...formData, website: e.target.value })}
        fullWidth
      />
      <TextField
        label="Tax ID (optional)"
        value={formData.tax_id}
        onChange={(e) => setFormData({ ...formData, tax_id: e.target.value })}
        fullWidth
      />
      <TextField
        select
        label="Practice Type"
        value={formData.practice_type}
        onChange={(e) => setFormData({ ...formData, practice_type: e.target.value })}
        required
        fullWidth
      >
        {practiceTypes.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
    </Box>
  );
}

function OperationsStep({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>Practice Operations</Typography>
      <TextField
        label="Years in Operation"
        type="number"
        value={formData.years_in_operation}
        onChange={(e) => setFormData({ ...formData, years_in_operation: e.target.value })}
        required
        fullWidth
        inputProps={{ min: 0 }}
        error={!!errors.years_in_operation}
        helperText={errors.years_in_operation}
      />
      <TextField
        label="Number of Providers"
        type="number"
        value={formData.provider_count}
        onChange={(e) => setFormData({ ...formData, provider_count: e.target.value })}
        required
        fullWidth
        inputProps={{ min: 1 }}
        error={!!errors.provider_count}
        helperText={errors.provider_count}
      />
      <TextField
        label="Number of Operatories"
        type="number"
        value={formData.operatory_count}
        onChange={(e) => setFormData({ ...formData, operatory_count: e.target.value })}
        required
        fullWidth
        inputProps={{ min: 1 }}
        error={!!errors.operatory_count}
        helperText={errors.operatory_count}
      />
    </Box>
  );
}

function FinancialStep({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>Financial Information</Typography>
      <TextField
        select
        label="Average Monthly Collections"
        value={formData.avg_monthly_collections_range}
        onChange={(e) => setFormData({ ...formData, avg_monthly_collections_range: e.target.value })}
        required
        fullWidth
        error={!!errors.avg_monthly_collections_range}
        helperText={errors.avg_monthly_collections_range}
      >
        {collectionsRanges.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        label="Insurance vs Self-Pay Mix"
        value={formData.insurance_vs_self_pay_mix}
        onChange={(e) => setFormData({ ...formData, insurance_vs_self_pay_mix: e.target.value })}
        required
        fullWidth
        error={!!errors.insurance_vs_self_pay_mix}
        helperText={errors.insurance_vs_self_pay_mix}
      >
        {insuranceMixOptions.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        label="Top Payers (e.g., Delta Dental, Cigna, Aetna)"
        value={formData.top_payers}
        onChange={(e) => setFormData({ ...formData, top_payers: e.target.value })}
        fullWidth
        multiline
        rows={2}
      />
      <TextField
        label="Average AR Days (optional)"
        type="number"
        value={formData.avg_ar_days}
        onChange={(e) => setFormData({ ...formData, avg_ar_days: e.target.value })}
        fullWidth
        inputProps={{ min: 0 }}
      />
    </Box>
  );
}

function BillingStep({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>Billing Operations</Typography>
      <TextField
        select
        label="Billing Model"
        value={formData.billing_model}
        onChange={(e) => setFormData({ ...formData, billing_model: e.target.value })}
        required
        fullWidth
      >
        {billingModels.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        label="Follow-up Frequency (e.g., Weekly, Bi-weekly)"
        value={formData.follow_up_frequency}
        onChange={(e) => setFormData({ ...formData, follow_up_frequency: e.target.value })}
        fullWidth
      />
      <TextField
        label="Practice Management Software"
        value={formData.practice_management_software}
        onChange={(e) => setFormData({ ...formData, practice_management_software: e.target.value })}
        fullWidth
        placeholder="e.g., Dentrix, Eaglesoft, Open Dental"
      />
      <TextField
        label="Claims per Month (optional)"
        type="number"
        value={formData.claims_per_month}
        onChange={(e) => setFormData({ ...formData, claims_per_month: e.target.value })}
        fullWidth
        inputProps={{ min: 0 }}
      />
      <FormControlLabel
        control={
          <Checkbox
            checked={formData.electronic_claims}
            onChange={(e) => setFormData({ ...formData, electronic_claims: e.target.checked })}
          />
        }
        label="We submit claims electronically"
      />
      <TextField
        label="What is your primary goal with Spoonbill?"
        value={formData.stated_goal}
        onChange={(e) => setFormData({ ...formData, stated_goal: e.target.value })}
        fullWidth
        multiline
        rows={3}
        placeholder="e.g., Improve cash flow, reduce AR days, accelerate collections..."
      />
      <TextField
        select
        label="Urgency Level"
        value={formData.urgency_level}
        onChange={(e) => setFormData({ ...formData, urgency_level: e.target.value })}
        required
        fullWidth
      >
        {urgencyLevels.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
    </Box>
  );
}

function ContactStep({ formData, setFormData, errors }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="h6" gutterBottom>Contact Information</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        This person will be the primary Practice Manager and receive login credentials upon approval.
      </Typography>
      <TextField
        label="Contact Name"
        value={formData.contact_name}
        onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })}
        required
        fullWidth
        error={!!errors.contact_name}
        helperText={errors.contact_name}
      />
      <TextField
        label="Contact Email"
        type="email"
        value={formData.contact_email}
        onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
        required
        fullWidth
        error={!!errors.contact_email}
        helperText={errors.contact_email}
      />
      <TextField
        label="Contact Phone (optional)"
        value={formData.contact_phone}
        onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
        fullWidth
      />
    </Box>
  );
}

function SuccessScreen({ applicationId, email }) {
  return (
    <Box sx={{ textAlign: 'center', py: 4 }}>
      <Typography variant="h4" gutterBottom>Application Submitted</Typography>
      <Typography variant="body1" paragraph>
        Thank you for applying to Spoonbill. Your application ID is:
      </Typography>
      <Typography variant="h5" sx={{ fontWeight: 'bold', my: 2 }}>
        #{applicationId}
      </Typography>
      <Typography variant="body1" paragraph>
        Our team will review your application and contact you at <strong>{email}</strong> within 2-3 business days.
      </Typography>
      <Typography variant="body2" color="text.secondary">
        You can check your application status at any time using your application ID and email.
      </Typography>
    </Box>
  );
}

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState(initialFormData);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [applicationId, setApplicationId] = useState(null);

  const validateStep = (step) => {
    const newErrors = {};
    
    if (step === 0) {
      if (!formData.legal_name.trim()) newErrors.legal_name = 'Required';
      if (!formData.address.trim()) newErrors.address = 'Required';
      if (!formData.phone.trim()) newErrors.phone = 'Required';
    } else if (step === 1) {
      if (!formData.years_in_operation) newErrors.years_in_operation = 'Required';
      if (!formData.provider_count) newErrors.provider_count = 'Required';
      if (!formData.operatory_count) newErrors.operatory_count = 'Required';
    } else if (step === 2) {
      if (!formData.avg_monthly_collections_range) newErrors.avg_monthly_collections_range = 'Required';
      if (!formData.insurance_vs_self_pay_mix) newErrors.insurance_vs_self_pay_mix = 'Required';
    } else if (step === 4) {
      if (!formData.contact_name.trim()) newErrors.contact_name = 'Required';
      if (!formData.contact_email.trim()) newErrors.contact_email = 'Required';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.contact_email)) {
        newErrors.contact_email = 'Invalid email format';
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(activeStep)) {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleSubmit = async () => {
    if (!validateStep(activeStep)) return;
    
    setSubmitting(true);
    setSubmitError(null);
    
    try {
      const payload = {
        ...formData,
        years_in_operation: parseInt(formData.years_in_operation, 10),
        provider_count: parseInt(formData.provider_count, 10),
        operatory_count: parseInt(formData.operatory_count, 10),
        avg_ar_days: formData.avg_ar_days ? parseInt(formData.avg_ar_days, 10) : null,
        claims_per_month: formData.claims_per_month ? parseInt(formData.claims_per_month, 10) : null,
      };
      
      const response = await fetch(`${API_BASE}/apply`, {
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
    } catch (error) {
      setSubmitError(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const getStepContent = (step) => {
    switch (step) {
      case 0:
        return <PracticeInfoStep formData={formData} setFormData={setFormData} errors={errors} />;
      case 1:
        return <OperationsStep formData={formData} setFormData={setFormData} errors={errors} />;
      case 2:
        return <FinancialStep formData={formData} setFormData={setFormData} errors={errors} />;
      case 3:
        return <BillingStep formData={formData} setFormData={setFormData} errors={errors} />;
      case 4:
        return <ContactStep formData={formData} setFormData={setFormData} errors={errors} />;
      default:
        return null;
    }
  };

  if (submitted) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="md" sx={{ py: 4 }}>
          <Paper sx={{ p: 4 }}>
            <SuccessScreen applicationId={applicationId} email={formData.contact_email} />
          </Paper>
        </Container>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Paper sx={{ p: 4 }}>
          <Typography variant="h4" align="center" gutterBottom>
            Apply for Spoonbill
          </Typography>
          <Typography variant="body1" align="center" color="text.secondary" sx={{ mb: 4 }}>
            Complete this form to apply for Spoonbill dental claims financing.
            Our team will review your application and contact you within 2-3 business days.
          </Typography>
          
          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          
          {submitError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {submitError}
            </Alert>
          )}
          
          {getStepContent(activeStep)}
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
            <Button
              disabled={activeStep === 0}
              onClick={handleBack}
              variant="outlined"
            >
              Back
            </Button>
            {activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={submitting}
                startIcon={submitting ? <CircularProgress size={20} /> : null}
              >
                {submitting ? 'Submitting...' : 'Submit Application'}
              </Button>
            ) : (
              <Button variant="contained" onClick={handleNext}>
                Next
              </Button>
            )}
          </Box>
        </Paper>
      </Container>
    </ThemeProvider>
  );
}

export default App;
