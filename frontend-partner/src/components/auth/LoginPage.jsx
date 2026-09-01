import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Handshake, TrendingUp, User, Lock, Mail, ArrowRight, ShieldCheck, Zap } from 'lucide-react';

export const LoginPage = () => {
  const { login } = useAuth();
  const { addToast } = useToast();
  
  const [selectedRole, setSelectedRole] = useState('PARTNER'); // 'PARTNER' | 'TRADER' | 'USER'
  const [email, setEmail] = useState('partner@trading.com');
  const [password, setPassword] = useState('partner123');
  const [loading, setLoading] = useState(false);

  const handleRoleSelect = (role) => {
    setSelectedRole(role);
    if (role === 'PARTNER') {
      setEmail('partner@trading.com');
      setPassword('partner123');
    } else if (role === 'TRADER') {
      setEmail('trader@example.com');
      setPassword('password123');
    } else {
      setEmail('user@trading.com');
      setPassword('user123');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      addToast(`Welcome back, ${email.split('@')[0]}!`, 'success');
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Login failed. Please check credentials.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(ellipse at top, #0f172a 0%, #05080f 100%)',
        padding: '20px',
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '460px',
          padding: '36px 32px',
          border: '1px solid var(--border-highlight)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '54px',
              height: '54px',
              borderRadius: '12px',
              background: selectedRole === 'PARTNER'
                ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                : 'linear-gradient(135deg, #0284c7 0%, #10b981 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              margin: '0 auto 16px auto',
              boxShadow: '0 0 20px rgba(56, 189, 248, 0.3)',
            }}
          >
            {selectedRole === 'PARTNER' ? <Handshake size={28} /> : <TrendingUp size={28} />}
          </div>

          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
            Zen<span style={{ color: selectedRole === 'PARTNER' ? 'var(--accent-amber)' : 'var(--accent-cyan)' }}>Algo</span>
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '4px' }}>
            {selectedRole === 'PARTNER' ? 'Partner Affiliate & Sub-Broker Portal' : 'Trader Execution Client Portal'}
          </p>
        </div>

        {/* Role Switcher Tabs */}
        <div>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px', display: 'block' }}>
            Select Portal Account Role:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
            <button
              type="button"
              onClick={() => handleRoleSelect('PARTNER')}
              style={{
                background: selectedRole === 'PARTNER' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${selectedRole === 'PARTNER' ? 'var(--accent-amber)' : 'var(--border-subtle)'}`,
                color: selectedRole === 'PARTNER' ? '#fff' : 'var(--text-muted)',
                fontWeight: selectedRole === 'PARTNER' ? 700 : 500,
                padding: '8px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
              }}
            >
              <Handshake size={14} />
              <span>PARTNER</span>
            </button>

            <button
              type="button"
              onClick={() => handleRoleSelect('TRADER')}
              style={{
                background: selectedRole === 'TRADER' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${selectedRole === 'TRADER' ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                color: selectedRole === 'TRADER' ? '#fff' : 'var(--text-muted)',
                fontWeight: selectedRole === 'TRADER' ? 700 : 500,
                padding: '8px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
              }}
            >
              <TrendingUp size={14} />
              <span>TRADER</span>
            </button>

            <button
              type="button"
              onClick={() => handleRoleSelect('USER')}
              style={{
                background: selectedRole === 'USER' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${selectedRole === 'USER' ? 'var(--accent-emerald)' : 'var(--border-subtle)'}`,
                color: selectedRole === 'USER' ? '#fff' : 'var(--text-muted)',
                fontWeight: selectedRole === 'USER' ? 700 : 500,
                padding: '8px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
              }}
            >
              <User size={14} />
              <span>CLIENT</span>
            </button>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Email Address</label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                required
                style={{ paddingLeft: '36px' }}
              />
              <Mail size={16} style={{ position: 'absolute', left: '10px', color: 'var(--text-dim)' }} />
            </div>
          </div>

          <div>
            <label>Password</label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                required
                style={{ paddingLeft: '36px' }}
              />
              <Lock size={16} style={{ position: 'absolute', left: '10px', color: 'var(--text-dim)' }} />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`btn ${selectedRole === 'PARTNER' ? 'btn-amber' : 'btn-primary'}`}
            style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: '0.95rem', marginTop: '6px' }}
          >
            <span>{loading ? 'Authenticating...' : `Sign In as ${selectedRole}`}</span>
            <ArrowRight size={16} />
          </button>
        </form>

        {/* Quick Demo Help */}
        <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-dim)', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          🔒 Protected by Argon2id Cryptographic Session Authentication
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
