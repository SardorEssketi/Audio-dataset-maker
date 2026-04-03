import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Slider,
  Paper,
  Grid,
  Card,
  CardContent,
  FormControlLabel,
  Switch,
  Divider,
  Chip,
  Button,
  Alert,
  Collapse,
  Select,
  MenuItem,
  IconButton,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

/**
 * Advanced configuration options modal.
 * Full config access for expert users.
 */
function AdditionalOptions({ config, onClose }) {
  const [formData, setFormData] = useState({});
  const [expanded, setExpanded] = useState({});

  const toggleSection = (section) => {
    setExpanded((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // Initialize form data from config
  React.useEffect(() => {
    if (config) {
      setFormData({
        // Audio settings
        audio_sample_rate: config.audio?.sample_rate || 16000,
        audio_channels: config.audio?.channels || 1,

        // VAD settings
        vad_aggressiveness: config.vad?.aggressiveness || 3,
        vad_frame_duration_ms: config.vad?.frame_duration_ms || 30,
        vad_min_silence_duration_ms: config.vad?.min_silence_duration_ms || 500,
        vad_min_segment_duration_s: config.vad?.min_segment_duration_s || 1.0,
        vad_max_segment_duration_s: config.vad?.max_segment_duration_s || 30.0,

        // Whisper settings
        whisper_language: config.whisper?.language || 'uz',
        whisper_batch_size: config.whisper?.batch_size || 8,
        whisper_compute_type: config.whisper?.compute_type || 'float16',
        whisper_mode: config.whisper?.mode || 'auto',
        whisper_device: config.whisper?.device || 'cuda',
        whisper_server_url: config.whisper?.server?.url || '',
      });
    }
  }, [config]);

  const handleChange = (field) => (event) => {
    const value = event.target.type === 'checkbox'
      ? event.target.checked
      : event.target.type === 'number'
        ? parseFloat(event.target.value)
        : event.target.value;

    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Additional Options
      </Typography>

      <Typography variant="body2" color="text.secondary" paragraph>
        Advanced configuration options. Modify these carefully as they affect all pipeline runs.
        Some changes may require a pipeline restart to take effect.
      </Typography>

      <Grid container spacing={2}>
        {/* Audio Settings */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2">Audio Settings</Typography>
                <IconButton size="small" onClick={() => toggleSection('audio')}>
                  {expanded.audio ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>

              <Collapse in={expanded.audio}>
                <Box sx={{ mt: 2 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Sample Rate (Hz)"
                        type="number"
                        value={formData.audio_sample_rate}
                        onChange={(e) => handleChange('audio_sample_rate')}
                        inputProps={{ step: 1000, min: 8000, max: 48000 }}
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Channels"
                        type="number"
                        value={formData.audio_channels}
                        onChange={(e) => handleChange('audio_channels')}
                        inputProps={{ min: 1, max: 2 }}
                      />
                    </Grid>
                  </Grid>
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* VAD Settings */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2">Voice Activity Detection (VAD)</Typography>
                <IconButton size="small" onClick={() => toggleSection('vad')}>
                  {expanded.vad ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>

              <Collapse in={expanded.vad}>
                <Box sx={{ mt: 2 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Aggressiveness: <strong>{formData.vad_aggressiveness}</strong>
                      </Typography>
                      <Slider
                        value={formData.vad_aggressiveness}
                        onChange={(e) => handleChange('vad_aggressiveness')}
                        min={0}
                        max={3}
                        marks={[
                          { value: 0, label: 'Least aggressive' },
                          { value: 1, label: 'Low' },
                          { value: 2, label: 'Medium' },
                          { value: 3, label: 'Most aggressive' },
                        ]}
                        valueLabelDisplay="off"
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Frame Duration (ms)"
                        type="number"
                        value={formData.vad_frame_duration_ms}
                        onChange={(e) => handleChange('vad_frame_duration_ms')}
                        inputProps={{ step: 5, min: 10, max: 100 }}
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Min Silence (ms)"
                        type="number"
                        value={formData.vad_min_silence_duration_ms}
                        onChange={(e) => handleChange('vad_min_silence_duration_ms')}
                        inputProps={{ step: 50, min: 100, max: 2000 }}
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Min Segment (sec)"
                        type="number"
                        value={formData.vad_min_segment_duration_s}
                        onChange={(e) => handleChange('vad_min_segment_duration_s')}
                        inputProps={{ step: 0.1, min: 0.5, max: 10 }}
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Max Segment (sec)"
                        type="number"
                        value={formData.vad_max_segment_duration_s}
                        onChange={(e) => handleChange('vad_max_segment_duration_s')}
                        inputProps={{ step: 1, min: 5, max: 60 }}
                      />
                    </Grid>
                  </Grid>
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* Whisper Settings */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2">Whisper Transcription</Typography>
                <IconButton size="small" onClick={() => toggleSection('whisper')}>
                  {expanded.whisper ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>

              <Collapse in={expanded.whisper}>
                <Box sx={{ mt: 2 }}>
                  <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 2 }}>
                    <Typography variant="caption">
                      Whisper model is fixed to OvozifyLabs/whisper-small-uz-v1 for Uzbek language.
                      These settings only affect the execution mode, not the model itself.
                    </Typography>
                  </Alert>

                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Language"
                        value={formData.whisper_language}
                        onChange={(e) => handleChange('whisper_language')}
                        helperText="uz for Uzbek"
                        disabled
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Batch Size"
                        type="number"
                        value={formData.whisper_batch_size}
                        onChange={(e) => handleChange('whisper_batch_size')}
                        inputProps={{ min: 1, max: 16 }}
                      />
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Compute Type
                      </Typography>
                      <Select
                        fullWidth
                        value={formData.whisper_compute_type}
                        onChange={(e) => handleChange('whisper_compute_type')}
                      >
                        <MenuItem value="float16">float16 (GPU)</MenuItem>
                        <MenuItem value="float32">float32 (CPU)</MenuItem>
                      </Select>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                        GPU: faster, requires 8GB+ VRAM
                      </Typography>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Mode
                      </Typography>
                      <Select
                        fullWidth
                        value={formData.whisper_mode}
                        onChange={(e) => handleChange('whisper_mode')}
                      >
                        <MenuItem value="auto">Auto (GPU if available, else CPU)</MenuItem>
                        <MenuItem value="local">Local Force</MenuItem>
                        <MenuItem value="server">Server</MenuItem>
                      </Select>
                    </Grid>

                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Device
                      </Typography>
                      <Select
                        fullWidth
                        value={formData.whisper_device}
                        onChange={(e) => handleChange('whisper_device')}
                      >
                        <MenuItem value="cuda">CUDA (GPU)</MenuItem>
                        <MenuItem value="cpu">CPU</MenuItem>
                      </Select>
                    </Grid>

                    {formData.whisper_mode === 'server' && (
                      <Grid item xs={12}>
                        <TextField
                          fullWidth
                          label="Server URL"
                          placeholder="http://your-server:8000/v1"
                          value={formData.whisper_server_url}
                          onChange={(e) => handleChange('whisper_server_url')}
                        />
                      </Grid>
                    )}
                  </Grid>
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
        <Button variant="outlined" onClick={onClose}>
          Close
        </Button>
      </Box>
    </Box>
  );
}

export default AdditionalOptions;
