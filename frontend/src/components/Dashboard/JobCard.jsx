import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Divider,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Refresh as RetryIcon,
  Visibility as ViewIcon,
  Close as CloseIcon,
  Schedule as ScheduleIcon,
  AudioFile as AudioFileIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import axios from 'axios';
import JobStatusBadge from './JobStatusBadge';

function JobCard({ job, onRetry, onCancel, onDelete }) {
  const [viewDetailsOpen, setViewDetailsOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const handleViewDetails = () => {
    setViewDetailsOpen(true);
  };

  const handleCloseDetails = () => {
    setViewDetailsOpen(false);
  };

  const handleCancel = async () => {
    if (cancelling || !onCancel) return;

    setCancelling(true);
    try {
      await onCancel(job);
    } catch (error) {
      console.error('Cancel failed:', error);
    } finally {
      setCancelling(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;

    try {
      await onDelete(job);
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const getSourceIcon = () => {
    const icons = {
      url: <AudioFileIcon />,
      youtube: <ScheduleIcon />, // Using schedule icon for video
      json: <AudioFileIcon />,
      huggingface: <AudioFileIcon />,
      local: <AudioFileIcon />,
    };
    return icons[job.source_type] || <AudioFileIcon />;
  };

  const getSourceTypeLabel = () => {
    const labels = {
      url: 'URL',
      youtube: 'YouTube',
      json: 'JSON',
      huggingface: 'HuggingFace',
      local: 'Local Files',
    };
    return labels[job.source_type] || job.source_type;
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

  const isRunning = job.status === 'running';
  const isPending = job.status === 'pending';
  const isFailed = job.status === 'failed';
  const isCompleted = job.status === 'completed';

  return (
    <>
      <Card
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: 'transform 0.2s',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: 6,
          },
        }}
      >
        <CardContent sx={{ flexGrow: 1, p: 2 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getSourceIcon()}
              <Box>
                <Typography variant="h6" component="div">
                  {getSourceTypeLabel()}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  #{job.id}
                </Typography>
              </Box>
            </Box>
            <JobStatusBadge status={job.status} />
          </Box>

          {/* Created time */}
          <Typography variant="caption" color="text.secondary">
            {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
          </Typography>

          {/* Source value (truncated) */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Source:
            </Typography>
            <Typography variant="body1" sx={{ wordBreak: 'break-all' }}>
              {job.source_value}
            </Typography>
          </Box>

          {/* Stats */}
          {job.file_count !== null && (
            <Box sx={{ mt: 1 }}>
              <Chip
                icon={<AudioFileIcon />}
                label={`${job.file_count} files`}
                size="small"
                sx={{ mr: 1 }}
              />
              {job.total_size_bytes !== null && (
                <Chip
                  label={formatSize(job.total_size_bytes)}
                  size="small"
                />
              )}
            </Box>
          )}

          {/* Last successful step for failed jobs */}
          {isFailed && job.last_successful_step && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Last successful step:{' '}
                <Chip
                  label={job.last_successful_step}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              </Typography>
            </Box>
          )}

          {/* Error preview */}
          {isFailed && job.error_message && (
            <Box sx={{ mt: 1, p: 1, bgcolor: 'error.light', borderRadius: 1 }}>
              <Typography variant="caption" color="error.dark" noWrap>
                {job.error_message}
              </Typography>
            </Box>
          )}
        </CardContent>

        {/* Actions */}
        <CardActions sx={{ p: 1, pt: 0 }}>
          <Tooltip title="View details">
            <IconButton onClick={handleViewDetails} size="small">
              <ViewIcon />
            </IconButton>
          </Tooltip>

          {isFailed && (
            <Tooltip title="Retry job">
              <IconButton
                onClick={() => onRetry(job)}
                size="small"
                color="primary"
              >
                <RetryIcon />
              </IconButton>
            </Tooltip>
          )}

          {isRunning && onCancel && (
            <Tooltip title="Cancel job">
              <IconButton
                onClick={handleCancel}
                size="small"
                color="error"
                disabled={cancelling}
              >
                <CloseIcon />
              </IconButton>
            </Tooltip>
          )}

          {!isRunning && onDelete && (
            <Tooltip title="Delete job">
              <IconButton
                onClick={handleDelete}
                size="small"
                color="default"
              >
                <DeleteIcon />
              </IconButton>
            </Tooltip>
          )}
        </CardActions>
      </Card>

      {/* Details Dialog */}
      <Dialog
        open={viewDetailsOpen}
        onClose={handleCloseDetails}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6">
              Job #{job.id} Details
            </Typography>
            <JobStatusBadge status={job.status} />
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          <Box sx={{ mt: 2 }}>
            {/* Timeline */}
            <Typography variant="subtitle2" gutterBottom>
              Timeline
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Created:
                </Typography>
                <Typography variant="body1">
                  {new Date(job.created_at).toLocaleString()}
                </Typography>
              </Box>

              {job.started_at && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Started:
                  </Typography>
                  <Typography variant="body1">
                    {new Date(job.started_at).toLocaleString()}
                  </Typography>
                </Box>
              )}

              {job.completed_at && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Completed:
                  </Typography>
                  <Typography variant="body1">
                    {new Date(job.completed_at).toLocaleString()}
                  </Typography>
                </Box>
              )}
            </Box>

            {/* Source Info */}
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>
              Source Information
            </Typography>
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Type: {getSourceTypeLabel()}
              </Typography>
              <Typography variant="body1" gutterBottom>
                Value: {job.source_value}
              </Typography>
            </Box>

            {/* Error Info */}
            {isFailed && job.error_message && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" color="error" gutterBottom>
                  Error
                </Typography>
                <Box sx={{ p: 1, bgcolor: 'error.light', borderRadius: 1 }}>
                  <Typography variant="body1" color="error.dark">
                    {job.error_message}
                  </Typography>
                </Box>

                {job.last_successful_step && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Last successful step:{' '}
                      <Chip
                        label={job.last_successful_step}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </Typography>
                  </Box>
                )}
              </>
            )}

            {/* Traceback */}
            {isFailed && job.error_traceback && (
              <>
                <Divider sx={{ my: 2 }} />
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    navigator.clipboard.writeText(job.error_traceback);
                  }}
                >
                  Copy Error Log
                </Button>
                <Box sx={{ mt: 1, maxHeight: 300, overflow: 'auto' }}>
                  <Typography
                    variant="body2"
                    component="pre"
                    sx={{
                      bgcolor: '#f5f5f5',
                      p: 2,
                      borderRadius: 1,
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {job.error_traceback}
                  </Typography>
                </Box>
              </>
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleCloseDetails}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default JobCard;
