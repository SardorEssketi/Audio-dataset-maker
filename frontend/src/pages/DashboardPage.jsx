import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Pagination,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Divider,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  PlayArrow as RunIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Cancel as CancelIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

/**
 * Dashboard page showing all pipeline jobs.
 * Features: job listing, filtering, status monitoring, actions.
 */
function DashboardPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState(null);

  const fetchJobs = async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, limit: 10 };
      if (statusFilter) {
        params.status = statusFilter;
      }

      const response = await axios.get('/api/pipelines', { params });
      setJobs(response.data.items || []);
      setTotalPages(response.data.pages || 1);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [page, statusFilter]);

  const handleStatusFilterChange = (status) => {
    setStatusFilter(status === statusFilter ? '' : status);
    setPage(1);
  };

  const handleRunNew = () => {
    navigate('/pipeline/run');
  };

  const handleViewJob = (jobId) => {
    navigate(`/pipeline/${jobId}`);
  };

  const handleCancelJob = async (jobId) => {
    try {
      await axios.post(`/api/pipelines/${jobId}/cancel`);
      fetchJobs();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel job');
    }
  };

  const handleDeleteJob = async () => {
    if (!jobToDelete) return;

    try {
      await axios.delete(`/api/pipelines/${jobToDelete}`);
      setDeleteDialogOpen(false);
      setJobToDelete(null);
      fetchJobs();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete job');
    }
  };

  const handleDownloadJob = async (jobId) => {
    setError('');
    try {
      const response = await axios.get(`/api/pipelines/${jobId}/download`, {
        responseType: 'blob',
      });

      // Guard against backend errors delivered as JSON/HTML (still a blob).
      // A valid ZIP starts with bytes "PK".
      try {
        const head = await response.data.slice(0, 2).arrayBuffer();
        const bytes = new Uint8Array(head);
        const isZip = bytes.length === 2 && bytes[0] === 0x50 && bytes[1] === 0x4b; // 'P' 'K'
        if (!isZip) {
          const text = await response.data.text();
          try {
            const parsed = JSON.parse(text);
            setError(parsed?.detail || 'Download failed (server did not return a ZIP)');
          } catch {
            setError('Download failed (server did not return a ZIP)');
          }
          return;
        }
      } catch {
        // If we can't validate, continue and let the user try to download.
      }

      const contentDisposition = response.headers?.['content-disposition'] || '';
      const filenameMatch = /filename="?([^";]+)"?/i.exec(contentDisposition);
      const filename = filenameMatch?.[1] || `job_${jobId}_processed.zip`;

      const url = window.URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to download processed files');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'cancelled': return 'default';
      case 'running': return 'primary';
      case 'pending': return 'info';
      default: return 'default';
    }
  };

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage your audio processing pipeline jobs
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Total Jobs
              </Typography>
              <Typography variant="h4">
                {jobs.filter(j => ['pending', 'running'].includes(j.status)).length}
                <Typography variant="body2" color="text.secondary" component="span">
                  {' '}active
                </Typography>
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Completed
              </Typography>
              <Typography variant="h4" color="success.main">
                {jobs.filter(j => j.status === 'completed').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Failed
              </Typography>
              <Typography variant="h4" color="error.main">
                {jobs.filter(j => j.status === 'failed').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Cancelled
              </Typography>
              <Typography variant="h4" color="text.secondary">
                {jobs.filter(j => j.status === 'cancelled').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Controls */}
      <Paper elevation={2}>
        <Box sx={{ p: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {['all', 'pending', 'running', 'completed', 'failed', 'cancelled'].map((status) => (
              <Chip
                key={status}
                label={status.charAt(0).toUpperCase() + status.slice(1)}
                onClick={() => handleStatusFilterChange(status === 'all' ? '' : status)}
                color={statusFilter === (status === 'all' ? '' : status) ? 'primary' : 'default'}
                variant={statusFilter === (status === 'all' ? '' : status) ? 'filled' : 'outlined'}
              />
            ))}
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchJobs} disabled={loading}>
                {loading ? <CircularProgress size={24} /> : <RefreshIcon />}
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleRunNew}
            >
              New Pipeline
            </Button>
          </Box>
        </Box>

        <Divider />

        {/* Jobs Table */}
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Source Type</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Current Step</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <CircularProgress />
                  </TableCell>
                </TableRow>
              ) : jobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Box sx={{ py: 4 }}>
                      <Typography variant="h6" color="text.secondary" gutterBottom>
                        No jobs found
                      </Typography>
                      <Button
                        variant="contained"
                        startIcon={<RunIcon />}
                        onClick={handleRunNew}
                      >
                        Run Your First Pipeline
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                jobs.map((job) => (
                  <TableRow key={job.id} hover>
                    <TableCell>#{job.id}</TableCell>
                    <TableCell>{job.source_type}</TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        sx={{
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {job.source_value || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={job.status} color={getStatusColor(job.status)} size="small" />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ minWidth: 180 }}>
                        <Typography variant="caption" color="text.secondary">
                          {job.current_step || '-'}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                          <Box sx={{ flexGrow: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={Number(job.overall_progress || 0)}
                              sx={{ height: 8, borderRadius: 1 }}
                            />
                          </Box>
                          <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'right' }}>
                            {Number(job.overall_progress || 0)}%
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        <Tooltip title="View">
                          <IconButton size="small" onClick={() => handleViewJob(job.id)}>
                            <ViewIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Download processed files">
                          <span>
                            <IconButton
                              size="small"
                              onClick={() => handleDownloadJob(job.id)}
                              disabled={!['completed', 'failed'].includes(job.status)}
                            >
                              <DownloadIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        {['pending', 'running'].includes(job.status) && (
                          <Tooltip title="Cancel">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleCancelJob(job.id)}
                            >
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => {
                              setJobToDelete(job.id);
                              setDeleteDialogOpen(true);
                            }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Pagination */}
        {totalPages > 1 && (
          <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={(e, newPage) => setPage(newPage)}
              color="primary"
            />
          </Box>
        )}
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setJobToDelete(null);
        }}
      >
        <DialogTitle>Delete Job</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete job #{jobToDelete}? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setDeleteDialogOpen(false);
            setJobToDelete(null);
          }}>
            Cancel
          </Button>
          <Button onClick={handleDeleteJob} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}

export default DashboardPage;
