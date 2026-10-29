import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, setTokens, getAccessToken, getRefreshToken, clearTokens } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(getAccessToken() || getRefreshToken()));
  const [userEmail, setUserEmail] = useState(sessionStorage.getItem('ai_user_email') || '');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Try restoring session from refresh token on startup
    const initAuth = async () => {
      const refresh = getRefreshToken();
      if (refresh) {
        try {
          const resp = await api.post('/auth/token/refresh/', { refresh });
          setTokens(resp.data.access, resp.data.refresh || refresh);
          setIsAuthenticated(true);
        } catch {
          clearTokens();
          setIsAuthenticated(false);
          setUserEmail('');
        }
      }
      setLoading(false);
    };

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setUserEmail('');
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
    return resp.data;
  };

  const logout = () => {
    clearTokens();
    setIsAuthenticated(false);
    setUserEmail('');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, userEmail, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
