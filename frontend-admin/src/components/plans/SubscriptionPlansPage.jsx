import React, { useState, useEffect } from 'react';
import { CreditCard, Check, Plus, ShieldCheck, RefreshCw, Zap, Users, Trash2, Search, Filter } from 'lucide-react';
import { plansApi } from '../../api/plansApi';
import { Modal } from '../common/Modal';
import { Pagination } from '../common/Pagination';
import { useToast } from '../../context/ToastContext';

export const SubscriptionPlansPage = () => {
  const { addToast } = useToast();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(6);

  // Form State
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [monthlyPrice, setMonthlyPrice] = useState('4999');
  const [subscriptionType, setSubscriptionType] = useState('MONTHLY');
  const [maxExecutions, setMaxExecutions] = useState('25');
  const [maxCapital, setMaxCapital] = useState('500000');
  const [maxStrategies, setMaxStrategies] = useState('5');
  const [minWalletBalance, setMinWalletBalance] = useState('5000');
  const [submitting, setSubmitting] = useState(false);

  const loadPlans = async () => {
    setLoading(true);
    try {
      const params = {
        page,
        size: pageSize,
        search: search || undefined,
        subscription_type: typeFilter !== 'ALL' ? typeFilter : undefined,
      };
      const res = await plansApi.getPublicPlans(params);
      setPlans(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to fetch subscription plans', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlans();
  }, [page, pageSize, typeFilter]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setPage(0);
      loadPlans();
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  const handleNameChange = (e) => {
    const val = e.target.value;
    setName(val);
    if (!code || code === name.toUpperCase().replace(/[^A-Z0-9]/g, '_')) {
      setCode(val.toUpperCase().replace(/[^A-Z0-9]/g, '_'));
    }
  };

  const handleCreatePlan = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    const payload = {
      code: code || name.toUpperCase().replace(/[^A-Z0-9]/g, '_'),
      name,
      description: description || 'Algorithmic strategy copy-trading tier',
      monthlyPrice: parseFloat(monthlyPrice),
      currency: 'INR',
      gstPercentage: 18.00,
      minWalletBalance: parseFloat(minWalletBalance) || 0.0,
      maxActiveStrategies: parseInt(maxStrategies) || 5,
      maxStrategyExecutionsPerDay: parseInt(maxExecutions) || 25,
      maxPortfolioCapital: parseFloat(maxCapital) || 500000.0,
      subscriptionType,
    };

    try {
      await plansApi.createPlanAdmin(payload);
      addToast(`Subscription Plan "${name}" created successfully!`, 'success');
      setIsModalOpen(false);
      setName('');
      setCode('');
      setDescription('');
      loadPlans();
    } catch (err) {
      addToast(err.message || 'Failed to create plan', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Subscription Tier Plans</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Configure copy-trading quotas, daily execution limits, and monetization plans.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadPlans} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setIsModalOpen(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Create New Tier Plan</span>
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '240px', maxWidth: '400px' }}>
          <Search size={18} color="var(--text-dim)" />
          <input
            type="text"
            placeholder="Search plans by name or code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field"
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Filter size={14} color="var(--text-dim)" />
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Billing Cycle:</span>
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }}
            className="input-field"
            style={{ width: '140px', padding: '6px 10px' }}
          >
            <option value="ALL">All Periods</option>
            <option value="MONTHLY">MONTHLY</option>
            <option value="QUARTERLY">QUARTERLY</option>
            <option value="ANNUAL">ANNUAL</option>
          </select>
        </div>
      </div>

      {/* Plans Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {loading ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            Loading subscription plans...
          </div>
        ) : plans.length === 0 ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            No subscription plans found matching filters. Click <strong>"+ Create New Tier Plan"</strong> to add pricing tiers.
          </div>
        ) : (
          plans.map((p) => {
            const priceVal = p.monthlyPrice !== undefined ? p.monthlyPrice : p.monthly_price;
            const maxExec = p.maxStrategyExecutionsPerDay !== undefined ? p.maxStrategyExecutionsPerDay : p.max_strategy_executions_per_day;
            const maxCap = p.maxPortfolioCapital !== undefined ? p.maxPortfolioCapital : p.max_portfolio_capital;
            const subType = p.subscriptionType || p.subscription_type || 'MONTHLY';
            const isActive = p.isActive !== undefined ? p.isActive : p.is_active;

            return (
              <div
                key={p.id}
                className="glass-panel"
                style={{
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  position: 'relative',
                  border: '1px solid var(--border-highlight)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>{p.name}</h3>
                    <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '2px' }}>
                      CODE: {p.code}
                    </div>
                  </div>
                  <div style={{
                    padding: '4px 10px',
                    borderRadius: '9999px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    color: 'var(--accent-cyan)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                  }}>
                    {subType}
                  </div>
                </div>

                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', minHeight: '36px' }}>
                  {p.description || 'Algorithmic strategy copy-trading tier'}
                </div>

                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-emerald)', fontFamily: 'Outfit, sans-serif' }}>
                  ₹{parseFloat(priceVal || 0).toLocaleString('en-IN')}
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 500 }}> / month</span>
                </div>

                <div style={{
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  fontSize: '0.875rem',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span><strong>{maxExec || 10}</strong> strategy executions / day</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Max Capital: <strong>₹{parseFloat(maxCap || 500000).toLocaleString('en-IN')}</strong></span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Min Wallet Balance: ₹{parseFloat(p.minWalletBalance || p.min_wallet_balance || 0).toLocaleString('en-IN')}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Autonomous Paper & Live Broker Execution</span>
                  </div>
                </div>

                <div style={{ marginTop: 'auto', paddingTop: '10px', display: 'flex', gap: '8px' }}>
                  <span className={`badge ${isActive ? 'badge-running' : 'badge-failed'}`} style={{ width: '100%', justifyContent: 'center' }}>
                    {isActive ? 'TIER ACTIVE' : 'INACTIVE'}
                  </span>
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
          totalItems={plans.length >= pageSize ? (page + 2) * pageSize : (page * pageSize) + plans.length}
          onPageChange={(newPage) => setPage(newPage)}
          onPageSizeChange={(newSize) => { setPageSize(newSize); setPage(0); }}
          pageSizeOptions={[3, 6, 12]}
        />
      </div>

      {/* Create Plan Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Create New Subscription Tier Plan">
        <form onSubmit={handleCreatePlan} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Plan Name</label>
              <input
                type="text"
                placeholder="e.g. VIP Scalper Pro"
                value={name}
                onChange={handleNameChange}
                className="input-field"
                required
              />
            </div>
            <div>
              <label>Plan Code (Unique)</label>
              <input
                type="text"
                placeholder="VIP_SCALPER_PRO"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                className="input-field font-mono"
                required
              />
            </div>
          </div>

          <div>
            <label>Plan Description</label>
            <input
              type="text"
              placeholder="High-frequency index options copy-trading tier"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input-field"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Monthly Price (₹)</label>
              <input
                type="number"
                value={monthlyPrice}
                onChange={(e) => setMonthlyPrice(e.target.value)}
                className="input-field"
                required
              />
            </div>
            <div>
              <label>Subscription Period</label>
              <select value={subscriptionType} onChange={(e) => setSubscriptionType(e.target.value)} className="input-field">
                <option value="MONTHLY">MONTHLY</option>
                <option value="QUARTERLY">QUARTERLY</option>
                <option value="ANNUAL">ANNUAL</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Max Executions / Day</label>
              <input
                type="number"
                value={maxExecutions}
                onChange={(e) => setMaxExecutions(e.target.value)}
                className="input-field"
                required
              />
            </div>
            <div>
              <label>Max Portfolio Capital (₹)</label>
              <input
                type="number"
                value={maxCapital}
                onChange={(e) => setMaxCapital(e.target.value)}
                className="input-field"
                required
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Max Active Strategies</label>
              <input
                type="number"
                value={maxStrategies}
                onChange={(e) => setMaxStrategies(e.target.value)}
                className="input-field"
                required
              />
            </div>
            <div>
              <label>Min Wallet Balance (₹)</label>
              <input
                type="number"
                value={minWalletBalance}
                onChange={(e) => setMinWalletBalance(e.target.value)}
                className="input-field"
                required
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={submitting} className="btn btn-primary">
              {submitting ? 'Creating...' : 'Create Plan Tier'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default SubscriptionPlansPage;
