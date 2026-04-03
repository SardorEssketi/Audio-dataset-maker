import { useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = '/api/config';

/**
 * Custom hook for user configuration management.
 * Handles loading, saving, and masking of sensitive values.
 */
export const useConfig = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await axios.get(API_BASE);
      setConfig(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load configuration');
      setConfig(null);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async (updates) => {
    setSaving(true);
    setError('');

    try {
      await axios.put(API_BASE, updates);
      // Reload config to get fresh data
      await loadConfig();
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Failed to save configuration';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    if (!window.confirm('Reset all settings to defaults?')) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      await axios.delete(API_BASE);
      await loadConfig();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset configuration');
    } finally {
      setLoading(false);
    }
  };

  const saveHuggingFaceToken = async (token) => {
    setSaving(true);
    setError('');

    try {
      await axios.put(`${API_BASE}/huggingface/token`, { token });
      await loadConfig();
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Failed to save HuggingFace token';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const deleteHuggingFaceToken = async () => {
    setSaving(true);
    setError('');

    try {
      await axios.delete(`${API_BASE}/huggingface/token`);
      await loadConfig();
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Failed to delete HuggingFace token';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  return {
    config,
    loading,
    saving,
    error,
    loadConfig,
    saveConfig,
    resetConfig,
    saveHuggingFaceToken,
    deleteHuggingFaceToken,
  };
};

export default useConfig;