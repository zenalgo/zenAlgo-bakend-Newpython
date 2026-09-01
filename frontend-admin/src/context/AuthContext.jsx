import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api/authApi';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('zenalgo_token') || null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // If token exists, restore user profile state
    if (token) {
      const savedEmail = localStorage.getItem('zenalgo_user_email') || 'superadmin@trading.com';
      const savedRole = localStorage.getItem('zenalgo_user_role') || 'SUPER_ADMIN';
      setUser({ email: savedEmail, role: savedRole });
    }
  }, [token]);

  const loginAdmin = async (email, password) => {
    setLoading(true);
    try {
      const res = await authApi.adminLogin(email, password);
      if (res.data?.accessToken) {
        const access = res.data.accessToken;
        localStorage.setItem('zenalgo_token', access);
        localStorage.setItem('zenalgo_user_email', email);
        localStorage.setItem('zenalgo_user_role', 'SUPER_ADMIN');
        setToken(access);
        setUser({ email, role: 'SUPER_ADMIN' });
        return { success: true };
      }
      return { success: false, message: 'Invalid token response' };
    } catch (err) {
      return { success: false, message: err.message || 'Login failed' };
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('zenalgo_token');
    localStorage.removeItem('zenalgo_user_email');
    localStorage.removeItem('zenalgo_user_role');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, loginAdmin, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
