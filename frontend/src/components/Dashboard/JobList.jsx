import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Select,
  MenuItem,
  TextField,
  InputAdornment,
  CircularProgress,
  Alert,
  Grid,
  Paper,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import JobCard from './JobCard';

/**
 * List of pipeline jobs with filtering and pagination.
 */
function JobList() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all'); // all, pending, running, completed, failed
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);
  const [total, setTotal] = useState(0);
  const [userStatus, setUserStatus] = useState(null);

  const navigate = useNavigate();
  const API_BASE = '/api/pipelines';

  const fetchJobs = async (currentFilter, currentPage = page, currentSearch = searchQuery) => {
    setLoading(true);
    setError('');

    try {
      let url = `${API_BASE}`;

      if (currentFilter !== 'all') {
        url += `?status_filter=${currentFilter}`;
      }

      if (currentSearch) {
        url += `&search=${encodeURIComponent(currentSearch)}`;
      }

      url += `&limit=${rowsPerPage}&offset=${currentPage * rowsPerPage}`;

      const response = await axios.get(url);
      setJobs(response.data);
      setTotal(response.data.length); // Backend would return total count in real app
      setPage(currentPage);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load jobs');
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/system/user-status`);
      setUserStatus(response.data);
    } catch (err) {
      // Non-critical, don't show error
    }
  };

  useEffect(() => {
    fetchJobs(filter);
    fetchUserStatus();
  }, []);

  useEffect(() => {
    fetchJobs(filter);
  }, [filter]);

  const handleFilterChange = (event) => {
    const newFilter = event.target.value;
    setFilter(newFilter);
    setPage(0);
    fetchJobs(newFilter, 0);
  };

  const handleSearchChange = (event) => {
    setSearchQuery(event.target.value);
    setPage(0);
    fetchJobs(filter, 0, event.target.value);
  };

  const handleRefresh = () => {
    fetchJobs(filter, page);
    fetchUserStatus();
  };

  const handleRunPipeline = () => {
    if (userStatus?.can_start_job) {
      navigate('/pipeline/run');
    } else {
      setError(userStatus?.active_job_id
        ? 'You already have a running job. Wait for it to complete or cancel it first.'
        : 'System at capacity. Try again later.'
      );
    }
  };

  const handleRetry = async (job) => {
    try {
      await axios.post(`${API_BASE}/${job.id}/retry`);
      fetchJobs(filter, page);
      fetchUserStatus();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to retry job');
    }
  };

  const handleCancel = async (job) => {
    try {
      await axios.post(`${API_BASE}/${job.id}/cancel`);
      fetchJobs(filter, page);
      fetchUserStatus();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel job');
    }
  };

  const handleDelete = async (job) => {
    if (!window.confirm(`Are you sure you want to delete job #${job.id}?`)) {
      return;
    }

    try {
      await axios.delete(`${API_BASE}/${job.id}`);
      fetchJobs(filter, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete job');
    }
  };

  const getStatusStats = () => {
    if (!jobs || jobs.length === 0) {
      return null;
    }

    const stats = {
      total: jobs.length,
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
    };

    jobs.forEach(job => {
      stats[job.status.toLowerCase()]++;
    });

    return stats;
  };

  const stats = getStatusStats();

  if (loading && jobs.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h4" component="div">
          Pipeline Jobs
        </Typography>

        {userStatus && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Chip
              label={`Active: ${userStatus.active_job_count}/${userStatus.max_user_concurrent}`}
              color={userStatus.can_start_job ? 'success' : 'warning'}
              variant="outlined"
            />
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={loading}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              color="primary"
              onClick={handleRunPipeline}
              disabled={!userStatus.can_start_job}
            >
              Run Pipeline
            </Button>
          </Box>
        )}
      </Box>

      {/* Filters and Search */}
      <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <Select
              value={filter}
              onChange={handleFilterChange}
              fullWidth
              size="small"
            >
              <MenuItem value="all">All Jobs</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="running">Running</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
            </Select>
          </Grid>

          <Grid item xs={12} sm={6} md={9}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search jobs..."
              value={searchQuery}
              onChange={handleSearchChange}
              disabled={loading}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
        </Grid>

        {/* Status Stats */}
        {stats && (
          <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
            <Chip label={`Total: ${stats.total}`} size="small" />
            <Chip
              label={`Pending: ${stats.pending}`}
              size="small"
              color="default"
            />
            <Chip
              label={`Running: ${stats.running}`}
              size="small"
              color="info"
            />
            <Chip
              label={`Completed: ${stats.completed}`}
              size="small"
              color="success"
            />
            <Chip
              label={`Failed: ${stats.failed}`}
              size="small"
              color="error"
            />
          </Box>
        )}
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Jobs Grid */}
      {jobs.length === 0 && !loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary">
            No jobs found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {filter !== 'all'
              ? `No ${filter} jobs yet. Create your first pipeline run!`
              : 'No jobs found matching your search.'
            }
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {jobs.map((job) => (
            <Grid item xs={12} sm={6} md={4} key={job.id}>
              <JobCard
                job={job}
                onRetry={handleRetry}
                onCancel={handleCancel}
                onDelete={handleDelete}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Pagination (simplified) */}
      {jobs.length > 0 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3, gap: 2 }}>
          <Button
            disabled={page === 0}
            onClick={() => {
              setPage(page - 1);
              fetchJobs(filter, page - 1);
            }}
          >
            Previous
          </Button>
          <Typography variant="body2">
            Page {page + 1}
          </Typography>
          <Button
            disabled={(page + 1) * rowsPerPage >= total}
            onClick={() => {
              setPage(page + 1);
              fetchJobs(filter, page + 1);
            }}
          >
            Next
          </Button>
        </Box>
      )}
    </Container>
  );
}

export default JobList;
