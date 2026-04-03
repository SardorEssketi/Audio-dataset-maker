import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);
const API_BASE_URL = '/api';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token') || null);

  useEffect(() => {
    const interceptor = axios.interceptors.request.use(
      (config) => {
        const storedToken = localStorage.getItem('token');
        if (storedToken) {
          config.headers.Authorization = `Bearer ${storedToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(interceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, []);

  useEffect(() => {
    const loadUser = async () => {
      const storedToken = localStorage.getItem('token');

      if (!storedToken) {
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(`${API_BASE_URL}/auth/me`);
        setUser(response.data);
        setToken(storedToken);
      } catch (error) {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = useCallback(async (username, password) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/login`, {
        username: String(username).trim(),
        password: String(password),
      });

      const { access_token } = response.data;

      localStorage.setItem('token', access_token);
      setToken(access_token);

      const userResponse = await axios.get(`${API_BASE_URL}/auth/me`);
      setUser(userResponse.data);

      return { success: true };
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      const err = new Error(message);
      err.response = error.response;
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (username, email, password) => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/auth/register`, {
        username: String(username).trim(),
        email: email ? String(email).trim() : null,
        password: String(password),
      });

      await login(username, password);

      return { success: true };
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed';
      const err = new Error(message);
      err.response = error.response;
      throw err;
    } finally {
      setLoading(false);
    }
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  }, []);

  const updateUser = useCallback(async (updates) => {
    const response = await axios.put(`${API_BASE_URL}/auth/me`, updates);
    setUser(response.data);
  }, []);

  const value = {
    user,
    loading,
    token,
    login,
    register,
    logout,
    updateUser,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export default AuthContext;