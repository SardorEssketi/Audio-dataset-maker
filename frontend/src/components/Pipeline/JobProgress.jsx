import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Paper,
  Step as MuiStep,
  StepLabel,
  Stepper,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  ContentCopy as ContentCopyIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';

const PIPELINE_STEPS = [
  { key: 'download', label: 'Download' },
  { key: 'normalize', label: 'Normalize' },
  { key: 'noise_reduction', label: 'Noise Reduction' },
  { key: 'vad_segmentation', label: 'Segment' },
  { key: 'transcription', label: 'Transcribe' },
  { key: 'filter', label: 'Filter' },
  { key: 'push', label: 'Push to HF' },
];

const makeInitialProgress = () => {
  const init = {};
  for (const step of PIPELINE_STEPS) {
    init[step.key] = { status: 'pending', progress: 0, message: '' };
  }
  return init;
};

const clampProgress = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
};

const toIsoTimestamp = (value) => {
  if (typeof value === 'string' && value.trim()) return value;
  return new Date().toISOString();
};

/**
 * Real-time job progress display.
 * Connects via FastAPI WebSocket (/ws/jobs/{jobId}?token=...)
 * and shows pipeline steps with progress.
 */
function JobProgress({ jobId, jobData, onCancel, onClose }) {
  const [progress, setProgress] = useState(() => makeInitialProgress());
  const [currentStep, setCurrentStep] = useState(null);
  const [logs, setLogs] = useState([]);
  const [showFullLogs, setShowFullLogs] = useState(false);
  const [errorDetailsOpen, setErrorDetailsOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const [connectionError, setConnectionError] = useState('');

  const [jobState, setJobState] = useState(() => ({
    status: jobData?.status ?? null,
    error_message: jobData?.error_message ?? '',
    last_successful_step: jobData?.last_successful_step ?? null,
    error_traceback: jobData?.error_traceback ?? '',
  }));

  const getStepIndex = (stepKey) => {
    return PIPELINE_STEPS.findIndex((s) => s.key === stepKey);
  };

  const getStepStatus = (step) => {
    const statusMap = {
      pending: 'pending',
      running: 'running',
      completed: 'completed',
      failed: 'failed',
    };

    return statusMap[progress[step.key]?.status] || 'pending';
  };

  useEffect(() => {
    setProgress(makeInitialProgress());
    setCurrentStep(null);
    setLogs([]);
    setShowFullLogs(false);
    setErrorDetailsOpen(false);
    setConnected(false);
    setConnectionError('');
    setJobState({
      status: jobData?.status ?? null,
      error_message: jobData?.error_message ?? '',
      last_successful_step: jobData?.last_successful_step ?? null,
      error_traceback: jobData?.error_traceback ?? '',
    });
  }, [jobId]);

  useEffect(() => {
    setJobState((prev) => ({
      ...prev,
      status: jobData?.status ?? prev.status,
      error_message: jobData?.error_message ?? prev.error_message,
      last_successful_step: jobData?.last_successful_step ?? prev.last_successful_step,
      error_traceback: jobData?.error_traceback ?? prev.error_traceback,
    }));
  }, [jobData?.status, jobData?.error_message, jobData?.last_successful_step, jobData?.error_traceback]);

  const appendLog = useCallback((entry) => {
    setLogs((prev) => {
      const next = [...prev, entry];
      return next.length > 1000 ? next.slice(-1000) : next;
    });
  }, []);

  const handleCancel = useCallback(async () => {
    if (onCancel) {
      await onCancel(jobId);
    }
    onClose();
  }, [jobId, onCancel, onClose]);

  const handleCopyLogs = useCallback(() => {
    const logsText = logs.map((log) => `[${log.timestamp}] ${log.message}`).join('\n');
    navigator.clipboard.writeText(logsText);
  }, [logs]);

  const handleProgressUpdate = useCallback((data) => {
    const step = typeof data?.step === 'string' ? data.step.trim() : '';
    if (!step) return;

    const pct = clampProgress(data?.progress);
    const message = data?.message ? String(data.message) : '';
    const timestamp = toIsoTimestamp(data?.timestamp);

    setCurrentStep(step);

    setProgress((prev) => {
      const next = { ...prev };
      if (!next[step]) {
        return prev;
      }

      const stepIdx = getStepIndex(step);
      if (stepIdx >= 0) {
        for (let i = 0; i < stepIdx; i++) {
          const k = PIPELINE_STEPS[i].key;
          const prevStep = next[k];
          if (!prevStep) continue;
          if (prevStep.status === 'pending' || prevStep.status === 'running') {
            next[k] = { ...prevStep, status: 'completed', progress: 100 };
          }
        }
      }

      next[step] = {
        ...next[step],
        status: pct >= 100 ? 'completed' : 'running',
        progress: pct,
        message,
      };

      return next;
    });

    if (message) {
      appendLog({ type: 'progress', timestamp, message });
    }
  }, [appendLog]);

  const handleStatusUpdate = useCallback((data) => {
    const status = data?.status ? String(data.status) : null;
    if (!status) return;

    const timestamp = toIsoTimestamp(data?.timestamp);
    setJobState((prev) => ({ ...prev, status }));
    appendLog({ type: 'status', timestamp, message: `Status: ${status}` });

    if (status === 'failed' && currentStep) {
      setProgress((prev) => {
        const next = { ...prev };
        if (next[currentStep]) {
          next[currentStep] = { ...next[currentStep], status: 'failed' };
        }
        return next;
      });
    }
  }, [appendLog, currentStep]);

  const handleJobError = useCallback((data) => {
    const errorMessage = data?.error_message ? String(data.error_message) : 'Job error';
    const traceback = data?.traceback ? String(data.traceback) : '';
    const timestamp = toIsoTimestamp(data?.timestamp);

    setJobState((prev) => ({
      ...prev,
      status: 'failed',
      error_message: errorMessage,
      error_traceback: traceback,
      last_successful_step: prev.last_successful_step ?? currentStep,
    }));

    appendLog({ type: 'error', timestamp, message: errorMessage });
  }, [appendLog, currentStep]);

  const handleJobCompleted = useCallback((data) => {
    const timestamp = toIsoTimestamp(data?.timestamp);
    setJobState((prev) => ({ ...prev, status: 'completed' }));
    appendLog({ type: 'status', timestamp, message: 'Job completed' });
  }, [appendLog]);

  const handleJobCancelled = useCallback((data) => {
    const timestamp = toIsoTimestamp(data?.timestamp);
    setJobState((prev) => ({ ...prev, status: 'cancelled' }));
    appendLog({ type: 'status', timestamp, message: 'Job cancelled' });
  }, [appendLog]);

  const handleWebSocketMessage = useCallback((data) => {
    const type = data?.type ? String(data.type) : '';
    switch (type) {
      case 'initial':
        setJobState((prev) => ({ ...prev, status: data?.status ?? prev.status }));
        return;
      case 'status':
        handleStatusUpdate(data);
        return;
      case 'progress':
        handleProgressUpdate(data);
        return;
      case 'error':
        handleJobError(data);
        return;
      case 'completed':
        handleJobCompleted(data);
        return;
      case 'cancelled':
        handleJobCancelled(data);
        return;
      case 'ping':
      case 'pong':
        return;
      default: {
        const msg = data?.message ? String(data.message) : '';
        if (!msg) return;
        appendLog({ type: 'info', timestamp: toIsoTimestamp(data?.timestamp), message: msg });
      }
    }
  }, [
    appendLog,
    handleJobCancelled,
    handleJobCompleted,
    handleJobError,
    handleProgressUpdate,
    handleStatusUpdate,
  ]);

  useEffect(() => {
    if (!jobId) return;

    const token = localStorage.getItem('token');
    if (!token) {
      setConnected(false);
      setConnectionError('Missing authentication token');
      return;
    }

    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${window.location.host}/ws/jobs/${jobId}?token=${encodeURIComponent(token)}`;

    let isUnmounted = false;
    let pingInterval = null;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (isUnmounted) return;
      setConnected(true);
      setConnectionError('');

      try {
        ws.send(JSON.stringify({ type: 'subscribe', job_id: jobId }));
      } catch {
        // Ignore
      }

      pingInterval = setInterval(() => {
        if (ws.readyState !== WebSocket.OPEN) return;
        try {
          ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        } catch {
          // Ignore
        }
      }, 25000);
    };

    ws.onclose = (event) => {
      if (isUnmounted) return;
      setConnected(false);
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }

      if (event?.code && event.code !== 1000) {
        setConnectionError(event.reason || `Connection closed (${event.code})`);
      }
    };

    ws.onerror = () => {
      if (isUnmounted) return;
      setConnectionError('Connection error');
    };

    ws.onmessage = (event) => {
      if (isUnmounted) return;
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch {
        // Ignore non-JSON payloads.
      }
    };

    return () => {
      isUnmounted = true;
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      try {
        ws.close(1000, 'Client closing');
      } catch {
        // Ignore
      }
    };
  }, [jobId, handleWebSocketMessage]);

  return (
    <Box>
      {/* Connection Status */}
      {connectionError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Connection error: {connectionError}
          <IconButton
            onClick={() => window.location.reload()}
            size="small"
            sx={{ ml: 1 }}
          >
            <RefreshIcon />
          </IconButton>
        </Alert>
      )}

      {connected && jobState.status === 'running' && (
        <Paper elevation={2}>
          <CardContent>
            {/* Stepper */}
            <Stepper activeStep={currentStep ? getStepIndex(currentStep) : -1} alternativeLabel>
              {PIPELINE_STEPS.map((step) => {
                const stepProgress = progress[step.key] || {};
                const stepStatus = getStepStatus(step);
                const isActive = currentStep === step.key;

                return (
                  <MuiStep key={step.key}>
                    <StepLabel
                      icon={
                        stepStatus === 'completed' ? <CheckCircleIcon color="success" /> :
                        stepStatus === 'failed' ? <ErrorIcon color="error" /> :
                          undefined
                      }
                    >
                      {step.label}
                    </StepLabel>
                    <LinearProgress
                      variant={isActive ? 'determinate' : 'buffer'}
                      value={stepProgress.progress}
                      sx={{
                        '& .MuiLinearProgress-bar': {
                          transitionDuration: '0.3s',
                        },
                      }}
                    />
                    {stepProgress.message && (
                      <Typography variant="caption" sx={{ ml: 1 }}>
                        {stepProgress.message}
                      </Typography>
                    )}
                  </MuiStep>
                );
              })}
            </Stepper>

            {/* Current Action */}
            <Box sx={{ mt: 3, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom>
                Current Action
              </Typography>
              {currentStep && (
                <Typography variant="body1">
                  {PIPELINE_STEPS[getStepIndex(currentStep)]?.label} is currently running...
                </Typography>
              )}
            </Box>

            {onCancel && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                <Button color="error" variant="outlined" onClick={handleCancel}>
                  Cancel Job
                </Button>
              </Box>
            )}
          </CardContent>
        </Paper>
      )}

      {connected && jobState.status === 'completed' && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={onClose}>
          Pipeline completed successfully! Dataset has been pushed to HuggingFace.
        </Alert>
      )}

      {connected && jobState.status === 'failed' && (
        <Paper elevation={2} sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <ErrorIcon color="error" sx={{ fontSize: 32 }} />
              <Typography variant="h5" color="error">
                Pipeline Failed
              </Typography>
            </Box>

            {jobState.error_message && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {jobState.error_message}
              </Alert>
            )}

            {jobState.last_successful_step && (
              <Box sx={{ p: 2, bgcolor: 'warning.light', borderRadius: 1 }}>
                <Typography variant="subtitle2">
                  Last successful step:
                </Typography>
                <Chip
                  label={jobState.last_successful_step}
                  color="primary"
                  variant="outlined"
                  sx={{ mt: 1 }}
                />
              </Box>
            )}

            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
              <Button
                variant="outlined"
                onClick={() => setErrorDetailsOpen(true)}
                disabled={!jobState.error_traceback}
              >
                View Error Log
              </Button>
              <Button
                variant="contained"
                onClick={() => window.location.href = `/dashboard`}
              >
                Back to Dashboard
              </Button>
            </Box>
          </CardContent>
        </Paper>
      )}

      {/* Logs */}
      {connected && logs.length > 0 && (
        <Paper elevation={2}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 2 }}>
            <Typography variant="h6">
              Progress Logs
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Copy logs to clipboard">
                <IconButton size="small" onClick={handleCopyLogs}>
                  <ContentCopyIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={showFullLogs ? 'Show recent only' : 'Show all logs'}>
                <IconButton size="small" onClick={() => setShowFullLogs(!showFullLogs)}>
                  {showFullLogs ? <VisibilityOffIcon /> : <VisibilityIcon />}
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
          <Divider />

          <List sx={{ maxHeight: 400, overflow: 'auto' }}>
            {(showFullLogs ? logs : logs.slice(-20)).map((log, index) => (
              <React.Fragment key={index}>
                <ListItem>
                  <ListItemText
                    primary={`[${new Date(log.timestamp).toLocaleTimeString()}] ${log.message}`}
                    secondary={formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                  />
                  {log.type === 'error' && (
                    <Alert severity="error" sx={{ mt: 1 }}>
                      {log.message}
                    </Alert>
                  )}
                </ListItem>
                {index !== logs.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>

          {logs.length > 20 && !showFullLogs && (
            <Box sx={{ textAlign: 'center', p: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Showing last 20 logs. Click the eye icon to show all.
              </Typography>
            </Box>
          )}
        </Paper>
      )}

      {/* Error Details Dialog */}
      <Dialog
        open={errorDetailsOpen}
        onClose={() => setErrorDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Error Details</DialogTitle>
        <DialogContent dividers>
          {jobState.error_traceback && (
            <Box sx={{ p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Stack Trace
              </Typography>
              <Typography
                component="pre"
                sx={{
                  bgcolor: '#f5f5f5',
                  p: 2,
                  borderRadius: 1,
                  maxHeight: 400,
                  overflow: 'auto',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  color: 'error.dark',
                }}
              >
                {jobState.error_traceback}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setErrorDetailsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default JobProgress;

