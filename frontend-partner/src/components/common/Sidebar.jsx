import React from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Users,
  DollarSign,
  CreditCard,
  Share2,
  TrendingUp,
  Cpu,
  FileText,
  Wallet,
  Link2,
  Package,
  Shield,
  Layers,
} from 'lucide-react';

export const Sidebar = ({ currentTab, onSelectTab }) => {
  const { user } = useAuth();
  const isPartner = user?.role === 'PARTNER';

  const partnerNavItems = [
    { id: 'partner-dashboard', label: 'Partner Dashboard', icon: LayoutDashboard },
    { id: 'partner-referrals', label: 'Referred Clients', icon: Users },
    { id: 'partner-commissions', label: 'Commission Ledger', icon: DollarSign },
    { id: 'partner-payouts', label: 'Payouts & Transfers', icon: CreditCard },
    { id: 'partner-links', label: 'Broker & Referral Links', icon: Share2 },
  ];

  const traderNavItems = [
    { id: 'trader-dashboard', label: 'Trader Dashboard', icon: LayoutDashboard },
    { id: 'trader-strategies', label: 'Copy-Trading Fleet', icon: Cpu },
    { id: 'trader-orders', label: 'My Placed Orders', icon: FileText },
    { id: 'trader-wallet', label: 'Trading Margin & Wallet', icon: Wallet },
    { id: 'trader-broker', label: 'Broker Binding', icon: Link2 },
    { id: 'trader-subscription', label: 'Subscription Plans', icon: Package },
  ];

  const navItems = isPartner ? partnerNavItems : traderNavItems;

  return (
    <aside
      style={{
        width: 'var(--sidebar-width)',
        background: 'rgba(9, 13, 22, 0.95)',
        borderRight: '1px solid var(--border-subtle)',
        padding: '24px 16px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        minHeight: 'calc(100vh - var(--navbar-height))',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ padding: '0 12px 12px 12px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {isPartner ? 'Partner Navigation' : 'Trading Navigation'}
        </div>

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
                gap: '12px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                background: isActive
                  ? isPartner
                    ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(217, 119, 6, 0.1) 100%)'
                    : 'linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(2, 132, 199, 0.1) 100%)'
                  : 'transparent',
                color: isActive ? (isPartner ? 'var(--accent-amber)' : 'var(--accent-cyan)') : 'var(--text-muted)',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.85rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s ease',
                borderLeft: isActive
                  ? `3px solid ${isPartner ? 'var(--accent-amber)' : 'var(--accent-cyan)'}`
                  : '3px solid transparent',
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Partner Tier / Account Status Footer Card */}
      <div
        className="glass-panel"
        style={{
          padding: '14px',
          background: isPartner ? 'rgba(245, 158, 11, 0.05)' : 'rgba(16, 185, 129, 0.05)',
          border: `1px solid ${isPartner ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`,
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Shield size={14} color={isPartner ? 'var(--accent-amber)' : 'var(--accent-emerald)'} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#fff' }}>
            {isPartner ? 'Gold Affiliate Tier' : 'Institutional Pro Trader'}
          </span>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {isPartner ? '25% Lifetime Recurring Rev-Share' : 'Connected to Ultra-Low Latency Execution'}
        </div>
      </div>
    </aside>
  );
};
