import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  RadioGroup,
  FormControlLabel,
  Radio,
  Paper,
  Switch,
  Alert,
  Divider,
  Grid,
  Card,
  CardContent,
  Button,
  Tooltip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  YouTube as YouTubeIcon,
  Description as DescriptionIcon,
  Storage as StorageIcon,
  Hub as HubIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

/**
 * Source type selector for pipeline run.
 * Provides different input forms for each source type (URL, YouTube, JSON, HuggingFace, Local).
 */
function SourceSelector({ sourceType, sourceValue, onChange, uploadedFiles, onUpload }) {
  const [localFiles, setLocalFiles] = useState([]);

  const handleChange = (field) => (event) => {
    onChange(field, event.target.value);
  };

  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    setLocalFiles(files);
    if (onUpload) {
      onUpload(files);
    }
  };

  const renderUrlSource = () => (
    <Box>
      <TextField
        fullWidth
        label="Audio URL"
        placeholder="https://example.com/audio.mp3"
        value={sourceValue || ''}
        onChange={handleChange('source_value')}
        helperText="Direct URL to an audio file (mp3, wav, flac, etc.)"
      />
      <Alert severity="info" sx={{ mt: 2 }}>
        <InfoIcon sx={{ mr: 1, fontSize: 'small' }} />
        The pipeline will download audio from the provided URL.
      </Alert>
    </Box>
  );

  const renderYoutubeSource = () => (
    <Box>
      <TextField
        fullWidth
        label="YouTube URL or Playlist"
        placeholder="https://www.youtube.com/watch?v=xxx"
        value={sourceValue || ''}
        onChange={handleChange('source_value')}
        helperText="YouTube video or playlist URL"
      />
      <Alert severity="info" sx={{ mt: 2 }}>
        <InfoIcon sx={{ mr: 1, fontSize: 'small' }} />
        Supports both single videos and playlists. yt-dlp will download the best audio quality.
      </Alert>
    </Box>
  );

  const renderJsonSource = () => (
    <Box>
      <TextField
        fullWidth
        label="JSON File Path"
        placeholder="/path/to/urls.json"
        value={sourceValue || ''}
        onChange={handleChange('source_value')}
        helperText="Path to JSON file containing list of audio URLs"
      />
      <Alert severity="info" sx={{ mt: 2 }}>
        <InfoIcon sx={{ mr: 1, fontSize: 'small' }} />
        JSON file should contain an array of URLs or an object with a "urls" or "audio" field.
      </Alert>
    </Box>
  );

  const renderHuggingFaceSource = () => (
    <Box>
      <TextField
        fullWidth
        label="HuggingFace Dataset"
        placeholder="username/dataset-name"
        value={sourceValue || ''}
        onChange={handleChange('source_value')}
        helperText="Dataset name on HuggingFace (e.g., mozilla-foundation/common_voice)"
      />
      <Alert severity="info" sx={{ mt: 2 }}>
        <InfoIcon sx={{ mr: 1, fontSize: 'small' }} />
        Pipeline will download audio files from the specified HuggingFace dataset.
      </Alert>
    </Box>
  );

  const renderLocalSource = () => (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Local Directory Path
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Leave empty to use files uploaded through the file upload option below.
        </Typography>
      </Box>

      <TextField
        fullWidth
        label="Directory Path (optional)"
        placeholder="C:\\path\\to\\audio_files"
        value={sourceValue || ''}
        onChange={handleChange('source_value')}
        helperText="If set, the server will read audio files from this directory."
        sx={{ mb: 2 }}
      />

      {uploadedFiles && uploadedFiles.length > 0 && (
        <>
          <Alert severity="success" sx={{ mb: 2 }}>
            <CloudUploadIcon sx={{ mr: 1 }} />
            {uploadedFiles.length} file(s) uploaded. Ready to process.
          </Alert>
          <List>
            {uploadedFiles.map((file, index) => (
              <ListItem key={index}>
                <ListItemText
                  primary={file.name}
                  secondary={`${(file.size / 1024).toFixed(2)} KB`}
                />
              </ListItem>
            ))}
          </List>
          <Button
            fullWidth
            variant="outlined"
            onClick={() => onUpload([])}
            sx={{ mt: 2 }}
          >
            Clear Files
          </Button>
        </>
      )}

      {!uploadedFiles || uploadedFiles.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <CloudUploadIcon sx={{ mr: 1 }} />
          No files uploaded. Upload audio files or leave empty to use local directory.
        </Alert>
      )}

      <Box sx={{ mt: 3 }}>
        <Button
          variant="outlined"
          startIcon={<CloudUploadIcon />}
          onClick={() => document.getElementById('file-upload').click()}
        disabled={uploadedFiles.length >= 5}
        fullWidth
        sx={{ height: 100 }}
        >
          Upload Audio Files
        </Button>
        <input
          id="file-upload"
          type="file"
          multiple
          accept=".wav,.mp3,.flac,.m4a,.ogg,.opus"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </Box>
    </Box>
  );

  const renderSourceSelector = () => {
    switch (sourceType) {
      case 'url':
        return renderUrlSource();
      case 'youtube':
        return renderYoutubeSource();
      case 'json':
        return renderJsonSource();
      case 'huggingface':
        return renderHuggingFaceSource();
      case 'local':
        return renderLocalSource();
      default:
        return <Typography>Please select a source type</Typography>;
    }
  };

  return (
    <Paper elevation={2}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            <StorageIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Audio Source
          </Typography>
        </Box>

        <RadioGroup
          value={sourceType}
          onChange={handleChange('source_type')}
        >
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                value="url"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <CloudUploadIcon sx={{ mr: 1 }} />
                    Direct URL
                  </Box>
                }
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                value="youtube"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <YouTubeIcon sx={{ mr: 1 }} />
                    YouTube
                  </Box>
                }
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                value="json"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <DescriptionIcon sx={{ mr: 1 }} />
                    JSON File
                  </Box>
                }
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                value="huggingface"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <HubIcon sx={{ mr: 1 }} />
                    HuggingFace Dataset
                  </Box>
                }
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                value="local"
                control={<Radio />}
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <StorageIcon sx={{ mr: 1 }} />
                    Local Files
                  </Box>
                }
              />
            </Grid>
          </Grid>
        </RadioGroup>

        <Divider sx={{ my: 3 }} />

        <Typography variant="subtitle2" gutterBottom>
          Source Configuration
        </Typography>
        {renderSourceSelector()}
      </CardContent>
    </Paper>
  );
}

export default SourceSelector;
