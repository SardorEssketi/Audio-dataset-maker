import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  FormControlLabel,
  Switch,
  Divider,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  VolumeUp as VolumeUpIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';

/**
 * Processing settings form.
 * Noise reduction and filtering toggles.
 */
function ProcessingSettings({ config }) {
  const [formData, setFormData] = useState({
    noise_reduction_enabled: config.noise_reduction_enabled !== undefined ? config.noise_reduction_enabled : true,
    filtering_enabled: config.filtering_enabled !== undefined ? config.filtering_enabled : true,
  });

  const handleChange = (field) => (event) => {
    setFormData((prev) => ({
      ...prev,
      [field]: event.target.checked,
    }));
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Processing Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Noise Reduction */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <VolumeUpIcon color="primary" sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h6">
                  Noise Reduction
                </Typography>
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={formData.noise_reduction_enabled}
                    onChange={(e) => handleChange('noise_reduction_enabled')}
                    color="primary"
                  />
                }
                label="Enable Noise Reduction"
              />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 2, display: 'block' }}>
                Removes background noise from audio files before transcription.
                Improves transcription quality but takes longer to process.
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2">
                When enabled:
              </Typography>
              <Box component="ul" sx={{ mt: 1 }}>
                <li>
                  <Typography variant="body2">
                    <strong>Stationary:</strong> {config.noise_reduction?.stationary !== false ? 'On' : 'Off'}
                  </Typography>
                </li>
                <li>
                  <Typography variant="body2">
                    <strong>Decrease:</strong> {config.noise_reduction?.prop_decrease !== undefined ? config.noise_reduction?.prop_decrease : '1.0'}
                  </Typography>
                </li>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Filtering */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <FilterIcon color="secondary" sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h6">
                  Transcription Filtering
                </Typography>
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={formData.filtering_enabled}
                    onChange={(e) => handleChange('filtering_enabled')}
                    color="secondary"
                  />
                }
                label="Enable Filtering"
              />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 2, display: 'block' }}>
                Filter out invalid transcriptions to improve dataset quality.
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2">
                Filter Criteria:
              </Typography>
              <Box component="ul" sx={{ mt: 1 }}>
                <li>
                  <Typography variant="body2">
                    <strong>Min Length:</strong> {config.filtering?.min_length || 3} characters
                  </Typography>
                </li>
                <li>
                  <Typography variant="body2">
                    <strong>Max Length:</strong> {config.filtering?.max_length || 1000} characters
                  </Typography>
                </li>
                <li>
                  <Typography variant="body2">
                    <strong>Min Uzbek Ratio:</strong> {(config.filtering?.min_uzbek_char_ratio || 0.7) * 100}%
                  </Typography>
                </li>
                <li>
                  <Typography variant="body2">
                    <strong>Max Repetition:</strong> {(config.filtering?.max_repetition_ratio || 0.7) * 100}%
                  </Typography>
                </li>
              </Box>

              <Box sx={{ mt: 2, p: 1, bgcolor: 'info.light', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Note: Filters also remove transcriptions with Cyrillic, Arabic, Chinese characters,
                  error markers, or excessive word repetition.
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default ProcessingSettings;
