import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Slider,
  FormControlLabel,
  Switch,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  Chip,
} from '@mui/material';
import {
  CloudDownload as CloudDownloadIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
} from '@mui/icons-material';

/**
 * Download settings form.
 * Max workers, scrape toggle, interval, sources with keywords management.
 */
function DownloadSettings({ config, onScrollToTop }) {
  const [formData, setFormData] = useState({
    max_workers: config.max_workers || 4,
    scrape_enabled: config.scrape_enabled || false,
    scrape_interval_minutes: config.scrape_interval_minutes || 180,
    sources: config.sources || [],
  });

  const [newKeyword, setNewKeyword] = useState('');

  const handleChange = (field) => (event) => {
    setFormData((prev) => ({
      ...prev,
      [field]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    }));
  };

  const handleAddKeyword = () => {
    if (newKeyword.trim()) {
      setFormData((prev) => ({
        ...prev,
        sources: {
          ...prev.sources,
          include_keywords: [
            ...(prev.sources.include_keywords || []),
            newKeyword.trim(),
          ],
        },
      }));
      setNewKeyword('');
    }
  };

  const handleRemoveKeyword = (keyword) => {
    setFormData((prev) => ({
      ...prev,
      sources: {
        ...prev.sources,
        include_keywords: prev.sources.include_keywords.filter(k => k !== keyword),
      },
    }));
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        <CloudDownloadIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Download Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Max Workers */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Max Concurrent Downloads
              </Typography>
              <TextField
                fullWidth
                type="number"
                label="Workers"
                value={formData.max_workers}
                onChange={(e) => handleChange('max_workers')}
                inputProps={{ min: 1, max: 10 }}
                helperText="Maximum concurrent download workers (1-10)"
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Scrape Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.scrape_enabled}
                    onChange={(e) => handleChange('scrape_enabled')}
                  />
                }
                label="Enable Auto-Scraping"
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                Automatically scrape sources at intervals
              </Typography>

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" gutterBottom>
                  Scrape Interval (minutes)
                </Typography>
                <Slider
                  value={formData.scrape_interval_minutes}
                  onChange={(e) => handleChange('scrape_interval_minutes')}
                  min={5}
                  max={1440}
                  step={5}
                  marks={[
                    { value: 5, label: '5 min' },
                    { value: 60, label: '1 hour' },
                    { value: 180, label: '3 hours' },
                    { value: 360, label: '6 hours' },
                    { value: 720, label: '12 hours' },
                    { value: 1440, label: '24 hours' },
                  ]}
                  valueLabelDisplay="value"
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                  {formData.scrape_interval_minutes} minutes
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Keywords */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Include Keywords Filter
              </Typography>
              <Typography variant="caption" color="text.secondary" paragraph>
                Videos/files containing these keywords will be included in scraping.
                Leave empty to include all content.
              </Typography>

              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="Add keyword..."
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && newKeyword.trim()) {
                      handleAddKeyword();
                    }
                  }}
                  InputProps={{
                    endAdornment: (
                      <Button
                        size="small"
                        onClick={handleAddKeyword}
                        disabled={!newKeyword.trim()}
                      >
                        <AddIcon />
                      </Button>
                    ),
                  }}
                />
              </Box>

              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {formData.sources?.include_keywords?.map((keyword) => (
                  <Chip
                    key={keyword}
                    label={keyword}
                    onDelete={() => handleRemoveKeyword(keyword)}
                    deleteIcon={<RemoveIcon fontSize="small" />}
                    variant="outlined"
                  />
                ))}
                {(!formData.sources?.include_keywords || formData.sources.include_keywords.length === 0) && (
                  <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    No keywords set - all content will be included
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default DownloadSettings;