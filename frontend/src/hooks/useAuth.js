import { useContext, useCallback } from 'react';
import { AuthContext } from '../context/AuthContext';

/**
 * Custom hook for authentication state and actions.
 * Provides easy access to auth context with automatic context validation.
 */
export const useAuth = () => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  const {
    user,
    loading,
    token,
    login,
    register,
    logout,
    updateUser,
    isAuthenticated,
  } = context;

  return {
    // State
    user,
    loading,
    token,
    isAuthenticated,

    // Actions
    login: useCallback(login, [login]),
    register: useCallback(register, [register]),
    logout: useCallback(logout, [logout]),
    updateUser: useCallback(updateUser, [updateUser]),
  };
};

export default useAuth;
