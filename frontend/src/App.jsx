import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';

import Layout from './components/Layout/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import SettingsPage from './pages/SettingsPage';
import RunPipelinePage from './pages/RunPipelinePage';

import { AuthProvider, useAuth } from './context/AuthContext';

function AppRoutes() {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Show loading while checking auth
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <Layout>
            <LoginPage />
          </Layout>
        }
      />
      <Route
        path="/register"
        element={
          <Layout>
            <RegisterPage />
          </Layout>
        }
      />
      <Route
        path="/"
        element={
          <Layout requireAuth>
            <DashboardPage />
          </Layout>
        }
      />
      <Route
        path="/dashboard"
        element={
          <Layout requireAuth>
            <DashboardPage />
          </Layout>
        }
      />
      <Route
        path="/settings"
        element={
          <Layout requireAuth>
            <SettingsPage />
          </Layout>
        }
      />
      <Route
        path="/pipeline/run"
        element={
          <Layout requireAuth>
            <RunPipelinePage />
          </Layout>
        }
      />
      <Route
        path="/pipeline/:jobId"
        element={
          <Layout requireAuth>
            <RunPipelinePage />
          </Layout>
        }
      />
      <Route
        path="*"
        element={<Navigate to="/" replace />}
      />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;