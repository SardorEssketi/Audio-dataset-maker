import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  Chip,
  Alert,
  Divider,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  ContentCopy as ContentCopyIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import JobStatusBadge from './JobStatusBadge';

/**
 * Detailed view of a pipeline job with error logs and traceback.
 */
function JobDetail() {
  const { jobId } = useParams();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchJob();
  }, [jobId]);

  const fetchJob = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await axios.get(`/api/pipelines/${jobId}`);
      setJob(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load job details');
      setJob(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchJob();
    setRefreshing(false);
  };

  const handleCopyError = () => {
    if (job?.error_traceback) {
      navigator.clipboard.writeText(job.error_traceback);
    }
  };

  const handleBack = () => {
    navigate('/dashboard');
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'success.main';
      case 'failed':
        return 'error.main';
      case 'running':
        return 'info.main';
      case 'cancelled':
        return 'warning.main';
      default:
        return 'grey.500';
    }
  };

  const formatDuration = (start, end) => {
    if (!start || !end) return 'N/A';
    const duration = new Date(end) - new Date(start);
    const minutes = Math.floor(duration / 60000);
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours > 0) {
      return `${hours}h ${remainingMinutes}m`;
    }
    return `${remainingMinutes}m`;
  };

  const formatSize = (bytes) => {
    if (!bytes) return 'N/A';
    const mb = bytes / (1024 * 1024);
    if (mb < 1) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    if (mb < 1024) {
      return `${mb.toFixed(2)} MB`;
    }
    return `${(mb / 1024).toFixed(2)} GB`;
  };

  if (loading && !job) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && !job) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={handleBack}
          sx={{ mb: 2 }}
        >
          Back to Dashboard
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={handleBack}
        >
          Back
        </Button>

        <Box sx={{ flexGrow: 1, ml: 2 }}>
          <Typography variant="h4" component="div">
            Job #{job.id} Details
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <JobStatusBadge status={job.status} />
          <Tooltip title="Refresh job details">
            <IconButton
              onClick={handleRefresh}
              disabled={refreshing}
              size="small"
            >
              <RefreshIcon sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Main Info Card */}
      <Paper elevation={2} sx={{ mb: 3 }}>
        <Box sx={{ p: 3 }}>
          <Grid container spacing={3}>
            {/* Status */}
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                Status
              </Typography>
              <Box
                sx={{
                  mt: 1,
                  p: 2,
                  bgcolor: getStatusColor(job.status),
                  borderRadius: 1,
                  textAlign: 'center',
                }}
              >
                <Typography variant="h5" sx={{ color: 'white' }}>
                  {job.status.toUpperCase()}
                </Typography>
              </Box>
            </Grid>

            {/* Created Time */}
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                Created
              </Typography>
              <Typography variant="body1">
                {new Date(job.created_at).toLocaleString()}
              </Typography>
            </Grid>

            {/* Duration */}
            {job.started_at && job.completed_at && (
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Duration
                </Typography>
                <Typography variant="body1">
                  {formatDuration(job.started_at, job.completed_at)}
                </Typography>
              </Grid>
            )}

            {/* File Count */}
            {job.file_count !== null && (
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Files Processed
                </Typography>
                <Typography variant="body1">
                  {job.file_count} files
                </Typography>
              </Grid>
            )}

            {/* Total Size */}
            {job.total_size_bytes !== null && (
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Total Size
                </Typography>
                <Typography variant="body1">
                  {formatSize(job.total_size_bytes)}
                </Typography>
              </Grid>
            )}
          </Grid>
        </Box>
      </Paper>

      {/* Source Information */}
      <Paper elevation={2} sx={{ mb: 3 }}>
        <Box sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Source Information
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="subtitle2">Type:</Typography>
              <Chip
                label={job.source_type.toUpperCase()}
                size="small"
                color="primary"
                sx={{ mt: 0.5 }}
              />
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2">Value:</Typography>
              <Typography
                variant="body1"
                sx={{
                  wordBreak: 'break-all',
                  fontFamily: 'monospace',
                  bgcolor: '#f5f5f5',
                  p: 1,
                  borderRadius: 1,
                  mt: 0.5,
                }}
              >
                {job.source_value}
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {/* Progress Steps - for completed jobs */}
      {job.status === 'completed' && (
        <Paper elevation={2} sx={{ mb: 3 }}>
          <Box sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Pipeline Steps
            </Typography>
            <Alert severity="success" sx={{ mb: 2 }}>
              Pipeline completed successfully!
            </Alert>
            <Typography variant="body2" color="text.secondary">
              All steps completed successfully.
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Error Information - for failed jobs */}
      {job.status === 'failed' && (
        <Accordion elevation={2} sx={{ mb: 3 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" sx={{ color: 'error' }}>
              Error Information
            </Typography>
          </AccordionSummary>

          <AccordionDetails>
            <Box sx={{ p: 2 }}>
              {/* Error Message */}
              {job.error_message && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Error Message
                  </Typography>
                  <Alert severity="error" sx={{ mt: 0.5 }}>
                    {job.error_message}
                  </Alert>
                </Box>
              )}

              {/* Last Successful Step */}
              {job.last_successful_step && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Last Successful Step
                  </Typography>
                  <Chip
                    label={job.last_successful_step}
                    color="primary"
                    variant="outlined"
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                    Pipeline completed up to this step before failing.
                  </Typography>
                </Box>
              )}

              {/* Traceback */}
              {job.error_traceback && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Error Traceback
                  </Typography>
                  <Box sx={{ position: 'relative' }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<ContentCopyIcon />}
                      onClick={handleCopyError}
                      sx={{ position: 'absolute', right: 0, top: 0, zIndex: 1 }}
                    >
                      Copy to Clipboard
                    </Button>
                    <Typography
                      component="pre"
                      sx={{
                        mt: 1,
                        bgcolor: '#f5f5f5',
                        p: 2,
                        borderRadius: 1,
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        maxHeight: '400px',
                        overflow: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        color: 'error.dark',
                      }}
                    >
                      {job.error_traceback}
                    </Typography>
                  </Box>
                </Box>
              )}

              {/* Actions */}
              <Box sx={{ mt: 3, display: 'flex', gap: 1, justifyContent: 'center' }}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => navigate(`/pipeline/run`)}
                >
                  Try Again
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleBack}
                >
                  Back to Dashboard
                </Button>
              </Box>
            </Box>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Running State */}
      {job.status === 'running' && (
        <Paper elevation={2} sx={{ mb: 3 }}>
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <CircularProgress size={40} sx={{ mb: 2 }} />
            <Typography variant="h6" color="primary">
              Pipeline is running...
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Check back later or view job details for progress.
            </Typography>
          </Box>
        </Paper>
      )}
    </Container>
  );
}

export default JobDetail;
