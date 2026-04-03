import React from 'react';
import { Chip } from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Pending as PendingIcon,
  Cancel as CancelIcon,
  Sync as RunningIcon,
} from '@mui/icons-material';

/**
 * Visual badge for job status.
 * Color-coded for quick status identification.
 */
function JobStatusBadge({ status, size = 'small' }) {
  const getStatusConfig = (status) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return {
          color: 'default',
          icon: <PendingIcon fontSize="small" />,
          label: 'Pending',
        };

      case 'running':
        return {
          color: 'info',
          icon: <RunningIcon fontSize="small" />,
          label: 'Running',
        };

      case 'completed':
        return {
          color: 'success',
          icon: <CheckCircleIcon fontSize="small" />,
          label: 'Completed',
        };

      case 'failed':
        return {
          color: 'error',
          icon: <ErrorIcon fontSize="small" />,
          label: 'Failed',
        };

      case 'cancelled':
        return {
          color: 'warning',
          icon: <CancelIcon fontSize="small" />,
          label: 'Cancelled',
        };

      default:
        return {
          color: 'default',
          icon: <PendingIcon fontSize="small" />,
          label: 'Unknown',
        };
    }
  };

  const config = getStatusConfig(status);

  return (
    <Chip
      icon={config.icon}
      label={config.label}
      color={config.color}
      size={size}
      variant="outlined"
      sx={{
        fontWeight: 500,
        '& .MuiChip-icon': {
          fontSize: size === 'small' ? '14px' : '16px',
        },
      }}
    />
  );
}

export default JobStatusBadge;
