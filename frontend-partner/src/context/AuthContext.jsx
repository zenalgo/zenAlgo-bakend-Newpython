import React, { createContext, useContext, useState, useEffect } from 'react';
import axiosClient from '../api/axiosClient';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedUser = localStorage.getItem('zenalgo_partner_user');
    const token = localStorage.getItem('zenalgo_partner_token');
    if (storedUser && token) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (err) {
        console.error('Failed to parse user session', err);
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const res = await axiosClient.post('/auth/login', { email, password });
    const data = res.data;
    if (data && data.accessToken) {
      localStorage.setItem('zenalgo_partner_token', data.accessToken);
      const userObj = {
        email: data.email,
        role: data.role,
        firstName: data.email.split('@')[0].toUpperCase(),
      };
      localStorage.setItem('zenalgo_partner_user', JSON.stringify(userObj));
      setUser(userObj);
      return userObj;
    }
    throw new Error('Authentication failed');
  };

  const logout = () => {
    localStorage.removeItem('zenalgo_partner_token');
    localStorage.removeItem('zenalgo_partner_user');
    setUser(null);
  };

  const switchRoleDemo = (role) => {
    const userObj = {
      email: role === 'PARTNER' ? 'partner@trading.com' : role === 'TRADER' ? 'trader@example.com' : 'user@trading.com',
      role: role,
      firstName: role === 'PARTNER' ? 'Vikram Mehta (Partner)' : role === 'TRADER' ? 'Arjun Trader' : 'Client User',
    };
    localStorage.setItem('zenalgo_partner_user', JSON.stringify(userObj));
    setUser(userObj);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, loading, login, logout, switchRoleDemo }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
