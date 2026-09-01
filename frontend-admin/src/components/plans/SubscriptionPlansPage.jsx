import React, { useState, useEffect } from 'react';
import { CreditCard, Check, Plus, ShieldCheck } from 'lucide-react';
import { plansApi } from '../../api/plansApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const SubscriptionPlansPage = () => {
  const { addToast } = useToast();
  const [plans, setPlans] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('4999');
  const [billingPeriod, setBillingPeriod] = useState('MONTHLY');
  const [maxExecutions, setMaxExecutions] = useState(10);
  const [maxCapital, setMaxCapital] = useState(500000);
  const [loading, setLoading] = useState(false);

  const loadPlans = async () => {
    try {
      const res = await plansApi.getPublicPlans();
      setPlans(res.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadPlans();
  }, []);

  const handleCreatePlan = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await plansApi.createPlanAdmin({
        name,
        description,
        price: parseFloat(price),
        billingPeriod,
        maxStrategyExecutionsPerDay: parseInt(maxExecutions),
        maxCapitalAllocation: parseFloat(maxCapital),
      });
      addToast('Subscription Plan created successfully!', 'success');
      setIsModalOpen(false);
      loadPlans();
    } catch (err) {
      addToast(err.message || 'Failed to create plan', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Subscription Tier Plans</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Configure copy-trading quotas, daily execution limits, and monetization plans.</p>
        </div>
        <button onClick={() => setIsModalOpen(true)} className="btn btn-primary">
          <Plus size={16} />
          <span>Create New Tier Plan</span>
        </button>
      </div>

      {/* Plans Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
        {plans.length === 0 ? (
          <div className="glass-panel" style={{ padding: '30px', textAlign: 'center', gridColumn: '1 / -1' }}>
            No subscription plans created yet. Click "Create New Tier Plan" to add pricing tiers.
          </div>
        ) : (
          plans.map((p) => (
            <div key={p.id} className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>{p.name}</h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.description || 'Institutional copy-trading tier'}</div>
                </div>
                <div style={{
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: 'var(--accent-cyan)',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                }}>
                  {p.billingPeriod}
                </div>
              </div>

              <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-emerald)', fontFamily: 'Outfit, sans-serif' }}>
                ₹{p.price?.toLocaleString()}
                <span style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 500 }}> / month</span>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Check size={16} color="var(--accent-emerald)" />
                  <span><strong>{p.maxStrategyExecutionsPerDay || 10}</strong> executions / day</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Check size={16} color="var(--accent-emerald)" />
                  <span>Max Capital: <strong>₹{(p.maxCapitalAllocation || 500000).toLocaleString()}</strong></span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Check size={16} color="var(--accent-emerald)" />
                  <span>Dhan & Broker Direct API Access</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Check size={16} color="var(--accent-emerald)" />
                  <span>Real-time Risk Guard Protection</span>
                </div>
              </div>

              <button className="btn btn-secondary" style={{ marginTop: 'auto', width: '100%' }}>
                Edit Plan Quota
              </button>
            </div>
          ))
        )}
      </div>

      {/* Create Plan Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Create Subscription Plan">
        <form onSubmit={handleCreatePlan} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Plan Name</label>
            <input type="text" placeholder="e.g. Pro Scalper Tier" value={name} onChange={(e) => setName(e.target.value)} className="input-field" required />
          </div>
          <div>
            <label>Description</label>
            <input type="text" placeholder="High-frequency copy trading access" value={description} onChange={(e) => setDescription(e.target.value)} className="input-field" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Monthly Price (₹)</label>
              <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label>Billing Period</label>
              <select value={billingPeriod} onChange={(e) => setBillingPeriod(e.target.value)} className="input-field">
                <option value="MONTHLY">MONTHLY</option>
                <option value="QUARTERLY">QUARTERLY</option>
                <option value="ANNUAL">ANNUAL</option>
              </select>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Max Executions / Day</label>
              <input type="number" value={maxExecutions} onChange={(e) => setMaxExecutions(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label>Max Capital Allocation (₹)</label>
              <input type="number" value={maxCapital} onChange={(e) => setMaxCapital(e.target.value)} className="input-field" required />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary">{loading ? 'Creating...' : 'Create Plan'}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default SubscriptionPlansPage;
