import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';

import { validateInviteToken, setPassword } from '../api';

export default function SetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [practiceName, setPracticeName] = useState('');
  const [error, setError] = useState(null);
  const [tokenValid, setTokenValid] = useState(false);

  const [password, setPasswordValue] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    const validate = async () => {
      try {
        const data = await validateInviteToken(token);
        setEmail(data.email);
        setPracticeName(data.practice_name);
        setTokenValid(true);
      } catch (err) {
        setError(err.message);
        setTokenValid(false);
      } finally {
        setLoading(false);
      }
    };
    validate();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);

    if (password.length < 8) {
      setFormError('Password must be at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await setPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ mt: 8, textAlign: 'center' }}>
          <CircularProgress />
          <Typography sx={{ mt: 2 }}>Validating invite link...</Typography>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ mt: 8 }}>
          <Typography variant="h4" component="h1" gutterBottom align="center" sx={{ fontWeight: 600 }}>
            Spoonbill Practice Portal
          </Typography>
          <Paper sx={{ p: 4, mt: 3 }}>
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              If you believe this is a mistake, please contact your Spoonbill representative to request a new invite link.
            </Typography>
          </Paper>
        </Box>
      </Container>
    );
  }

  if (success) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ mt: 8 }}>
          <Typography variant="h4" component="h1" gutterBottom align="center" sx={{ fontWeight: 600 }}>
            Spoonbill Practice Portal
          </Typography>
          <Paper sx={{ p: 4, mt: 3 }}>
            <Alert severity="success" sx={{ mb: 2 }}>
              Password set successfully! You can now log in.
            </Alert>
            <Button
              fullWidth
              variant="contained"
              onClick={() => navigate('/')}
              sx={{ mt: 2 }}
            >
              Go to Login
            </Button>
          </Paper>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center" sx={{ fontWeight: 600 }}>
          Spoonbill Practice Portal
        </Typography>
        <Paper sx={{ p: 4, mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Set Your Password
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Welcome to <strong>{practiceName}</strong>!
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Set a password for <strong>{email}</strong> to access the Practice Portal.
          </Typography>

          {formError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="New Password"
              type="password"
              value={password}
              onChange={(e) => setPasswordValue(e.target.value)}
              required
              sx={{ mb: 2 }}
              inputProps={{ minLength: 8 }}
              helperText="Minimum 8 characters"
            />
            <TextField
              fullWidth
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              sx={{ mb: 3 }}
            />
            <Button
              fullWidth
              type="submit"
              variant="contained"
              disabled={submitting}
              size="large"
            >
              {submitting ? 'Setting Password...' : 'Set Password'}
            </Button>
          </form>
        </Paper>
      </Box>
    </Container>
  );
}
