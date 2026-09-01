import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogOut, User, Shield, Zap, Sparkles, ChevronDown, CheckCircle2, TrendingUp, Handshake } from 'lucide-react';

export const Navbar = () => {
  const { user, logout, switchRoleDemo } = useAuth();
  const isPartner = user?.role === 'PARTNER';

  return (
    <header
      className="glass-panel"
      style={{
        height: 'var(--navbar-height)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: 'rgba(9, 13, 22, 0.9)',
      }}
    >
      {/* Brand Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '8px',
              background: isPartner
                ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                : 'linear-gradient(135deg, #0284c7 0%, #10b981 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 800,
              boxShadow: isPartner ? '0 0 15px rgba(245, 158, 11, 0.4)' : '0 0 15px rgba(2, 132, 199, 0.4)',
            }}
          >
            {isPartner ? <Handshake size={20} /> : <TrendingUp size={20} />}
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '-0.5px', color: '#fff' }}>
              Zen<span style={{ color: isPartner ? 'var(--accent-amber)' : 'var(--accent-cyan)' }}>Algo</span>
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
              {isPartner ? 'Partner & Affiliate Hub' : 'Trader Execution Portal'}
            </div>
          </div>
        </div>

        {/* Dynamic Role Badge */}
        <span
          className="badge"
          style={{
            background: isPartner ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
            color: isPartner ? 'var(--accent-amber)' : 'var(--accent-emerald)',
            border: `1px solid ${isPartner ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
            padding: '4px 10px',
            fontSize: '0.75rem',
            fontWeight: 800,
          }}
        >
          {isPartner ? '🤝 PARTNER / SUB-BROKER' : user?.role === 'TRADER' ? '⚡ TRADER ACCOUNT' : '👤 CLIENT USER'}
        </span>
      </div>

      {/* Role Switcher & User Profile Menu */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        
        {/* Quick Role Tester Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.8)', padding: '4px 8px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Role Switcher:</span>
          <select
            value={user?.role || 'PARTNER'}
            onChange={(e) => switchRoleDemo(e.target.value)}
            className="input-field"
            style={{ padding: '2px 6px', fontSize: '0.75rem', width: '110px' }}
          >
            <option value="PARTNER">PARTNER</option>
            <option value="TRADER">TRADER</option>
            <option value="USER">USER</option>
          </select>
        </div>

        {/* User Identity Chip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '50%',
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid var(--border-highlight)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-cyan)',
              fontWeight: 700,
              fontSize: '0.85rem',
            }}
          >
            {user?.email?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
              {user?.firstName || user?.email?.split('@')[0]}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              {user?.email}
            </div>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          className="btn btn-secondary"
          style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          title="Sign out of portal"
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </div>
    </header>
  );
};
