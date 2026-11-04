import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, setTokens, getAccessToken, getRefreshToken, clearTokens } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(getAccessToken() || getRefreshToken()));
  const [userEmail, setUserEmail] = useState(sessionStorage.getItem('ai_user_email') || '');
  const [userRole, setUserRole] = useState(sessionStorage.getItem('ai_user_role') || 'recruiter');
  const [loading, setLoading] = useState(true);

  const fetchUserProfile = async () => {
    try {
      const resp = await api.get('/auth/me/');
      if (resp.data?.email) {
        setUserEmail(resp.data.email);
        sessionStorage.setItem('ai_user_email', resp.data.email);
      }
      if (resp.data?.role) {
        setUserRole(resp.data.role);
        sessionStorage.setItem('ai_user_role', resp.data.role);
      }
      return resp.data;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    // Try restoring session from refresh token on startup
    const initAuth = async () => {
      const refresh = getRefreshToken();
      if (refresh) {
        try {
          const resp = await api.post('/auth/token/refresh/', { refresh });
          setTokens(resp.data.access, resp.data.refresh || refresh);
          setIsAuthenticated(true);
          await fetchUserProfile();
        } catch {
          clearTokens();
          setIsAuthenticated(false);
          setUserEmail('');
          setUserRole('recruiter');
          sessionStorage.removeItem('ai_user_role');
        }
      }
      setLoading(false);
    };

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setUserEmail('');
      setUserRole('recruiter');
      sessionStorage.removeItem('ai_user_role');
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    initAuth();

    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, []);

  const login = async (email, password) => {
    const resp = await api.post('/auth/token/', { email, password });
    setTokens(resp.data.access, resp.data.refresh);
    sessionStorage.setItem('ai_user_email', email);
    setUserEmail(email);
    setIsAuthenticated(true);
    const profile = await fetchUserProfile();
    return { ...resp.data, role: profile?.role || 'recruiter' };
  };

  const logout = () => {
    clearTokens();
    sessionStorage.removeItem('ai_user_role');
    setIsAuthenticated(false);
    setUserEmail('');
    setUserRole('recruiter');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, userEmail, userRole, loading, login, logout, isAdmin: userRole === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
