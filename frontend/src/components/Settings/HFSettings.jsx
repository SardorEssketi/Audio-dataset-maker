import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  FormControlLabel,
  Switch,
  Button,
  Alert,
  InputAdornment,
  IconButton,
  FormHelperText,
  CircularProgress,
} from '@mui/material';
import {
  Hub as HubIcon,
  Visibility,
  VisibilityOff,
  Check as CheckIcon,
  Key as KeyIcon,
} from '@mui/icons-material';

/**
 * HuggingFace settings form.
 * Repo ID, private toggle, and masked token management.
 */
function HFSettings({ config, onSave }) {
  const [formData, setFormData] = useState({
    repo_id: config.repo_id || '',
    private: config.private || false,
    token: '', // Only for input, never stored/displayed
  });
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: checked !== undefined ? checked : value,
    }));
  };

  const validateForm = () => {
    if (!formData.repo_id.trim()) {
      setError('Repository ID is required');
      return false;
    }
    if (formData.repo_id && !formData.repo_id.includes('/')) {
      setError('Repository ID must be in format "username/repo-name"');
      return false;
    }
    setError('');
    return true;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setSaving(true);
    setError('');
    setSuccess(false);

    try {
      // Save repo_id and private
      await onSave({
        huggingface_repo_id: formData.repo_id,
        huggingface_private: formData.private,
      });

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const hasToken = config.token && config.token !== '********' && config.token !== '';

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        <HubIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Hugging Face Configuration
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert
          severity="success"
          sx={{ mb: 3 }}
          onClose={() => setSuccess(false)}
          icon={<CheckIcon />}
        >
          Settings saved successfully!
        </Alert>
      )}

      <Box component="form" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
        {/* Repository ID */}
        <TextField
          fullWidth
          label="Repository ID"
          name="repo_id"
          value={formData.repo_id}
          onChange={handleChange}
          disabled={saving}
          required
          margin="normal"
          helperText="Format: username/repo-name"
          error={!formData.repo_id.trim() || (formData.repo_id && !formData.repo_id.includes('/'))}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <HubIcon fontSize="small" color="action" />
              </InputAdornment>
            ),
          }}
        />

        {/* Private Repository */}
        <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <FormControlLabel
            control={
              <Switch
                checked={formData.private}
                onChange={handleChange}
                disabled={saving}
              />
            }
            label="Private Repository"
          />
          <FormHelperText>
            Make the dataset private (only accessible to you)
          </FormHelperText>
        </Box>

        {/* Token Management */}
        <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ mb: 1 }}>
            <KeyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            HuggingFace Token
          </Typography>

          {hasToken ? (
            <Alert
              severity="info"
              sx={{ mb: 1 }}
              action={
                <Button
                  size="small"
                  onClick={() => setShowToken(!showToken)}
                >
                  {showToken ? 'Hide' : 'Show'}
                </Button>
              }
            >
              Token is configured and encrypted. Click to view or modify.
            </Alert>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No token configured. You need to add a token to push datasets to HuggingFace.
            </Typography>
          )}

          {showToken && hasToken && (
            <TextField
              fullWidth
              label="Token"
              name="token"
              value={formData.token}
              onChange={handleChange}
              disabled={saving}
              placeholder="Enter your HuggingFace token (starts with hf_)"
              margin="normal"
              helperText="Your token will be encrypted before saving"
              autoFocus
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <KeyIcon fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
            />
          )}
        </Box>

        {/* Save Button */}
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={saving}
            startIcon={saving ? <CircularProgress size={20} /> : undefined}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export default HFSettings;