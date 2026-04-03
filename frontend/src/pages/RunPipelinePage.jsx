import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Typography, CircularProgress, Alert, Box } from '@mui/material';
import axios from 'axios';
import RunForm from '../components/Pipeline/RunForm';

/**
 * Run pipeline page.
 * Creates a new job or shows existing job details if jobId is in URL.
 */
function RunPipelinePage() {
  const { jobId } = useParams();
  const [initialJobData, setInitialJobData] = useState(null);
  const [loading, setLoading] = useState(!!jobId);
  const [error, setError] = useState('');

  useEffect(() => {
    if (jobId) {
      fetchJobDetails();
    }
  }, [jobId]);

  const fetchJobDetails = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`/api/pipelines/${jobId}`);
      setInitialJobData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load job details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {jobId ? 'Pipeline Job Details' : 'Run New Pipeline'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {jobId
            ? 'View and manage your pipeline job progress'
            : 'Configure and start a new audio processing pipeline'
          }
        </Typography>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <RunForm initialJobData={initialJobData} />
      )}
    </Container>
  );
}

export default RunPipelinePage;