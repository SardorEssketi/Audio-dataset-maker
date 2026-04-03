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
 * Registration page with username, email, and password.
 */
function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: '' }));
    setSubmitError('');

    // Validate field on change
    validateField(name, value);
  };

  const validateField = (name, value) => {
    setErrors((prev) => {
      const newErrors = { ...prev };

      if (name === 'username') {
        if (!value.trim()) {
          newErrors.username = 'Username is required';
        } else if (value.length < 3) {
          newErrors.username = 'Username must be at least 3 characters';
        } else if (value.length > 50) {
          newErrors.username = 'Username must be less than 50 characters';
        } else if (!/^[a-zA-Z0-9_-]+$/.test(value)) {
          newErrors.username = 'Username can only contain letters, numbers, underscores, and hyphens';
        } else {
          delete newErrors.username;
        }
      }

      if (name === 'email' && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        newErrors.email = 'Invalid email address';
      } else if (name === 'email' && !value) {
        delete newErrors.email;
      }

      if (name === 'password') {
        if (!value) {
          newErrors.password = 'Password is required';
        } else if (value.length < 6) {
          newErrors.password = 'Password must be at least 6 characters';
        } else {
          delete newErrors.password;
        }
        // Also check confirmation if confirmPassword has a value
        if (form.confirmPassword && value !== form.confirmPassword) {
          newErrors.confirmPassword = 'Passwords do not match';
        } else if (form.confirmPassword) {
          delete newErrors.confirmPassword;
        }
      }

      if (name === 'confirmPassword') {
        if (value !== form.password) {
          newErrors.confirmPassword = 'Passwords do not match';
        } else {
          delete newErrors.confirmPassword;
        }
      }

      return newErrors;
    });
  };

  const validateForm = () => {
    const newErrors = {};

    if (!form.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (form.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    } else if (form.username.length > 50) {
      newErrors.username = 'Username must be less than 50 characters';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(form.username)) {
      newErrors.username = 'Username can only contain letters, numbers, underscores, and hyphens';
    }

    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      newErrors.email = 'Invalid email address';
    }

    if (!form.password) {
      newErrors.password = 'Password is required';
    } else if (form.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    if (form.password !== form.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
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
      await register(form.username, form.email || null, form.password);
      // Redirect to login page after successful registration
      navigate('/login');
    } catch (error) {
      setSubmitError(
        error.response?.data?.detail || 'Registration failed. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 4, mb: 8 }}>
        <Paper elevation={3}>
          <Box sx={{ p: 4 }}>
            <Typography variant="h4" align="center" gutterBottom>
              Create Account
            </Typography>
            <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 4 }}>
              Register to start using the audio processing pipeline
            </Typography>

            {submitError && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSubmitError('')}>
                {submitError}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Username *"
                name="username"
                value={form.username}
                onChange={handleChange}
                error={!!errors.username}
                helperText={errors.username || 'Letters, numbers, underscores, hyphens only'}
                autoComplete="username"
                autoFocus
                sx={{ mb: 3 }}
                FormHelperTextProps={{
                  sx: { color: errors.username ? 'error.main' : 'text.secondary' }
                }}
              />

              <TextField
                fullWidth
                label="Email (optional)"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                error={!!errors.email}
                helperText={errors.email}
                autoComplete="email"
                sx={{ mb: 3 }}
              />

              <TextField
                fullWidth
                label="Password *"
                name="password"
                type="password"
                value={form.password}
                onChange={handleChange}
                error={!!errors.password}
                helperText={errors.password || 'At least 6 characters'}
                autoComplete="new-password"
                sx={{ mb: 3 }}
                FormHelperTextProps={{
                  sx: { color: errors.password ? 'error.main' : 'text.secondary' }
                }}
              />

              <TextField
                fullWidth
                label="Confirm Password *"
                name="confirmPassword"
                type="password"
                value={form.confirmPassword}
                onChange={handleChange}
                error={!!errors.confirmPassword}
                helperText={errors.confirmPassword || 'Re-enter password'}
                autoComplete="new-password"
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
                {isSubmitting ? 'Creating account...' : 'Register'}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2">
                  Already have an account?{' '}
                  <Link
                    component="button"
                    type="button"
                    onClick={() => navigate('/login')}
                    underline="hover"
                  >
                    Sign In
                  </Link>
                </Typography>
              </Box>
            </form>
          </Box>
        </Paper>

        <Box sx={{ mt: 4, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            What you'll get:
          </Typography>
          <Typography variant="body2" component="ul" sx={{ pl: 2 }}>
            <li>User-isolated data directories</li>
            <li>Per-user pipeline configuration with HuggingFace integration</li>
            <li>Real-time job progress tracking</li>
            <li>Secure token encryption</li>
          </Typography>
        </Box>
      </Box>
    </Container>
  );
}

export default RegisterPage;