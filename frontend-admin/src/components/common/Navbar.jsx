import React, { useState, useEffect } from 'react';
import { Shield, PlayCircle, LogOut, UserCircle, Activity, Zap, FileText, Settings, Check, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTradingMode } from '../../context/TradingModeContext';
import { useToast } from '../../context/ToastContext';
import { settingsApi } from '../../api/settingsApi';

export const Navbar = ({ onOpenSimulate }) => {
  const { user, logout } = useAuth();
  const { tradingMode, setTradingMode, isLive, isPaper } = useTradingMode();
  const { addToast } = useToast();

  const [orderCap, setOrderCap] = useState(5000);
  const [isEditingCap, setIsEditingCap] = useState(false);
  const [capInput, setCapInput] = useState('5000');
  const [savingCap, setSavingCap] = useState(false);

  useEffect(() => {
    settingsApi.getOrderCap()
      .then((res) => {
        const val = res.data?.data?.maxOrderValueCap || 5000;
        setOrderCap(val);
        setCapInput(String(val));
      })
      .catch(() => {});
  }, []);

  const handleSaveCap = async (e) => {
    e.preventDefault();
    const num = parseFloat(capInput);
    if (isNaN(num) || num <= 0) {
      addToast('Please enter a valid positive amount for the safety cap', 'warning');
      return;
    }
    setSavingCap(true);
    try {
      const res = await settingsApi.updateOrderCap(num);
      const updated = res.data?.data?.maxOrderValueCap || num;
      setOrderCap(updated);
      setIsEditingCap(false);
      addToast(`🛡️ Live Order Safety Cap successfully set to ₹${parseFloat(updated).toLocaleString('en-IN')}!`, 'success');
    } catch (err) {
      addToast(err.message || 'Failed to update safety cap', 'error');
    } finally {
      setSavingCap(false);
    }
  };

  const handleModeSwitch = (newMode) => {
    if (newMode === tradingMode) return;
    setTradingMode(newMode);
    if (newMode === 'LIVE') {
      addToast('⚡ Platform Mode: LIVE TRADING activated! Real orders will route to connected brokers.', 'warning');
    } else {
      addToast('📝 Platform Mode: PAPER TRADING activated! Executions will run in simulated sandbox.', 'info');
    }
  };

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

        {/* Trading Mode Switch Toggler */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '24px',
          padding: '3px',
          gap: '3px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
        }}>
          <button
            type="button"
            id="nav-mode-paper-btn"
            onClick={() => handleModeSwitch('PAPER')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '20px',
              border: isPaper ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 700,
              transition: 'all 0.2s ease',
              background: isPaper ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              color: isPaper ? 'var(--accent-cyan)' : 'var(--text-muted)',
              boxShadow: isPaper ? '0 0 12px rgba(56, 189, 248, 0.3)' : 'none'
            }}
          >
            <FileText size={14} />
            <span>Paper Trading</span>
          </button>

          <button
            type="button"
            id="nav-mode-live-btn"
            onClick={() => handleModeSwitch('LIVE')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '20px',
              border: isLive ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid transparent',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 700,
              transition: 'all 0.2s ease',
              background: isLive ? 'rgba(16, 185, 129, 0.25)' : 'transparent',
              color: isLive ? '#34d399' : 'var(--text-muted)',
              boxShadow: isLive ? '0 0 14px rgba(16, 185, 129, 0.4)' : 'none'
            }}
          >
            <Zap size={14} />
            <span>Live Trading</span>
            {isLive && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 6px #34d399', display: 'inline-block' }}></span>}
          </button>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: isLive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(56, 189, 248, 0.1)',
          padding: '4px 10px',
          borderRadius: '9999px',
          border: `1px solid ${isLive ? 'rgba(16, 185, 129, 0.25)' : 'rgba(56, 189, 248, 0.25)'}`,
          fontSize: '0.75rem',
          color: isLive ? 'var(--accent-emerald)' : 'var(--accent-cyan)',
          fontWeight: 600,
        }}>
          <span className="pulse-active" style={{ background: isLive ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }}></span>
          <span>{isLive ? 'LIVE BROKER GATEWAY' : 'SIMULATION ENGINE'}</span>
        </div>

        {/* Admin-Configurable Max Order Value Safety Cap */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            id="nav-safety-cap-btn"
            onClick={() => setIsEditingCap(!isEditingCap)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              borderRadius: '20px',
              padding: '5px 12px',
              fontSize: '0.76rem',
              fontWeight: 700,
              color: '#f59e0b',
              cursor: 'pointer',
              transition: 'all 0.2s',
              boxShadow: '0 2px 6px rgba(0,0,0,0.2)'
            }}
            title="Click to change the platform-wide Max Order Value Safety Cap"
          >
            <Shield size={13} color="#f59e0b" />
            <span>Cap: ₹{parseFloat(orderCap).toLocaleString('en-IN')}</span>
            <span style={{ fontSize: '0.65rem', opacity: 0.8, textDecoration: 'underline' }}>Edit</span>
          </button>

          {/* Quick Edit Popover */}
          {isEditingCap && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 8px)',
              left: 0,
              width: '260px',
              background: 'rgba(15, 23, 42, 0.95)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              borderRadius: '12px',
              padding: '14px',
              boxShadow: '0 12px 30px rgba(0,0,0,0.6)',
              zIndex: 100,
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#fff' }}>🛡️ Max Order Value Cap</span>
                <button
                  type="button"
                  onClick={() => setIsEditingCap(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                >
                  <X size={14} />
                </button>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                Enforced by the execution engine. Any order exceeding this amount will be scaled down or safely rejected.
              </span>
              <form onSubmit={handleSaveCap} style={{ display: 'flex', gap: '6px' }}>
                <input
                  type="number"
                  min="100"
                  step="100"
                  value={capInput}
                  onChange={(e) => setCapInput(e.target.value)}
                  className="input-field"
                  style={{ padding: '6px 10px', fontSize: '0.85rem', flex: 1 }}
                  placeholder="e.g. 5000"
                  autoFocus
                />
                <button
                  type="submit"
                  disabled={savingCap}
                  className="btn btn-emerald"
                  style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                >
                  {savingCap ? '...' : <Check size={14} />}
                </button>
              </form>
            </div>
          )}
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
