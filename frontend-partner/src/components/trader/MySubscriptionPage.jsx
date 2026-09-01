import React, { useState } from 'react';
import { Package, Check, Sparkles, Shield, ArrowUpRight } from 'lucide-react';
import { useToast } from '../../context/ToastContext';

export const MySubscriptionPage = () => {
  const { addToast } = useToast();
  const [currentPlan, setCurrentPlan] = useState('PRO');

  const plans = [
    {
      id: 'BASIC',
      name: 'Basic Trader Tier',
      price: '₹2,499',
      billing: '/month',
      features: ['Up to 2 Concurrent Strategies', 'Paper Trading Engine', '15m Candle Execution', 'Standard Discord Support'],
    },
    {
      id: 'PRO',
      name: 'Institutional Pro Tier',
      price: '₹5,999',
      billing: '/month',
      popular: true,
      features: ['Up to 6 Concurrent Strategies', 'Live Dhan Broker Integration', '5m High-Frequency Execution', 'Auto Trailing Stop Loss', 'Priority 1-on-1 Support'],
    },
    {
      id: 'INSTITUTIONAL',
      name: 'Hedge Fleet Tier',
      price: '₹14,999',
      billing: '/quarter',
      features: ['Unlimited Fleet Strategies', 'Zero-Latency Webhook Routing', '1m Scalper Execution', 'Multi-Leg Hedging', 'Dedicated Account Manager'],
    },
  ];

  const handleSubscribe = (planId) => {
    setCurrentPlan(planId);
    addToast(`Subscribed to ${planId} Tier successfully!`, 'success');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Subscription Plans & Fleet Access</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Manage your algorithmic trading fleet quota and execution tiers.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        {plans.map((p) => {
          const isCurrent = currentPlan === p.id;
          return (
            <div
              key={p.id}
              className="glass-panel"
              style={{
                padding: '28px 24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                border: isCurrent
                  ? '2px solid var(--accent-emerald)'
                  : p.popular
                  ? '1px solid var(--border-highlight)'
                  : '1px solid var(--border-subtle)',
                position: 'relative',
              }}
            >
              {p.popular && (
                <span
                  style={{
                    position: 'absolute',
                    top: '-12px',
                    right: '20px',
                    background: 'var(--accent-cyan)',
                    color: '#000',
                    fontSize: '0.7rem',
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    textTransform: 'uppercase',
                  }}
                >
                  Most Popular
                </span>
              )}

              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>{p.name}</h3>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginTop: '8px' }}>
                  <span style={{ fontSize: '2rem', fontWeight: 800, color: '#fff' }}>{p.price}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{p.billing}</span>
                </div>

                <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '20px', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {p.features.map((feat, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                      <Check size={16} color="var(--accent-emerald)" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: '24px' }}>
                <button
                  onClick={() => handleSubscribe(p.id)}
                  className={`btn ${isCurrent ? 'btn-emerald' : 'btn-primary'}`}
                  style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
                >
                  <span>{isCurrent ? '✓ Current Active Plan' : 'Subscribe / Upgrade Plan'}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MySubscriptionPage;
