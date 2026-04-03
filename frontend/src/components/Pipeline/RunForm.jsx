import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
  Chip,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Refresh as RetryIcon,
  Cancel as CancelIcon,
  CloudUpload as CloudUploadIcon,
  Storage as StorageIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import SourceSelector from './SourceSelector';
import JobProgress from './JobProgress';

/**
 * Pipeline run form with source selection and job management.
 * Supports both create and view modes based on URL jobId.
 */
function RunForm({ initialJobData }) {
  const navigate = useNavigate();
  const isViewMode = !!initialJobData?.id;

  const [form, setForm] = useState({
    source_type: 'url',
    source_value: '',
    skip_download: false,
    skip_push: false,
  });

  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [jobId, setJobId] = useState(initialJobData?.id || null);
  const [jobData, setJobData] = useState(initialJobData || null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const sourceTypeLimits = {
    url: { min: 1, max: 1, unit: 'URL', description: 'Direct link to audio file' },
    youtube: { min: 1, max: 10, unit: 'videos', description: 'YouTube videos or playlists' },
    json: { min: 1, max: 1, unit: 'JSON file', description: 'JSON file with URLs array' },
    huggingface: { min: 1, max: 1, unit: 'dataset', description: 'HuggingFace dataset name' },
    local: { min: 1, max: 5, unit: 'files', description: 'Uploaded audio files' },
  };

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const handleFileUpload = (files) => {
    setUploadedFiles(files);
    setErrors((prev) => ({ ...prev, files: '' }));
  };

  const validateForm = useCallback(() => {
    const newErrors = {};

    if (!form.source_type) {
      newErrors.source_type = 'Please select a source type';
      return newErrors;
    }

    const limits = sourceTypeLimits[form.source_type];

    if (form.source_type === 'local') {
      const hasDirectoryPath = !!form.source_value?.trim();
      const fileCount = uploadedFiles.length;

      // Allow either a directory path OR uploaded files.
      if (!hasDirectoryPath) {
        if (fileCount < limits.min) {
          newErrors.files = `At least ${limits.min} ${limits.unit} required`;
        } else if (fileCount > limits.max) {
          newErrors.files = `Maximum ${limits.max} ${limits.unit} allowed`;
        }

        uploadedFiles.forEach((file, index) => {
          const maxSize = 2 * 1024 * 1024 * 1024; // 2GB
          if (file.size > maxSize) {
            newErrors[`file_${index}`] = `File too large (max 2GB)`;
          }
        });
      }
    } else if (!form.source_value?.trim()) {
      newErrors.source_value = `${limits.description} is required`;
    }

    return newErrors;
  }, [form, uploadedFiles, sourceTypeLimits]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setErrors({});
    setIsSubmitting(true);

    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      setIsSubmitting(false);
      return;
    }

    try {
      let sourceValue = form.source_value;

      const isLocal = form.source_type === 'local';
      const autoSkipDownload = isLocal;

      // Backend expects JSON for /api/pipelines. For local uploads, first upload
      // files to the temp directory endpoint, then pass the returned temp_dir as
      // the local source_value (directory path).
      if (isLocal && uploadedFiles.length > 0 && !sourceValue?.trim()) {
        const uploadData = new FormData();
        uploadedFiles.forEach((file) => uploadData.append('files', file));

        const uploadResp = await axios.post('/api/pipelines/files/upload', uploadData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        sourceValue = uploadResp.data?.temp_dir || '';
      }

      const response = await axios.post('/api/pipelines', {
        source_type: form.source_type,
        source_value: sourceValue,
        skip_download: autoSkipDownload,
        skip_push: form.skip_push,
      });

      setJobId(response.data.id);
      setJobData(response.data);
      setSubmitSuccess(true);
      setIsSubmitting(false);
    } catch (error) {
      setErrors({
        submit: error.response?.data?.detail || 'Failed to submit job. Please try again.',
      });
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;

    try {
      await axios.post(`/api/pipelines/${jobId}/cancel`);
      if (jobData) {
        setJobData({ ...jobData, status: 'cancelled' });
      }
    } catch (error) {
      setErrors({
        cancel: error.response?.data?.detail || 'Failed to cancel job.',
      });
    }
  };

  const handleRetry = async () => {
    if (!jobId) return;

    setIsSubmitting(true);
    try {
      const response = await axios.post(`/api/pipelines/${jobId}/retry`);
      setJobData(response.data);
      setIsSubmitting(false);
    } catch (error) {
      setErrors({
        retry: error.response?.data?.detail || 'Failed to retry job.',
      });
      setIsSubmitting(false);
    }
  };

  return (
    <Box>
      {submitSuccess && jobData && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSubmitSuccess(false)}>
          Pipeline job started successfully! Job ID: {jobId}
        </Alert>
      )}

      {Object.values(errors).filter(Boolean).length > 0 && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {Object.values(errors).filter(Boolean).join('. ')}
        </Alert>
      )}

      {!isViewMode && (
        <Paper elevation={2}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Run Pipeline
            </Typography>

            <SourceSelector
              sourceType={form.source_type}
              sourceValue={form.source_value}
              onChange={handleChange}
              uploadedFiles={uploadedFiles}
              onUpload={handleFileUpload}
            />

            <Divider sx={{ my: 3 }} />

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Button
                  fullWidth
                  variant={form.source_type === 'local' ? 'outlined' : 'contained'}
                  disabled
                >
                  {form.source_type === 'local' ? 'Auto: Skipped' : 'Auto: Included'} Download
                </Button>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Automatic: local sources use the provided directory/files; remote sources must download.
                </Typography>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Button
                  fullWidth
                  variant={form.skip_push ? 'outlined' : 'contained'}
                  onClick={() => handleChange('skip_push', !form.skip_push)}
                  color="secondary"
                >
                  {form.skip_push ? 'Skipped' : 'Include'} Push to HF
                </Button>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Skip pushing results to HuggingFace dataset
                </Typography>
              </Grid>
            </Grid>

            <Divider sx={{ my: 3 }} />

            {/* Limits Info */}
            <Box sx={{ p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>
                Source Limits for {form.source_type.toUpperCase()}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  icon={<StorageIcon />}
                  label={`Min: ${sourceTypeLimits[form.source_type].min}`}
                  size="small"
                />
                <Chip
                  icon={<CloudUploadIcon />}
                  label={`Max: ${sourceTypeLimits[form.source_type].max} ${sourceTypeLimits[form.source_type].unit}`}
                  size="small"
                />
              </Box>
            </Box>

            <Divider sx={{ my: 3 }} />

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                onClick={() => navigate('/dashboard')}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                startIcon={isSubmitting ? <CircularProgress size={20} /> : <PlayIcon />}
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Submitting...' : 'Run Pipeline'}
              </Button>
            </Box>
          </CardContent>
        </Paper>
      )}

      {isViewMode && jobId && jobData && (
        <Box>
          {/* Job Info Card */}
          <Paper elevation={2} sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Job Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2">Job ID:</Typography>
                  <Typography variant="body2">{jobId}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2">Status:</Typography>
                  <Chip
                    label={jobData.status}
                    color={
                      jobData.status === 'completed' ? 'success' :
                      jobData.status === 'failed' ? 'error' :
                      jobData.status === 'cancelled' ? 'default' : 'primary'
                    }
                    size="small"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2">Source Type:</Typography>
                  <Typography variant="body2">{jobData.source_type}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2">Created:</Typography>
                  <Typography variant="body2">
                    {new Date(jobData.created_at).toLocaleString()}
                  </Typography>
                </Grid>
                {jobData.source_value && (
                  <Grid item xs={12}>
                    <Typography variant="subtitle2">Source:</Typography>
                    <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                      {jobData.source_value}
                    </Typography>
                  </Grid>
                )}
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  startIcon={<RetryIcon />}
                  onClick={handleRetry}
                  disabled={
                    isSubmitting ||
                    ['running', 'pending'].includes(jobData.status)
                  }
                >
                  Retry
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<CancelIcon />}
                  onClick={handleCancel}
                  disabled={
                    !['pending', 'running'].includes(jobData.status) ||
                    isSubmitting
                  }
                >
                  Cancel
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => navigate('/dashboard')}
                >
                  Back to Dashboard
                </Button>
              </Box>
            </CardContent>
          </Paper>

          {/* Progress Display */}
          <JobProgress
            jobId={jobId}
            jobData={jobData}
            onCancel={handleCancel}
            onClose={() => navigate('/dashboard')}
          />
        </Box>
      )}
    </Box>
  );
}

export default RunForm;
