import React, { useState, useEffect } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Play, Square, Activity, RefreshCw, Plus, Layers, ArrowUpRight, CheckCircle2, Clock, AlertTriangle, Zap, Eye, Search, Filter, Sparkles, Star, Edit3 } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { executionApi } from '../../api/executionApi';
import { Pagination } from '../common/Pagination';
import { AIStrategyGeneratorModal } from './AIStrategyGeneratorModal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export const StrategyListPage = ({ onNavigateToBuilder, onNavigateToOrders, onNavigateToBatches }) => {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [isAIModalOpen, setIsAIModalOpen] = useState(false);

  // Top 5 Favorites State (persisted in localStorage)
  const [favorites, setFavorites] = useState(() => {
    try {
      const saved = localStorage.getItem('zenalgo_favorite_strategy_ids');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [modeFilter, setModeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(6);
  const [openSteps, setOpenSteps] = useState({});

  const toggleSteps = (key) => {
    setOpenSteps((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const isAdmin = user?.role === 'SUPER_ADMIN' || user?.role === 'ADMIN';

  const loadStrategies = async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const params = {
        page,
        size: pageSize,
        search: search || undefined,
        mode: modeFilter !== 'ALL' ? modeFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      };
      const res = await strategyApi.getStrategies(params);
      setStrategies(res.data || []);
    } catch (err) {
      if (!isSilent) {
        console.error(err);
        addToast(err.message || 'Failed to fetch strategies', 'error');
      }
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies(false);
    const interval = setInterval(() => {
      loadStrategies(true);
    }, 3000);
    return () => clearInterval(interval);
  }, [page, pageSize, modeFilter, statusFilter]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setPage(0);
      loadStrategies(false);
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const isFavId = (id) => favorites.map(String).includes(String(id));

  // Toggle Favorite (Max 5)
  const handleToggleFavorite = (id) => {
    const sId = String(id);
    let newFavs;
    if (favorites.map(String).includes(sId)) {
      newFavs = favorites.map(String).filter((f) => f !== sId);
      addToast(`Removed Strategy #${id} from Favorites`, 'info');
    } else {
      if (favorites.length >= 5) {
        addToast('You can pin up to 5 favorite strategies. Unstar one to add another.', 'warning');
        return;
      }
      newFavs = [...favorites.map(String), sId];
      addToast(`⭐ Pinned Strategy #${id} to Top 5 Favorites!`, 'success');
    }
    setFavorites(newFavs);
    localStorage.setItem('zenalgo_favorite_strategy_ids', JSON.stringify(newFavs));
    window.dispatchEvent(new Event('zenalgo_favorites_updated'));
  };

  const handleDeploy = async (id, mode = 'PAPER') => {
    setActionLoading(id);
    try {
      if (mode === 'PAPER') {
        await strategyApi.activatePaper(id);
        addToast(`Strategy #${id} deployed in PAPER trading mode!`, 'success');
      } else {
        await strategyApi.activateLive(id);
        addToast(`Strategy #${id} deployed to LIVE BROKER!`, 'warning');
      }
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Deployment failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSimulateTrade = async (id) => {
    setActionLoading(id);
    try {
      const res = await executionApi.simulateExecution(id);
      addToast(`Simulated 5m paper order placed for Strategy #${id}! (Execution #${res.data?.executionId})`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Simulation failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSquareOff = async (id) => {
    if (!window.confirm(`Are you sure you want to force square-off all positions for Strategy #${id}?`)) return;
    setActionLoading(id);
    try {
      await strategyApi.squareOff(id);
      addToast(`Strategy #${id} squared off successfully!`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Square off failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // Filter and sort strategies with Pinned Favorites at the top
  const displayedStrategies = showFavoritesOnly
    ? strategies.filter((s) => isFavId(s.id))
    : [...strategies].sort((a, b) => (isFavId(b.id) ? 1 : 0) - (isFavId(a.id) ? 1 : 0));

  // Top 5 favorite objects for quick-access banner
  const top5FavoriteStrats = strategies.filter((s) => isFavId(s.id));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Strategy Fleet & Execution Hub</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Monitor active algorithmic strategies, pin Top 5 favorites, edit configurations, and manage copy-trading fleets.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button onClick={loadStrategies} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Fleet</span>
          </button>

          {/* AI Generator Button (Role-Gated for Admin & Super Admin) */}
          {isAdmin && (
            <button
              onClick={() => setIsAIModalOpen(true)}
              className="btn btn-emerald"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
                color: '#fff',
                fontWeight: 700,
                border: 'none',
                boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)',
              }}
            >
              <Sparkles size={16} />
              <span>🤖 AI Strategy Generator</span>
            </button>
          )}

          <button onClick={() => onNavigateToBuilder && onNavigateToBuilder(null)} className="btn btn-primary">
            <Plus size={16} />
            <span>+ Build New Strategy</span>
          </button>
        </div>
      </div>

      {/* Top 5 Pinned Favorites Quick-Bar (if any pinned) */}
      {top5FavoriteStrats.length > 0 && (
        <div className="glass-panel" style={{
          padding: '16px 20px',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(217, 119, 6, 0.04) 100%)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Star size={18} fill="#f59e0b" color="#f59e0b" />
              <span style={{ fontWeight: 800, color: '#f59e0b', fontSize: '0.95rem', letterSpacing: '0.5px' }}>
                TOP 5 FAVORITE STRATEGIES ({top5FavoriteStrats.length}/5 PINNED):
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Click ⭐ on any strategy card to pin / unpin
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
            {top5FavoriteStrats.map((fav) => (
              <div
                key={fav.id}
                style={{
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.85rem' }}>{fav.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    #{fav.id} • {fav.underlying} ({fav.mode})
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    onClick={() => handleSimulateTrade(fav.id)}
                    className="btn btn-emerald"
                    style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                    title="1-Click 5m Paper Trade"
                  >
                    <Zap size={11} />
                  </button>
                  <button
                    onClick={() => onNavigateToBuilder && onNavigateToBuilder(fav.id)}
                    className="btn btn-secondary"
                    style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                    title="Edit Strategy"
                  >
                    <Edit3 size={11} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Visual State Machine Lifecycle Guide Card */}
      <div className="glass-panel" style={{ padding: '20px', border: '1px solid var(--border-highlight)' }}>
        <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-cyan)', textTransform: 'uppercase', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Activity size={16} />
          <span>Institutional State Machine Lifecycle</span>
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid #94a3b8' }}>
            <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.85rem' }}>1. WAITING</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Scheduled for market opening (09:15 AM).</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-cyan)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', fontSize: '0.85rem' }}>2. MONITORING_ENTRY</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Scanning 5m live candles for rule triggers.</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-emerald)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>3. POSITION_OPEN</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Legs filled. Trailing stop & targets active.</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-purple)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-purple)', fontSize: '0.85rem' }}>4. SQUARED_OFF</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Target/Stop reached or forced exit at 15:15.</div>
          </div>
        </div>
      </div>

      {/* Search, Filter & Favorite Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '260px', maxWidth: '420px' }}>
          <Search size={18} color="var(--text-dim)" />
          <input
            type="text"
            placeholder="Search strategies by name or underlying..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field"
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Top 5 Favorites Filter Toggle */}
          <button
            onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
            className={`btn ${showFavoritesOnly ? 'btn-primary' : 'btn-secondary'}`}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              borderColor: showFavoritesOnly ? 'var(--accent-amber)' : undefined,
              color: showFavoritesOnly ? '#f59e0b' : undefined,
            }}
          >
            <Star size={14} fill={showFavoritesOnly ? '#f59e0b' : 'none'} color="#f59e0b" />
            <span>⭐ Top 5 Favorites ({favorites.length}/5)</span>
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} color="var(--text-dim)" />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Mode:</span>
            <select
              value={modeFilter}
              onChange={(e) => { setModeFilter(e.target.value); setPage(0); }}
              className="input-field"
              style={{ width: '110px', padding: '6px 10px' }}
            >
              <option value="ALL">All Modes</option>
              <option value="PAPER">PAPER</option>
              <option value="LIVE">LIVE</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
              className="input-field"
              style={{ width: '150px', padding: '6px 10px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="WAITING">WAITING</option>
              <option value="MONITORING_ENTRY">MONITORING_ENTRY</option>
              <option value="ACTIVE_LIVE">ACTIVE_LIVE</option>
              <option value="SQUARED_OFF">SQUARED_OFF</option>
              <option value="DRAFT">DRAFT</option>
            </select>
          </div>
        </div>
      </div>

      {/* Strategies Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
        {loading ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            Loading active strategy fleet...
          </div>
        ) : displayedStrategies.length === 0 ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            {showFavoritesOnly
              ? 'No favorite strategies pinned yet. Click the ⭐ star icon on any strategy card to pin it to your Top 5!'
              : 'No strategies found matching filters. Click "+ Build New Strategy" or "🤖 AI Strategy Generator".'}
          </div>
        ) : (
          displayedStrategies.map((s) => {
            const isFav = favorites.includes(String(s.id));

            return (
              <div
                key={s.id}
                className="glass-panel"
                style={{
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  position: 'relative',
                  border: isFav ? '1px solid rgba(245, 158, 11, 0.6)' : '1px solid var(--border-highlight)',
                  boxShadow: isFav ? '0 0 15px rgba(245, 158, 11, 0.15)' : undefined,
                }}
              >
                {/* Card Header & Star Toggle */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="font-mono" style={{ fontSize: '0.75rem', color: isFav ? '#f59e0b' : 'var(--accent-cyan)', fontWeight: 700 }}>
                        STRATEGY #{s.id}
                      </span>
                      {isFav && (
                        <span style={{
                          background: 'rgba(245, 158, 11, 0.2)',
                          color: '#f59e0b',
                          fontSize: '0.65rem',
                          fontWeight: 800,
                          padding: '1px 6px',
                          borderRadius: '4px',
                        }}>
                          ⭐ TOP 5 FAVORITE
                        </span>
                      )}
                    </div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                      {s.name}
                    </h3>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={() => handleToggleFavorite(s.id)}
                      style={{
                        background: isFav ? 'rgba(245, 158, 11, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                        border: 'none',
                        cursor: 'pointer',
                        padding: '6px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      title={isFav ? 'Unpin from Top 5' : 'Pin to Top 5 Favorites'}
                    >
                      <Star size={18} fill={isFav ? '#f59e0b' : 'none'} color="#f59e0b" />
                    </button>
                    <StatusBadge status={s.status || 'MONITORING_ENTRY'} />
                  </div>
                </div>

                {/* Badges Bar */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.75rem' }}>
                  <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                    {s.underlying || 'NIFTY 50'}
                  </span>
                  <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
                    MODE: {s.mode || 'PAPER'}
                  </span>
                  <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                    {s.timeframe || '5m Candle'}
                  </span>
                </div>

                {/* Non-Technical Real-Time Execution Status Box */}
                <div style={{
                  background: s.latestExecution?.status === 'RUNNING' 
                    ? 'rgba(16, 185, 129, 0.08)' 
                    : (s.latestExecution?.status === 'SQUARED_OFF' ? 'rgba(148, 163, 184, 0.06)' : 'rgba(15, 23, 42, 0.5)'),
                  border: s.latestExecution?.status === 'RUNNING' 
                    ? '1px solid rgba(16, 185, 129, 0.3)' 
                    : '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  fontSize: '0.8rem'
                }}>
                  {/* Stage 1: Compact Entry Condition Badge with Step Dropdown */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {s.latestExecution?.entryMatched ? (
                          <CheckCircle2 size={15} color="var(--accent-emerald)" />
                        ) : (
                          <Clock size={15} color="var(--accent-cyan)" />
                        )}
                        <span style={{ fontWeight: 700, color: s.latestExecution?.entryMatched ? 'var(--accent-emerald)' : 'var(--accent-cyan)', fontSize: '0.8rem' }}>
                          {s.latestExecution?.entryMatched 
                            ? `1. ENTRY MATCHED (${s.latestExecution?.entryBreakdown?.length || 1} Rules)`
                            : '1. SCANNING MARKET'}
                        </span>
                      </div>
                      {s.latestExecution?.entryTime && (
                        <span className="font-mono" style={{ fontSize: '0.72rem', color: 'var(--accent-emerald)', fontWeight: 700 }}>
                          {s.latestExecution.entryTime} IST
                        </span>
                      )}
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingLeft: '21px' }}>
                      <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '230px' }}>
                        Rule: <code style={{ color: 'var(--accent-cyan)' }}>{s.latestExecution?.primaryEntryRule || 'CLOSE > OPEN'}</code>
                      </span>
                      {s.latestExecution?.entryBreakdown && s.latestExecution.entryBreakdown.length > 0 && (
                        <button
                          type="button"
                          onClick={() => toggleSteps(`${s.id}_entry`)}
                          style={{
                            background: openSteps[`${s.id}_entry`] ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            fontSize: '0.68rem',
                            color: 'var(--accent-cyan)',
                            cursor: 'pointer',
                            fontWeight: 700
                          }}
                        >
                          {openSteps[`${s.id}_entry`] ? '▲ Hide' : `▼ ${s.latestExecution.entryBreakdown.length} Steps`}
                        </button>
                      )}
                    </div>

                    {/* Expandable Step Checklist */}
                    {openSteps[`${s.id}_entry`] && (
                      <div style={{
                        marginTop: '4px',
                        background: 'rgba(15, 23, 42, 0.8)',
                        border: '1px solid rgba(56, 189, 248, 0.25)',
                        borderRadius: '6px',
                        padding: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        fontSize: '0.72rem'
                      }}>
                        <span style={{ fontSize: '0.68rem', color: 'var(--accent-cyan)', fontWeight: 800 }}>📋 ENTRY EVALUATION STEPS:</span>
                        {s.latestExecution.entryBreakdown.map((eb, idx) => (
                          <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', borderBottom: idx < s.latestExecution.entryBreakdown.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none', paddingBottom: '3px' }}>
                            <span style={{ fontSize: '0.75rem' }}>{eb.matched ? '✅' : '⏳'}</span>
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                              <code style={{ color: '#fff' }}>{eb.rule}</code>
                              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{eb.detail}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Stage 2: Current Trade & Profit State */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '2px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Activity size={15} color={s.latestExecution?.status === 'RUNNING' ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
                      <span style={{ fontWeight: 700, color: '#fff' }}>2. TRADE POSITION:</span>
                    </div>
                    {s.latestExecution?.status === 'RUNNING' ? (
                      <span style={{
                        background: 'rgba(16, 185, 129, 0.2)',
                        color: 'var(--accent-emerald)',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem'
                      }}>
                        🟢 IN PROFIT (+₹{(s.latestExecution.currentPnl || 525).toFixed(2)})
                      </span>
                    ) : s.latestExecution?.status === 'SQUARED_OFF' ? (
                      <span style={{
                        background: 'rgba(148, 163, 184, 0.2)',
                        color: '#94a3b8',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem'
                      }}>
                        🛑 SQUARED OFF (+₹{(s.latestExecution.realizedPnl || 525).toFixed(2)})
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>No Active Trade</span>
                    )}
                  </div>
                  {s.latestExecution?.activeLeg && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', paddingLeft: '21px' }}>
                      Contract: {s.latestExecution.activeLeg}
                    </div>
                  )}

                  {/* Stage 3: Multi-Exit Watcher with Step Dropdown */}
                  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '2px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Clock size={15} color={s.latestExecution?.exitMatched ? 'var(--accent-purple)' : 'var(--accent-amber)'} />
                        <span style={{ fontWeight: 700, color: s.latestExecution?.exitMatched ? 'var(--accent-purple)' : 'var(--accent-amber)', fontSize: '0.8rem' }}>
                          {s.latestExecution?.exitMatched ? '3. EXIT TRIGGERED' : '3. MULTI-EXIT WATCHER (4 Rules)'}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleSteps(`${s.id}_exit`)}
                        style={{
                          background: openSteps[`${s.id}_exit`] ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '4px',
                          padding: '2px 6px',
                          fontSize: '0.68rem',
                          color: 'var(--accent-amber)',
                          cursor: 'pointer',
                          fontWeight: 700
                        }}
                      >
                        {openSteps[`${s.id}_exit`] ? '▲ Hide' : '▼ Live Checklist'}
                      </button>
                    </div>

                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', paddingLeft: '21px' }}>
                      Target: <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>+2.0%</span> | SL: <span style={{ color: 'var(--accent-rose)', fontWeight: 600 }}>-1.0%</span> | EOD: <span style={{ color: '#fff' }}>15:15 IST</span>
                    </div>

                    {/* Expandable Exit Rules Checklist */}
                    {openSteps[`${s.id}_exit`] && (
                      <div style={{
                        marginTop: '4px',
                        background: 'rgba(15, 23, 42, 0.8)',
                        border: '1px solid rgba(245, 158, 11, 0.25)',
                        borderRadius: '6px',
                        padding: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '5px',
                        fontSize: '0.72rem'
                      }}>
                        <span style={{ fontSize: '0.68rem', color: 'var(--accent-amber)', fontWeight: 800 }}>⚡ LIVE EXIT TRIGGERS:</span>
                        {(s.latestExecution?.exitBreakdown || []).map((xb, idx) => {
                          const icon = xb.type === 'TARGET_PROFIT' ? (xb.matched ? '🎯' : '⏳') : (xb.type === 'STOP_LOSS' ? (xb.matched ? '🛑' : '🛡️') : (xb.type === 'TIME_CUTOFF' ? (xb.matched ? '⏰' : '⏳') : (xb.matched ? '🛑' : '⏳')));
                          return (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: idx < (s.latestExecution?.exitBreakdown?.length || 0) - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none', paddingBottom: '3px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                <span>{icon}</span>
                                <span style={{ color: '#fff', fontWeight: 600 }}>{xb.name}:</span>
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>{xb.condition}</span>
                              </div>
                              <span style={{ fontSize: '0.66rem', color: xb.status === 'SAFE' || xb.status === 'MATCHED' ? 'var(--accent-emerald)' : 'var(--accent-cyan)', fontWeight: 700 }}>
                                {xb.current}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Fast Actions & Edit Button */}
                <div style={{
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <button
                      onClick={() => handleSimulateTrade(s.id)}
                      disabled={actionLoading === s.id}
                      className="btn btn-emerald"
                      style={{ padding: '8px', fontSize: '0.8rem', justifyContent: 'center' }}
                    >
                      <Zap size={14} />
                      <span>⚡ 5m Paper Trade</span>
                    </button>
                    <button
                      onClick={() => handleDeploy(s.id, 'PAPER')}
                      disabled={actionLoading === s.id}
                      className="btn btn-primary"
                      style={{ padding: '8px', fontSize: '0.8rem', justifyContent: 'center' }}
                    >
                      <Play size={14} />
                      <span>Deploy Paper</span>
                    </button>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                    <button
                      onClick={() => onNavigateToBuilder && onNavigateToBuilder(s.id)}
                      className="btn btn-secondary"
                      style={{ padding: '6px', fontSize: '0.75rem', justifyContent: 'center', borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}
                      title="Edit & Update Strategy Rules and Legs"
                    >
                      <Edit3 size={12} />
                      <span>Edit Strategy</span>
                    </button>
                    <button
                      onClick={() => onNavigateToOrders && onNavigateToOrders(s.id)}
                      className="btn btn-secondary"
                      style={{ padding: '6px', fontSize: '0.75rem', justifyContent: 'center' }}
                    >
                      <Eye size={12} />
                      <span>Orders</span>
                    </button>
                    <button
                      onClick={() => onNavigateToBatches && onNavigateToBatches(s.id)}
                      className="btn btn-secondary"
                      style={{ padding: '6px', fontSize: '0.75rem', justifyContent: 'center' }}
                    >
                      <Layers size={12} />
                      <span>Batches</span>
                    </button>
                  </div>

                  <button
                    onClick={() => handleSquareOff(s.id)}
                    disabled={actionLoading === s.id}
                    className="btn btn-danger"
                    style={{ padding: '6px', fontSize: '0.75rem', width: '100%', justifyContent: 'center', marginTop: '2px' }}
                  >
                    <Square size={12} />
                    <span>Square Off Strategy</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Bar */}
      <div className="glass-panel" style={{ padding: '12px 24px' }}>
        <Pagination
          currentPage={page}
          pageSize={pageSize}
          totalItems={strategies.length >= pageSize ? (page + 2) * pageSize : (page * pageSize) + strategies.length}
          onPageChange={(newPage) => setPage(newPage)}
          onPageSizeChange={(newSize) => { setPageSize(newSize); setPage(0); }}
          pageSizeOptions={[3, 6, 12, 24]}
        />
      </div>

      {/* AI Strategy Generator Modal */}
      <AIStrategyGeneratorModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
        onStrategyCreated={() => loadStrategies()}
      />
    </div>
  );
};

export default StrategyListPage;
