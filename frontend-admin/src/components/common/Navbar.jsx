import React from 'react';
import { Shield, PlayCircle, LogOut, UserCircle, Activity } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Navbar = ({ onOpenSimulate }) => {
  const { user, logout } = useAuth();

  return (
    <header style={{
      height: '64px',
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(8, 12, 20, 0.85)',
      backdropFilter: 'blur(12px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 28px',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#04101e',
            fontWeight: 800,
            fontSize: '1.1rem',
          }}>
            Z
          </div>
          <div>
            <span style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '-0.02em', color: '#fff' }}>ZenAlgo</span>
            <span style={{ fontSize: '0.75rem', marginLeft: '6px', color: 'var(--accent-cyan)', fontWeight: 700 }}>PRO PLATFORM</span>
          </div>
        </div>

        <div style={{ height: '20px', width: '1px', background: 'var(--border-subtle)', margin: '0 8px' }}></div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'rgba(16, 185, 129, 0.1)',
          padding: '4px 10px',
          borderRadius: '9999px',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          fontSize: '0.75rem',
          color: 'var(--accent-emerald)',
          fontWeight: 600,
        }}>
          <span className="pulse-active"></span>
          <span>AUTONOMOUS ENGINE ACTIVE</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <button
          onClick={onOpenSimulate}
          className="btn btn-primary"
          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
        >
          <PlayCircle size={16} />
          <span>Simulate 5m Candle & Execution</span>
        </button>

        <div style={{ height: '24px', width: '1px', background: 'var(--border-subtle)' }}></div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
              {user?.email || 'superadmin@trading.com'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              {user?.role || 'SUPER_ADMIN'}
            </div>
          </div>

          <button
            onClick={logout}
            title="Logout"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '8px',
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
