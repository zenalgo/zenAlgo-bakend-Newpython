import React, { useState } from 'react';
import { Link2, ShieldCheck, CheckCircle2, RefreshCw, Key, ExternalLink } from 'lucide-react';
import { useToast } from '../../context/ToastContext';

export const BrokerBindingPage = () => {
  const { addToast } = useToast();
  const [clientId, setClientId] = useState('1100293841');
  const [pin, setPin] = useState('123456');
  const [totp, setTotp] = useState('654321');
  const [connecting, setConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(true);

  const handleConnect = (e) => {
    e.preventDefault();
    setConnecting(true);
    setTimeout(() => {
      setConnecting(false);
      setIsConnected(true);
      addToast('Dhan Broker Trading Account connected successfully!', 'success');
    }, 1000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '900px' }}>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Broker Binding & API Authentication</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Connect your broker account (Dhan HQ) for live algorithmic execution and real-time order routing.
        </p>
      </div>

      {/* Broker Connection Card */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)' }}>
              <Link2 size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: 0 }}>Dhan HQ Live Broker Gateway</h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)' }}>● Gateway Status: ONLINE (14ms Latency)</span>
            </div>
          </div>

          <span className={`badge ${isConnected ? 'badge-active' : 'badge-inactive'}`}>
            {isConnected ? '✓ CONNECTED & LIVE' : 'DISCONNECTED'}
          </span>
        </div>

        <form onSubmit={handleConnect} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <label>Dhan Client ID</label>
              <input
                type="text"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="input-field font-mono"
                required
              />
            </div>

            <div>
              <label>Account Password / PIN</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                className="input-field font-mono"
                required
              />
            </div>

            <div>
              <label>Authenticator TOTP</label>
              <input
                type="text"
                value={totp}
                onChange={(e) => setTotp(e.target.value)}
                className="input-field font-mono"
                required
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button type="submit" disabled={connecting} className="btn btn-primary" style={{ padding: '10px 24px' }}>
              <ShieldCheck size={16} />
              <span>{connecting ? 'Validating Broker...' : 'Re-Authenticate Broker Gateway'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default BrokerBindingPage;
