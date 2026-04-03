import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Link,
} from '@mui/material';
import { useAuth } from '../context/AuthContext';

/**
 * Login page with username/password authentication.
 */
function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [form, setForm] = useState({
    username: '',
    password: '',
  });
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: '' }));
    setSubmitError('');
  };

  const validateForm = () => {
    const newErrors = {};

    if (!form.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (form.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    }

    if (!form.password) {
      newErrors.password = 'Password is required';
    } else if (form.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    return newErrors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setSubmitError('');

    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      await login(form.username, form.password);
      navigate('/dashboard');
    } catch (error) {
      setSubmitError(
        error.response?.data?.detail || 'Login failed. Please check your credentials.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8 }}>
        <Paper elevation={3}>
          <Box sx={{ p: 4 }}>
            <Typography variant="h4" align="center" gutterBottom>
              Welcome Back
            </Typography>
            <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 4 }}>
              Sign in to manage your audio processing pipelines
            </Typography>

            {submitError && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSubmitError('')}>
                {submitError}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Username"
                name="username"
                value={form.username}
                onChange={handleChange}
                error={!!errors.username}
                helperText={errors.username}
                autoComplete="username"
                autoFocus
                sx={{ mb: 3 }}
              />

              <TextField
                fullWidth
                label="Password"
                name="password"
                type="password"
                value={form.password}
                onChange={handleChange}
                error={!!errors.password}
                helperText={errors.password}
                autoComplete="current-password"
                sx={{ mb: 4 }}
              />

              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                disabled={isSubmitting}
                sx={{ mb: 2 }}
              >
                {isSubmitting ? 'Signing in...' : 'Sign In'}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2">
                  Don't have an account?{' '}
                  <Link
                    component="button"
                    type="button"
                    onClick={() => navigate('/register')}
                    underline="hover"
                  >
                    Register
                  </Link>
                </Typography>
              </Box>
            </form>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
}

export default LoginPage;