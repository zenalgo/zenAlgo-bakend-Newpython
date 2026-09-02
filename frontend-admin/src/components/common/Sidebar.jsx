import React from 'react';
import {
  LayoutDashboard,
  Zap,
  Cpu,
  Package,
  Layers,
  CreditCard,
  Wallet,
  Users,
  ShieldCheck,
  Building2,
  CheckCircle2,
} from 'lucide-react';

export const Sidebar = ({ currentTab, onSelectTab }) => {
  const navItems = [
    { id: 'dashboard', label: 'Platform Overview', icon: LayoutDashboard },
    { id: 'strategies', label: 'Strategy Management', icon: Zap },
    { id: 'builder', label: 'Strategy Builder & AI', icon: Cpu },
    { id: 'placed-orders', label: 'Placed Orders & Positions', icon: Package, badge: 'Live' },
    { id: 'batches', label: 'Copy-Trading Auditing', icon: Layers },
    { id: 'approvals', label: 'Plan UTR Approvals & Wallet', icon: CheckCircle2, badge: 'New' },
    { id: 'payment-settings', label: 'Bank & UPI Settings', icon: Building2 },
    { id: 'plans', label: 'Subscription Plans', icon: CreditCard },
    { id: 'wallets', label: 'Wallets & Ledger', icon: Wallet },
    { id: 'users', label: 'User Directory', icon: Users },
    { id: 'brokers', label: 'Broker Accounts', icon: ShieldCheck },
  ];

  return (
    <aside style={{
      width: '260px',
      borderRight: '1px solid var(--border-subtle)',
      background: 'var(--bg-main)',
      display: 'flex',
      flexDirection: 'column',
      minHeight: 'calc(100vh - 64px)',
      padding: '20px 12px',
    }}>
      <div style={{
        fontSize: '0.7rem',
        fontWeight: 700,
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        padding: '0 12px 10px',
      }}>
        Command Center
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderRadius: '8px',
                background: isActive ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                color: isActive ? 'var(--accent-cyan)' : 'var(--text-muted)',
                border: isActive ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid transparent',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: isActive ? 600 : 500,
                transition: 'all 0.15s ease',
                textAlign: 'left',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon size={18} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span style={{
                  fontSize: '0.65rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'rgba(16, 185, 129, 0.2)',
                  color: 'var(--accent-emerald)',
                  fontWeight: 700,
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', padding: '12px' }}>
        <div className="glass-panel" style={{ padding: '14px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>FastAPI Backend</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>● ONLINE (Port 8000)</div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
