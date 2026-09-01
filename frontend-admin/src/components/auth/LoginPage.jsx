import React, { useState } from 'react';
import { Lock, Mail, Shield, ArrowRight, UserCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export const LoginPage = () => {
  const { loginAdmin, loading } = useAuth();
  const { addToast } = useToast();
  const [email, setEmail] = useState('superadmin@trading.com');
  const [password, setPassword] = useState('superadmin123');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const res = await loginAdmin(email, password);
    if (res.success) {
      addToast('Welcome back, Super Admin!', 'success');
    } else {
      addToast(res.message || 'Login failed', 'error');
    }
  };

  const handleQuickLogin = async (quickEmail, quickPass) => {
    setEmail(quickEmail);
    setPassword(quickPass);
    const res = await loginAdmin(quickEmail, quickPass);
    if (res.success) {
      addToast('Signed in successfully!', 'success');
    } else {
      addToast(res.message || 'Login failed', 'error');
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at top, #0f172a 0%, #080c14 100%)',
      padding: '20px',
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '440px',
        padding: '36px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)',
        border: '1px solid var(--border-highlight)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#04101e',
            fontWeight: 800,
            fontSize: '1.5rem',
            margin: '0 auto 12px',
          }}>
            Z
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff' }}>ZenAlgo Portal</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '4px' }}>
            Institutional Algorithmic Trading Admin Center
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <div>
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '0.95rem', marginTop: '8px' }}
          >
            <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
            <ArrowRight size={18} />
          </button>
        </form>

        {/* 1-Click Demo Buttons */}
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textAlign: 'center', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            1-Click Presentation Sign-In
          </div>
          <button
            type="button"
            onClick={() => handleQuickLogin('superadmin@trading.com', 'superadmin123')}
            className="btn btn-emerald"
            style={{ width: '100%', padding: '8px', fontSize: '0.8rem' }}
          >
            <Shield size={14} />
            <span>Login as Super Admin</span>
          </button>
        </div>

        <div style={{
          marginTop: '24px',
          paddingTop: '18px',
          borderTop: '1px solid var(--border-subtle)',
          textAlign: 'center',
          fontSize: '0.75rem',
          color: 'var(--text-dim)',
        }}>
          FastAPI Backend • Schema v2.0.0 • Connected to Port 8000
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
