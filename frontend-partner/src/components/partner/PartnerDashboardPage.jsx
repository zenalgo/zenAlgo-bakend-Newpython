import React, { useState, useEffect } from 'react';
import {
  DollarSign,
  Users,
  TrendingUp,
  CreditCard,
  Share2,
  Copy,
  Check,
  RefreshCw,
  ArrowUpRight,
  Sparkles,
  ShieldCheck,
  Award,
  Link2,
} from 'lucide-react';
import { partnerApi } from '../../api/partnerApi';
import { brokerApi } from '../../api/brokerApi';
import { useToast } from '../../context/ToastContext';

export const PartnerDashboardPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [stats, setStats] = useState(null);
  const [brokerSession, setBrokerSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const loadStats = async () => {
    setLoading(true);
    try {
      const [resStats, resBroker] = await Promise.allSettled([
        partnerApi.getDashboardStats(),
        brokerApi.getActiveSession(),
      ]);
      if (resStats.status === 'fulfilled') {
        setStats(resStats.value.data);
      }
      if (resBroker.status === 'fulfilled' && resBroker.value?.data?.connected) {
        setBrokerSession(resBroker.value.data);
      } else {
        setBrokerSession(null);
      }
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load partner dashboard stats', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleCopyLink = () => {
    if (stats?.referralLink) {
      navigator.clipboard.writeText(stats.referralLink);
      setCopied(true);
      addToast('Referral link copied to clipboard! 📋', 'success');
      setTimeout(() => setCopied(false), 3000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Partner Affiliate Hub</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Track client onboarding, sub-broker copy-trading fleets, and recurring commission payouts.
          </p>
        </div>

        <button onClick={loadStats} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Analytics</span>
        </button>
      </div>

      {/* Referral Link Quick Copy Card */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(217, 119, 6, 0.03) 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '8px',
              background: 'rgba(245, 158, 11, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-amber)',
            }}
          >
            <Share2 size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 800, color: '#fff', fontSize: '1rem' }}>
              Your Unique Partner Referral Link:
            </div>
            <div className="font-mono" style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', marginTop: '2px' }}>
              {stats?.referralLink || 'https://zenalgo.com/register?ref=REF-PARTNER77'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleCopyLink}
            className="btn btn-amber"
            style={{ padding: '10px 18px' }}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? 'Copied!' : 'Copy Referral Link'}</span>
          </button>

          <button
            onClick={() => onNavigate && onNavigate('partner-links')}
            className="btn btn-secondary"
            style={{ padding: '10px 18px' }}
          >
            <span>Broker Links & QR</span>
            <ArrowUpRight size={16} />
          </button>
        </div>
      </div>

      {/* Hero Metrics KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        
        {/* Total Earnings */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>TOTAL COMMISSION EARNED</span>
            <DollarSign size={18} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            ₹{Number(stats?.totalCommissionEarned ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
            ● Lifetime recurring revenue share
          </div>
        </div>

        {/* Ready Payout */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-amber)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>AVAILABLE PAYOUT BALANCE</span>
            <CreditCard size={18} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '8px' }}>
            ₹{Number(stats?.availablePayoutBalance ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
            <span>Ready for bank withdrawal</span>
            <button
              onClick={() => onNavigate && onNavigate('partner-payouts')}
              style={{ background: 'transparent', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', fontWeight: 700 }}
            >
              Withdraw →
            </button>
          </div>
        </div>

        {/* Total Referred Traders */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>REFERRED CLIENTS</span>
            <Users size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {stats?.totalReferrals ?? 0} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Traders</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            <strong style={{ color: 'var(--accent-emerald)' }}>{stats?.activeSubscribers ?? 0}</strong> Active Paid Subscribers
          </div>
        </div>

        {/* Conversion Rate */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-purple)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>CONVERSION & FLEET VOLUME</span>
            <TrendingUp size={18} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-purple)', marginTop: '8px' }}>
            {stats?.conversionRate != null ? `${stats.conversionRate}%` : '0.0%'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            30-Day Fleet Vol: ₹{Number(stats?.monthlyReferredVolume ?? 0).toLocaleString('en-IN')}
          </div>
        </div>

        {/* Partner Broker Account Binding */}
        <div
          className="glass-panel"
          onClick={() => onNavigate && onNavigate('partner-broker')}
          style={{
            padding: '20px',
            borderLeft: `4px solid ${brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)'}`,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>PARTNER BROKER LINK</span>
            <Link2 size={18} color={brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)'} />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {brokerSession?.connected ? `${brokerSession.brokerCode} Active` : 'Disconnected'}
          </div>
          <div style={{ fontSize: '0.75rem', color: brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)', marginTop: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{brokerSession?.connected ? `ID: ${brokerSession.accountClientId}` : 'Click to connect broker'}</span>
            <span style={{ textDecoration: 'underline' }}>Configure &rarr;</span>
          </div>
        </div>
      </div>

      {/* Quick Access Action Banners */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        
        {/* Client Sub-Fleet Overview Card */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={20} color="var(--accent-cyan)" />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                Referred Traders & Clients
              </h3>
            </div>
            <button onClick={() => onNavigate && onNavigate('partner-referrals')} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
              View All
            </button>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Inspect active trader strategies, subscription tiers, and copy-trading execution health across your client fleet.
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span className="badge badge-active">12 Active Institutional</span>
            <span className="badge badge-pending">4 Trial Users</span>
          </div>
        </div>

        {/* Commission History Card */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <DollarSign size={20} color="var(--accent-emerald)" />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                Commission Breakdown
              </h3>
            </div>
            <button onClick={() => onNavigate && onNavigate('partner-commissions')} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
              Ledger
            </button>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Live audit of 25% recurring revenue cuts credited from client plan subscriptions and copy-trading performance fees.
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span className="badge badge-active">₹12,500.00 This Week</span>
            <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>100% On-Time Clearing</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartnerDashboardPage;
