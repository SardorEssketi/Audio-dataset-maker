import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { useConfig } from '../hooks/useConfig';

// Import setting components
import HFSettings from '../components/Settings/HFSettings';
import DownloadSettings from '../components/Settings/DownloadSettings';
import ProcessingSettings from '../components/Settings/ProcessingSettings';
import AdditionalOptions from '../components/Settings/AdditionalOptions';

/**
 * Settings page with tabs for different configuration categories.
 */
function SettingsPage() {
  const {
    config,
    loading,
    saving,
    error,
    loadConfig,
    resetConfig,
  } = useConfig();

  const [activeTab, setActiveTab] = useState(0);
  const [additionalOptionsOpen, setAdditionalOptionsOpen] = useState(false);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleOpenAdditionalOptions = () => {
    setAdditionalOptionsOpen(true);
  };

  const handleCloseAdditionalOptions = () => {
    setAdditionalOptionsOpen(false);
    loadConfig(); // Reload to get fresh data
  };

  const handleReset = async () => {
    try {
      await resetConfig();
    } catch (err) {
      // Error is already handled in useConfig
    }
  };

  if (loading && !config) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <SettingsIcon fontSize="large" />
          <Typography variant="h4" component="div">
            Settings
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleOpenAdditionalOptions}
            disabled={loading}
          >
            Additional Options
          </Button>
          <Button
            variant="outlined"
            color="error"
            onClick={handleReset}
            disabled={loading || saving}
          >
            Reset to Defaults
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => {}}>
          {error}
        </Alert>
      )}

      {/* Settings Tabs */}
      <Paper elevation={2}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTabs-scrollButtons': {
              '& .MuiTabScrollButton-root': {
                color: 'primary.main',
              },
            },
          }}
        >
          <Tab label="Hugging Face" />
          <Tab label="Download" />
          <Tab label="Processing" />
        </Tabs>

        {saving && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={24} />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Saving changes...
            </Typography>
          </Box>
        )}
      </Paper>

      {/* Tab Content */}
      <Paper elevation={2} sx={{ mt: 2, minHeight: 400 }}>
        {activeTab === 0 && config && (
          <HFSettings config={config.huggingface || {}} onSave={loadConfig} />
        )}

        {activeTab === 1 && config && (
          <DownloadSettings config={config.download || {}} onScrollToTop={handleReset} />
        )}

        {activeTab === 2 && config && (
          <ProcessingSettings config={config} onScrollToTop={handleReset} />
        )}
      </Paper>

      {/* Additional Options Dialog */}
      <Dialog
        open={additionalOptionsOpen}
        onClose={handleCloseAdditionalOptions}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Typography variant="h6">
            Additional Options
          </Typography>
        </DialogTitle>

        <DialogContent dividers>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" paragraph>
              Advanced configuration options that are not shown in the main settings.
              These are optional and typically do not need to be modified.
            </Typography>

            {config && (
              <AdditionalOptions
                config={config}
                onClose={handleCloseAdditionalOptions}
              />
            )}
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleCloseAdditionalOptions}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}

export default SettingsPage;
