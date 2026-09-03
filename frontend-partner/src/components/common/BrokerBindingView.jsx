import React, { useState, useEffect } from 'react';
import {
  Link2,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Key,
  ExternalLink,
  AlertTriangle,
  LogOut,
  Wallet,
  TrendingUp,
  Layers,
  Copy,
  Eye,
  EyeOff,
  Clock,
  Sparkles,
  Info,
  DollarSign,
  ArrowRightLeft,
  XCircle,
  PlusCircle,
  Calculator,
  Activity,
  FileText,
  PieChart,
  ShoppingBag,
  Check,
  X,
  Search,
  Building2,
} from 'lucide-react';
import { brokerApi } from '../../api/brokerApi';
import { useToast } from '../../context/ToastContext';
import { useBroker } from '../../context/BrokerContext';

export const BrokerBindingView = ({ role = 'TRADER' }) => {
  const { addToast } = useToast();
  const { checkBrokerSession } = useBroker();
  const isPartner = role === 'PARTNER';

  // Active Session & Data State
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [funds, setFunds] = useState(null);
  const [profile, setProfile] = useState(null);
  const [positions, setPositions] = useState([]);
  const [holdings, setHoldings] = useState([]);
  const [orders, setOrders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [refreshingData, setRefreshingData] = useState(false);

  // Tab State
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'positions' | 'holdings' | 'orders' | 'margin'
  const [ordersSubTab, setOrdersSubTab] = useState('orders'); // 'orders' | 'trades'

  // Connection Form State (When Disconnected)
  const [selectedBroker, setSelectedBroker] = useState('DHAN');
  const [authMode, setAuthMode] = useState('TOKEN'); // 'TOKEN' | 'TOTP'
  const [clientId, setClientId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [pin, setPin] = useState('');
  const [totp, setTotp] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [formError, setFormError] = useState('');

  // Instant Order Entry Modal State
  const [isOrderModalOpen, setIsOrderModalOpen] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderForm, setOrderForm] = useState({
    tradingSymbol: 'TATAGOLD',
    securityId: '21401',
    companyName: 'Tata Gold ETF',
    sector: 'Commodities & ETFs',
    exchangeSegment: 'NSE_EQ',
    transactionType: 'BUY',
    orderType: 'MARKET',
    productType: 'CNC',
    quantity: 1,
    price: 0,
  });

  // Stock / Scrip Search Autocomplete State
  const [searchStockQuery, setSearchStockQuery] = useState('');
  const [stockSearchResults, setStockSearchResults] = useState([]);
  const [searchingStocks, setSearchingStocks] = useState(false);
  const [showStockDropdown, setShowStockDropdown] = useState(false);

  // Live Stock Search Debounce
  useEffect(() => {
    if (!isOrderModalOpen) return;
    const timer = setTimeout(async () => {
      if (searchStockQuery.trim().length >= 1) {
        setSearchingStocks(true);
        try {
          const res = await brokerApi.searchInstruments(searchStockQuery.trim());
          if (res.data?.data) {
            setStockSearchResults(res.data.data);
            setShowStockDropdown(true);
          }
        } catch (err) {
          console.error('Failed to search instruments:', err);
        } finally {
          setSearchingStocks(false);
        }
      } else {
        setStockSearchResults([]);
        setShowStockDropdown(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchStockQuery, isOrderModalOpen]);

  const handleSelectStock = (stock) => {
    setOrderForm((prev) => ({
      ...prev,
      tradingSymbol: stock.symbol,
      securityId: stock.securityId,
      companyName: stock.companyName,
      sector: stock.sector,
      exchangeSegment: stock.exchangeSegment || 'NSE_EQ',
      quantity: stock.lotSize || 1,
    }));
    setSearchStockQuery('');
    setShowStockDropdown(false);
  };

  // Margin Calculator Tool State
  const [calculatingMargin, setCalculatingMargin] = useState(false);
  const [marginForm, setMarginForm] = useState({
    tradingSymbol: 'NIFTY 24500 CE',
    securityId: '52145',
    exchangeSegment: 'NSE_FNO',
    productType: 'INTRADAY',
    quantity: 50,
    price: 145.0,
  });
  const [marginResult, setMarginResult] = useState(null);

  // Position Conversion Action State
  const [actionLoading, setActionLoading] = useState(null);

  // Load Active Session and Data
  const loadActiveSession = async () => {
    setLoading(true);
    setFormError('');
    try {
      const res = await brokerApi.getActiveSession();
      if (res.data && res.data.connected) {
        setSession(res.data);
        await loadAllBrokerData();
      } else {
        setSession(null);
        setFunds(null);
        setProfile(null);
        setPositions([]);
        setHoldings([]);
        setOrders([]);
        setTrades([]);
      }
    } catch (err) {
      console.error('Error fetching broker session:', err);
      setSession(null);
    } finally {
      setLoading(false);
    }
  };

  const loadAllBrokerData = async () => {
    setRefreshingData(true);
    try {
      const [fundsRes, profileRes, posRes, holdRes, ordRes, trdRes] = await Promise.allSettled([
        brokerApi.getDhanFunds(),
        brokerApi.getDhanProfile(),
        brokerApi.getDhanPositions(),
        brokerApi.getDhanHoldings(),
        brokerApi.getDhanOrders(),
        brokerApi.getDhanTrades(),
      ]);

      if (fundsRes.status === 'fulfilled' && fundsRes.value?.data) {
        setFunds(fundsRes.value.data);
      }
      if (profileRes.status === 'fulfilled' && profileRes.value?.data) {
        setProfile(profileRes.value.data);
      }
      if (posRes.status === 'fulfilled' && Array.isArray(posRes.value?.data)) {
        setPositions(posRes.value.data);
      }
      if (holdRes.status === 'fulfilled' && Array.isArray(holdRes.value?.data)) {
        setHoldings(holdRes.value.data);
      }
      if (ordRes.status === 'fulfilled' && Array.isArray(ordRes.value?.data)) {
        setOrders(ordRes.value.data);
      }
      if (trdRes.status === 'fulfilled' && Array.isArray(trdRes.value?.data)) {
        setTrades(trdRes.value.data);
      }
    } catch (err) {
      console.warn('Could not load complete broker dataset:', err);
    } finally {
      setRefreshingData(false);
    }
  };

  useEffect(() => {
    loadActiveSession();
  }, []);

  // Handle Connecting Broker
  const handleConnect = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError('');

    try {
      // DHAN HQ Connection (Sole Supported Broker)
      if (authMode === 'TOKEN') {
        if (!clientId.trim() || !accessToken.trim()) {
          setFormError('Please enter both Dhan Client ID and Access Token.');
          setSubmitting(false);
          return;
        }

        await brokerApi.connectBroker('DHAN', {
          clientId: clientId.trim(),
          accessToken: accessToken.trim(),
        });

        addToast('Dhan HQ Broker connected successfully! Unlocking all ZenAlgo features...', 'success');
        setAccessToken('');
        await loadActiveSession();
        await checkBrokerSession();
      } else if (authMode === 'TOTP') {
        if (!clientId.trim() || !pin.trim() || !totp.trim()) {
          setFormError('Please enter Client ID, Password/PIN, and 6-digit TOTP.');
          setSubmitting(false);
          return;
        }

        await brokerApi.connectDhanTotp({
          dhanClientId: clientId.trim(),
          pin: pin.trim(),
          totp: totp.trim(),
        });

        addToast('Dhan HQ account verified via TOTP & connected! Unlocking all ZenAlgo features...', 'success');
        setPin('');
        setTotp('');
        await loadActiveSession();
        await checkBrokerSession();
      }
    } catch (err) {
      console.error('Broker connection failed:', err);
      const msg = err.response?.data?.message || err.message || 'Failed to authenticate broker credentials.';
      setFormError(msg);
      addToast(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Disconnecting Broker
  const handleDisconnect = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Dhan broker account? Live order execution and ZenAlgo features will be locked until re-authenticated.')) {
      return;
    }

    setDisconnecting(true);
    try {
      await brokerApi.disconnectDhanSession();
      addToast('Broker session disconnected successfully.', 'info');
      setSession(null);
      setFunds(null);
      setProfile(null);
      setPositions([]);
      setHoldings([]);
      setOrders([]);
      setTrades([]);
      await checkBrokerSession();
    } catch (err) {
      const msg = err.response?.data?.message || err.message || 'Failed to disconnect broker.';
      addToast(msg, 'error');
    } finally {
      setDisconnecting(false);
    }
  };

  // Handle Placing Instant Order
  const handlePlaceOrderSubmit = async (e) => {
    e.preventDefault();
    setPlacingOrder(true);
    try {
      const payload = {
        tradingSymbol: orderForm.tradingSymbol.trim(),
        securityId: orderForm.securityId.trim(),
        exchangeSegment: orderForm.exchangeSegment,
        transactionType: orderForm.transactionType,
        orderType: orderForm.orderType,
        productType: orderForm.productType,
        quantity: parseInt(orderForm.quantity, 10),
        price: orderForm.orderType === 'MARKET' ? 0 : parseFloat(orderForm.price),
      };

      const res = await brokerApi.placeDhanOrder(payload);
      addToast(`Order placed successfully on Dhan! ID: ${res.data?.brokerOrderId || 'LIVE'}`, 'success');
      setIsOrderModalOpen(false);
      await loadAllBrokerData();
    } catch (err) {
      console.error('Order placement failed:', err);
      addToast(err.response?.data?.message || err.message || 'Order placement failed.', 'error');
    } finally {
      setPlacingOrder(false);
    }
  };

  // Handle Cancel Order
  const handleCancelOrder = async (orderId) => {
    if (!window.confirm(`Are you sure you want to cancel order ${orderId}?`)) return;
    try {
      await brokerApi.cancelDhanOrder(orderId);
      addToast(`Order ${orderId} cancelled successfully on Dhan.`, 'info');
      await loadAllBrokerData();
    } catch (err) {
      addToast(err.response?.data?.message || err.message || 'Failed to cancel order.', 'error');
    }
  };

  // Handle Convert Position
  const handleConvertPosition = async (pos) => {
    const targetProduct = pos.positionType === 'INTRADAY' ? 'MARGIN' : 'INTRADAY';
    if (!window.confirm(`Convert position ${pos.tradingSymbol} from ${pos.positionType} to ${targetProduct}?`)) return;

    setActionLoading(pos.securityId);
    try {
      await brokerApi.convertDhanPosition({
        tradingSymbol: pos.tradingSymbol,
        securityId: pos.securityId,
        fromProductType: pos.positionType,
        toProductType: targetProduct,
        quantity: pos.netQty,
      });
      addToast(`Position converted to ${targetProduct} successfully!`, 'success');
      await loadAllBrokerData();
    } catch (err) {
      addToast(err.response?.data?.message || err.message || 'Position conversion failed.', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Calculate Margin
  const handleCalculateMarginSubmit = async (e) => {
    e.preventDefault();
    setCalculatingMargin(true);
    try {
      const res = await brokerApi.calculateDhanMargin({
        tradingSymbol: marginForm.tradingSymbol.trim(),
        securityId: marginForm.securityId.trim(),
        exchangeSegment: marginForm.exchangeSegment,
        productType: marginForm.productType,
        quantity: parseInt(marginForm.quantity, 10),
        price: parseFloat(marginForm.price),
      });
      setMarginResult(res.data);
      addToast('Margin calculated successfully!', 'success');
    } catch (err) {
      addToast(err.response?.data?.message || err.message || 'Failed to calculate margin.', 'error');
    } finally {
      setCalculatingMargin(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* Header Section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', margin: 0 }}>
              {isPartner ? 'Partner Dhan HQ Trading Gateway' : 'Dhan HQ Broker Gateway & Trading Hub'}
            </h1>
            <span
              className={`badge ${session?.connected ? 'badge-active' : 'badge-inactive'}`}
              style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            >
              {session?.connected ? '● GATEWAY LIVE' : '○ DISCONNECTED'}
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '6px' }}>
            {isPartner
              ? 'Access live positions, portfolio holdings, order routing, and margin limits directly from your connected Dhan HQ account.'
              : 'Direct integration with Dhan HQ API v2 for real-time positions, demat holdings, live order execution, and margin calculation.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {session?.connected && (
            <button
              onClick={() => setIsOrderModalOpen(true)}
              className="btn btn-primary"
              style={{ padding: '8px 18px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
            >
              <PlusCircle size={16} />
              <span>Place Dhan Order</span>
            </button>
          )}

          <button
            onClick={loadActiveSession}
            disabled={loading || refreshingData}
            className="btn btn-secondary"
            style={{ padding: '8px 16px' }}
          >
            <RefreshCw size={15} className={loading || refreshingData ? 'animate-spin' : ''} />
            <span>Sync Broker Data</span>
          </button>
        </div>
      </div>

      {/* 1-Day Token Policy Notice */}
      <div
        className="glass-panel"
        style={{
          padding: '12px 18px',
          background: session?.connected ? 'rgba(16, 185, 129, 0.06)' : 'rgba(245, 158, 11, 0.06)',
          border: session?.connected ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {session?.connected ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <CheckCircle2 size={16} color="var(--accent-emerald)" />
              <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
                <strong style={{ color: 'var(--accent-emerald)' }}>Dhan HQ Session Status:</strong> Authenticated & Active for today ({session.connectionDate || new Date().toISOString().split('T')[0]}) in Asia/Kolkata timezone (1-day validity).
              </div>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Client ID: <span className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>{session.accountClientId}</span>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Clock size={16} color="var(--accent-amber)" />
            <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
              <strong style={{ color: 'var(--accent-amber)' }}>Dhan HQ Session Status:</strong> Not connected. Please connect your broker credentials below (Dhan sessions are valid for 1 calendar day).
            </div>
          </div>
        )}
      </div>

      {/* ========================================================= */}
      {/* CASE A: BROKER CONNECTED -> FULL DHAN HQ HUB               */}
      {/* ========================================================= */}
      {session?.connected ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Navigation Tabs */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              borderBottom: '1px solid var(--border-subtle)',
              paddingBottom: '8px',
              flexWrap: 'wrap',
            }}
          >
            <button
              onClick={() => setActiveTab('overview')}
              className={`btn ${activeTab === 'overview' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 16px' }}
            >
              <PieChart size={15} />
              <span>Overview & Funds</span>
            </button>

            <button
              onClick={() => setActiveTab('positions')}
              className={`btn ${activeTab === 'positions' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 16px' }}
            >
              <Activity size={15} />
              <span>Positions ({positions.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('holdings')}
              className={`btn ${activeTab === 'holdings' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 16px' }}
            >
              <ShoppingBag size={15} />
              <span>Holdings ({holdings.length})</span>
            </button>

            <button
              id="tab-orders"
              onClick={() => setActiveTab('orders')}
              className={`btn ${activeTab === 'orders' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 16px' }}
            >
              <FileText size={15} />
              <span>Orders & Trades ({orders.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('margin')}
              className={`btn ${activeTab === 'margin' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 16px' }}
            >
              <Calculator size={15} />
              <span>Margin Calculator</span>
            </button>
          </div>

          {/* -------------------------------------------------------- */}
          {/* TAB 1: OVERVIEW & FUNDS                                   */}
          {/* -------------------------------------------------------- */}
          {activeTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* Profile Card */}
              <div
                className="glass-panel"
                style={{
                  padding: '20px 24px',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(5, 150, 105, 0.03) 100%)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div
                    style={{
                      width: '46px',
                      height: '46px',
                      borderRadius: '10px',
                      background: 'rgba(16, 185, 129, 0.2)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--accent-emerald)',
                    }}
                  >
                    <ShieldCheck size={24} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                        {session.brokerCode === 'DHAN' ? 'Dhan HQ Live Account' : `${session.brokerCode} Sandbox`}
                      </h3>
                      <span className="badge badge-active">ACTIVE & AUTHENTICATED</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Client ID:{' '}
                      <span className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
                        {session.accountClientId}
                      </span>
                      {profile?.name && (
                        <span style={{ color: 'var(--text-main)', marginLeft: '12px' }}>
                          • Holder: <strong>{profile.name}</strong> ({profile.ucc || 'UCC Verified'})
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleDisconnect}
                    disabled={disconnecting}
                    className="btn btn-danger"
                    style={{ padding: '8px 16px' }}
                  >
                    <LogOut size={16} />
                    <span>{disconnecting ? 'Disconnecting...' : 'Disconnect Broker'}</span>
                  </button>
                </div>
              </div>

              {/* Funds Breakdown Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '8px', borderLeft: '4px solid var(--accent-emerald)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>AVAILABLE BALANCE</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '6px' }}>
                    {funds?.availableBalance != null ? `₹${Number(funds.availableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'N/A'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>Free intraday trading margin</div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '8px', borderLeft: '4px solid var(--accent-cyan)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>START OF DAY (SOD) LIMIT</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
                    {funds?.sodLimit != null ? `₹${Number(funds.sodLimit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'N/A'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>Initial margin allocation</div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '8px', borderLeft: '4px solid var(--accent-purple)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>COLLATERAL PLEDGED</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
                    {funds?.collateralAmount != null ? `₹${Number(funds.collateralAmount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '₹0.00'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>Securities collateral margin</div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '8px', borderLeft: '4px solid var(--accent-amber)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>UTILIZED MARGIN</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '6px' }}>
                    {funds?.utilizedAmount != null ? `₹${Number(funds.utilizedAmount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '₹0.00'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>Margin locked in open positions</div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '8px', borderLeft: '4px solid var(--border-subtle)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>WITHDRAWABLE BALANCE</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
                    {funds?.withdrawableBalance != null ? `₹${Number(funds.withdrawableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'N/A'}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>Settled funds for bank transfer</div>
                </div>
              </div>
            </div>
          )}

          {/* -------------------------------------------------------- */}
          {/* TAB 2: LIVE POSITIONS                                     */}
          {/* -------------------------------------------------------- */}
          {activeTab === 'positions' && (
            <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                  Active Positions Book
                </h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Auto-synced with Dhan Open API v2
                </span>
              </div>

              {positions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                  No active open positions on Dhan today.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '12px 10px' }}>TRADING SYMBOL</th>
                        <th style={{ padding: '12px 10px' }}>PRODUCT</th>
                        <th style={{ padding: '12px 10px' }}>NET QTY</th>
                        <th style={{ padding: '12px 10px' }}>BUY AVG</th>
                        <th style={{ padding: '12px 10px' }}>SELL AVG</th>
                        <th style={{ padding: '12px 10px' }}>UNREALIZED P&L</th>
                        <th style={{ padding: '12px 10px' }}>REALIZED P&L</th>
                        <th style={{ padding: '12px 10px', textAlign: 'right' }}>ACTIONS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                          <td style={{ padding: '14px 10px', fontWeight: 700, color: '#fff' }}>
                            {p.tradingSymbol}
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', display: 'block' }}>ID: {p.securityId}</span>
                          </td>
                          <td style={{ padding: '14px 10px' }}>
                            <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                              {p.positionType}
                            </span>
                          </td>
                          <td style={{ padding: '14px 10px', fontWeight: 700, color: p.netQty > 0 ? 'var(--accent-emerald)' : p.netQty < 0 ? 'var(--accent-rose)' : 'var(--text-muted)' }}>
                            {p.netQty}
                          </td>
                          <td style={{ padding: '14px 10px', fontFamily: 'monospace' }}>₹{p.buyAvg}</td>
                          <td style={{ padding: '14px 10px', fontFamily: 'monospace' }}>₹{p.sellAvg}</td>
                          <td style={{ padding: '14px 10px', fontWeight: 800, color: p.unrealizedProfit >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                            {p.unrealizedProfit >= 0 ? '+' : ''}₹{p.unrealizedProfit.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', fontWeight: 700, color: p.realizedProfit >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                            {p.realizedProfit >= 0 ? '+' : ''}₹{p.realizedProfit.toFixed(2)}
                          </td>
                          <td style={{ padding: '14px 10px', textAlign: 'right' }}>
                            <button
                              onClick={() => handleConvertPosition(p)}
                              disabled={actionLoading === p.securityId}
                              className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                            >
                              <ArrowRightLeft size={13} />
                              <span>Convert</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* -------------------------------------------------------- */}
          {/* TAB 3: DEMAT HOLDINGS                                     */}
          {/* -------------------------------------------------------- */}
          {activeTab === 'holdings' && (
            <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                  Demat Portfolio & Equity Holdings
                </h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Total Demat Stocks: {holdings.length}
                </span>
              </div>

              {holdings.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                  No demat holdings found in this Dhan account.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '12px 10px' }}>STOCK SYMBOL</th>
                        <th style={{ padding: '12px 10px' }}>ISIN CODE</th>
                        <th style={{ padding: '12px 10px' }}>TOTAL QTY</th>
                        <th style={{ padding: '12px 10px' }}>AVAILABLE QTY</th>
                        <th style={{ padding: '12px 10px' }}>AVG COST</th>
                        <th style={{ padding: '12px 10px' }}>LTP</th>
                        <th style={{ padding: '12px 10px' }}>CURRENT VALUE</th>
                        <th style={{ padding: '12px 10px' }}>P&L (₹)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((h, idx) => {
                        const curVal = h.totalQty * h.lastTradedPrice;
                        const invVal = h.totalQty * h.avgCostPrice;
                        const pnl = curVal - invVal;
                        return (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                            <td style={{ padding: '14px 10px', fontWeight: 800, color: '#fff' }}>{h.tradingSymbol}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', color: 'var(--text-dim)', fontSize: '0.75rem' }}>{h.isin}</td>
                            <td style={{ padding: '14px 10px', fontWeight: 700 }}>{h.totalQty}</td>
                            <td style={{ padding: '14px 10px', color: 'var(--accent-emerald)' }}>{h.availableQty}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace' }}>₹{h.avgCostPrice.toFixed(2)}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', fontWeight: 700, color: '#fff' }}>₹{h.lastTradedPrice.toFixed(2)}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', fontWeight: 700 }}>₹{curVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td style={{ padding: '14px 10px', fontWeight: 800, color: pnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                              {pnl >= 0 ? '+' : ''}₹{pnl.toFixed(2)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* -------------------------------------------------------- */}
          {/* TAB 4: ORDERS & TRADES                                    */}
          {/* -------------------------------------------------------- */}
          {activeTab === 'orders' && (
            <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Sub-Tabs: Orders vs Trades */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={() => setOrdersSubTab('orders')}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: ordersSubTab === 'orders' ? 'var(--accent-cyan)' : 'var(--text-muted)',
                      fontWeight: ordersSubTab === 'orders' ? 800 : 500,
                      borderBottom: ordersSubTab === 'orders' ? '2px solid var(--accent-cyan)' : 'none',
                      padding: '6px 12px',
                      cursor: 'pointer',
                    }}
                  >
                    Live Orders ({orders.length})
                  </button>

                  <button
                    onClick={() => setOrdersSubTab('trades')}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: ordersSubTab === 'trades' ? 'var(--accent-cyan)' : 'var(--text-muted)',
                      fontWeight: ordersSubTab === 'trades' ? 800 : 500,
                      borderBottom: ordersSubTab === 'trades' ? '2px solid var(--accent-cyan)' : 'none',
                      padding: '6px 12px',
                      cursor: 'pointer',
                    }}
                  >
                    Executed Trades ({trades.length})
                  </button>
                </div>

                <button
                  id="btn-new-order"
                  onClick={() => setIsOrderModalOpen(true)}
                  className="btn btn-primary"
                  style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                >
                  <PlusCircle size={14} />
                  <span>New Order</span>
                </button>
              </div>

              {/* Sub-View: Orders */}
              {ordersSubTab === 'orders' && (
                <div style={{ overflowX: 'auto' }}>
                  {orders.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                      No orders placed for today yet.
                    </div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '12px 10px' }}>ORDER ID</th>
                          <th style={{ padding: '12px 10px' }}>SYMBOL</th>
                          <th style={{ padding: '12px 10px' }}>SIDE</th>
                          <th style={{ padding: '12px 10px' }}>PRODUCT</th>
                          <th style={{ padding: '12px 10px' }}>ORDER TYPE</th>
                          <th style={{ padding: '12px 10px' }}>QTY</th>
                          <th style={{ padding: '12px 10px' }}>PRICE</th>
                          <th style={{ padding: '12px 10px' }}>STATUS</th>
                          <th style={{ padding: '12px 10px', textAlign: 'right' }}>ACTION</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orders.map((o, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', color: 'var(--accent-cyan)' }}>
                              {o.orderId || o.brokerOrderId}
                            </td>
                            <td style={{ padding: '14px 10px', fontWeight: 800, color: '#fff' }}>{o.tradingSymbol}</td>
                            <td style={{ padding: '14px 10px' }}>
                              <span style={{ fontWeight: 800, color: (o.transactionType || '').toUpperCase() === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                                {o.transactionType}
                              </span>
                            </td>
                            <td style={{ padding: '14px 10px' }}>{o.productType}</td>
                            <td style={{ padding: '14px 10px' }}>{o.orderType}</td>
                            <td style={{ padding: '14px 10px', fontWeight: 700 }}>{o.quantity}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace' }}>₹{o.price}</td>
                            <td style={{ padding: '14px 10px' }}>
                              <span
                                className="badge"
                                style={{
                                  background:
                                    o.orderStatus === 'TRADED' || o.orderStatus === 'FILLED'
                                      ? 'rgba(16, 185, 129, 0.15)'
                                      : o.orderStatus === 'OPEN'
                                      ? 'rgba(245, 158, 11, 0.15)'
                                      : 'rgba(244, 63, 94, 0.15)',
                                  color:
                                    o.orderStatus === 'TRADED' || o.orderStatus === 'FILLED'
                                      ? 'var(--accent-emerald)'
                                      : o.orderStatus === 'OPEN'
                                      ? 'var(--accent-amber)'
                                      : 'var(--accent-rose)',
                                }}
                              >
                                {o.orderStatus}
                              </span>
                            </td>
                            <td style={{ padding: '14px 10px', textAlign: 'right' }}>
                              {o.orderStatus === 'OPEN' && (
                                <button
                                  onClick={() => handleCancelOrder(o.orderId || o.brokerOrderId)}
                                  className="btn btn-danger"
                                  style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                >
                                  Cancel
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {/* Sub-View: Trades */}
              {ordersSubTab === 'trades' && (
                <div style={{ overflowX: 'auto' }}>
                  {trades.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                      No trades executed for today yet.
                    </div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '12px 10px' }}>TRADE ID</th>
                          <th style={{ padding: '12px 10px' }}>ORDER ID</th>
                          <th style={{ padding: '12px 10px' }}>SYMBOL</th>
                          <th style={{ padding: '12px 10px' }}>SIDE</th>
                          <th style={{ padding: '12px 10px' }}>TRADED QTY</th>
                          <th style={{ padding: '12px 10px' }}>EXECUTION PRICE</th>
                          <th style={{ padding: '12px 10px' }}>EXECUTION TIME</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trades.map((t, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', color: 'var(--accent-emerald)' }}>{t.tradeId}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', color: 'var(--text-dim)' }}>{t.orderId}</td>
                            <td style={{ padding: '14px 10px', fontWeight: 800, color: '#fff' }}>{t.tradingSymbol}</td>
                            <td style={{ padding: '14px 10px', fontWeight: 800, color: t.transactionType === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                              {t.transactionType}
                            </td>
                            <td style={{ padding: '14px 10px', fontWeight: 700 }}>{t.tradedQuantity}</td>
                            <td style={{ padding: '14px 10px', fontFamily: 'monospace', color: '#fff', fontWeight: 700 }}>₹{t.tradedPrice}</td>
                            <td style={{ padding: '14px 10px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>{t.tradeTime}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          )}

          {/* -------------------------------------------------------- */}
          {/* TAB 5: MARGIN CALCULATOR                                 */}
          {/* -------------------------------------------------------- */}
          {activeTab === 'margin' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
              
              {/* Calculator Form */}
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', marginBottom: '16px' }}>
                  Dhan Real-Time Margin Calculator
                </h3>

                <form onSubmit={handleCalculateMarginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                      Trading Symbol
                    </label>
                    <input
                      type="text"
                      value={marginForm.tradingSymbol}
                      onChange={(e) => setMarginForm({ ...marginForm, tradingSymbol: e.target.value })}
                      className="input-field font-mono"
                      required
                      style={{ width: '100%' }}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                        Quantity
                      </label>
                      <input
                        type="number"
                        value={marginForm.quantity}
                        onChange={(e) => setMarginForm({ ...marginForm, quantity: e.target.value })}
                        className="input-field font-mono"
                        required
                        style={{ width: '100%' }}
                      />
                    </div>

                    <div>
                      <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                        Expected Price (₹)
                      </label>
                      <input
                        type="number"
                        step="0.05"
                        value={marginForm.price}
                        onChange={(e) => setMarginForm({ ...marginForm, price: e.target.value })}
                        className="input-field font-mono"
                        required
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                        Segment
                      </label>
                      <select
                        value={marginForm.exchangeSegment}
                        onChange={(e) => setMarginForm({ ...marginForm, exchangeSegment: e.target.value })}
                        className="input-field"
                        style={{ width: '100%' }}
                      >
                        <option value="NSE_FNO">NSE_FNO (Options & Futures)</option>
                        <option value="NSE_EQ">NSE_EQ (Cash Equity)</option>
                        <option value="BSE_EQ">BSE_EQ (Cash)</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                        Product
                      </label>
                      <select
                        value={marginForm.productType}
                        onChange={(e) => setMarginForm({ ...marginForm, productType: e.target.value })}
                        className="input-field"
                        style={{ width: '100%' }}
                      >
                        <option value="INTRADAY">INTRADAY (MIS)</option>
                        <option value="MARGIN">MARGIN (NRML Carryforward)</option>
                        <option value="CNC">CNC (Delivery)</option>
                      </select>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={calculatingMargin}
                    className="btn btn-primary"
                    style={{ padding: '10px 18px', marginTop: '10px' }}
                  >
                    <Calculator size={16} />
                    <span>{calculatingMargin ? 'Calculating Margin...' : 'Calculate Required Margin'}</span>
                  </button>
                </form>
              </div>

              {/* Calculator Results Display */}
              <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                  Margin Sufficiency Analysis
                </h3>

                {marginResult ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div
                      style={{
                        padding: '12px 16px',
                        borderRadius: '8px',
                        background: marginResult.marginSufficient ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                        border: `1px solid ${marginResult.marginSufficient ? 'var(--accent-emerald)' : 'var(--accent-rose)'}`,
                        color: marginResult.marginSufficient ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        fontWeight: 700,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      {marginResult.marginSufficient ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                      <span>{marginResult.marginSufficient ? 'Margin is SUFFICIENT for trade' : 'INSUFFICIENT margin in Dhan account'}</span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: '6px' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SPAN MARGIN</span>
                        <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                          ₹{Number(marginResult.spanMargin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </div>
                      </div>

                      <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: '6px' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EXPOSURE MARGIN</span>
                        <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                          ₹{Number(marginResult.exposureMargin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </div>
                      </div>
                    </div>

                    <div style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>TOTAL MARGIN REQUIRED</span>
                      <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '4px' }}>
                        ₹{Number(marginResult.totalMarginRequired || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>Your Available Balance:</span>
                      <strong style={{ color: 'var(--accent-emerald)' }}>
                        ₹{Number(funds?.availableBalance ?? marginResult.availableBalance ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-muted)' }}>
                    Fill the parameters on the left and click Calculate to simulate live margin requirements from Dhan HQ.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* ========================================================= */
        /* CASE B: DISCONNECTED - AUTHENTICATION FORM                */
        /* ========================================================= */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Exclusive Gateway Info Card */}
          <div
            className="glass-panel"
            style={{
              padding: '18px 22px',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              background: 'rgba(56, 189, 248, 0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-cyan)',
                }}
              >
                <Link2 size={22} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>Dhan HQ Open API v2</h4>
                  <span className="badge badge-active" style={{ fontSize: '0.7rem' }}>PRIMARY GATEWAY</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                  All ZenAlgo strategies, order execution, and fleet copy-trading route directly through Dhan HQ.
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-cyan)', fontWeight: 700, fontSize: '0.85rem' }}>
              <CheckCircle2 size={18} />
              <span>Dhan HQ Enabled</span>
            </div>
          </div>

          {/* Authentication Method Selector */}
          <div>
            <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px', display: 'block' }}>
              SELECT AUTHENTICATION METHOD
            </label>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => setAuthMode('TOKEN')}
                className={`btn ${authMode === 'TOKEN' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '8px 18px' }}
              >
                <Key size={15} />
                <span>Access Token (Direct Developer API)</span>
              </button>

              <button
                type="button"
                onClick={() => setAuthMode('TOTP')}
                className={`btn ${authMode === 'TOTP' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '8px 18px' }}
              >
                <ShieldCheck size={15} />
                <span>PIN + Authenticator TOTP</span>
              </button>
            </div>
          </div>

          {/* Form Error Banner */}
          {formError && (
            <div
              style={{
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid rgba(244, 63, 94, 0.4)',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: 'var(--accent-rose)',
                fontSize: '0.85rem',
              }}
            >
              <AlertTriangle size={18} />
              <span>{formError}</span>
            </div>
          )}

          {/* Step 3: Credentials Form */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <form onSubmit={handleConnect} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {selectedBroker === 'DHAN' && authMode === 'TOKEN' && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                        Dhan Client ID *
                      </label>
                      <input
                        type="text"
                        value={clientId}
                        onChange={(e) => setClientId(e.target.value)}
                        placeholder="e.g. 1100293841"
                        className="input-field font-mono"
                        required
                        style={{ width: '100%' }}
                      />
                    </div>

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          Dhan API Access Token *
                        </label>
                        <button
                          type="button"
                          onClick={() => setShowToken(!showToken)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
                        >
                          {showToken ? <EyeOff size={13} /> : <Eye size={13} />}
                          <span>{showToken ? 'Hide' : 'Show'}</span>
                        </button>
                      </div>
                      <input
                        type={showToken ? 'text' : 'password'}
                        value={accessToken}
                        onChange={(e) => setAccessToken(e.target.value)}
                        placeholder="Paste your 24h Dhan access token"
                        className="input-field font-mono"
                        required
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(245, 158, 11, 0.08)',
                      border: '1px solid rgba(245, 158, 11, 0.25)',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                  >
                    <Info size={18} color="var(--accent-amber)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                      <strong style={{ color: '#fff' }}>How to generate your Dhan Access Token:</strong>
                      <br />
                      1. Log in to <a href="https://web.dhan.co" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'underline' }}>web.dhan.co</a>
                      <br />
                      2. Go to <strong>My Profile & Settings &gt; DhanHQ Trading APIs &gt; Access Token</strong>
                      <br />
                      3. Click <strong>Generate Access Token</strong> and paste it above.
                    </div>
                  </div>
                </>
              )}

              {selectedBroker === 'DHAN' && authMode === 'TOTP' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                      Dhan Client ID *
                    </label>
                    <input
                      type="text"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      placeholder="e.g. 1100293841"
                      className="input-field font-mono"
                      required
                      style={{ width: '100%' }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                      Account PIN / Password *
                    </label>
                    <input
                      type="password"
                      value={pin}
                      onChange={(e) => setPin(e.target.value)}
                      placeholder="6-digit Dhan PIN"
                      className="input-field font-mono"
                      maxLength={6}
                      required
                      style={{ width: '100%' }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                      Authenticator TOTP *
                    </label>
                    <input
                      type="text"
                      value={totp}
                      onChange={(e) => setTotp(e.target.value)}
                      placeholder="6-digit live TOTP"
                      className="input-field font-mono"
                      maxLength={6}
                      required
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '10px' }}>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn btn-primary"
                  style={{ padding: '10px 24px', fontSize: '0.9rem', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
                >
                  <ShieldCheck size={18} />
                  <span>{submitting ? 'Authenticating Dhan Gateway...' : 'Connect Dhan HQ Account'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* INSTANT DHAN ORDER ENTRY MODAL                            */}
      {/* ========================================================= */}
      {isOrderModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '20px',
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '520px',
              padding: '28px',
              background: 'rgba(15, 23, 42, 0.98)',
              border: '1px solid var(--border-highlight)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)' }}>
                  <PlusCircle size={20} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', margin: 0 }}>Place Dhan Market Order</h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Direct execution via Dhan Open API v2</span>
                </div>
              </div>

              <button
                onClick={() => setIsOrderModalOpen(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handlePlaceOrderSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Buy / Sell Toggle */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setOrderForm({ ...orderForm, transactionType: 'BUY' })}
                  style={{
                    padding: '10px',
                    borderRadius: '6px',
                    fontWeight: 800,
                    border: 'none',
                    cursor: 'pointer',
                    background: orderForm.transactionType === 'BUY' ? 'var(--accent-emerald)' : 'rgba(255, 255, 255, 0.08)',
                    color: orderForm.transactionType === 'BUY' ? '#fff' : 'var(--text-muted)',
                  }}
                >
                  BUY
                </button>

                <button
                  type="button"
                  onClick={() => setOrderForm({ ...orderForm, transactionType: 'SELL' })}
                  style={{
                    padding: '10px',
                    borderRadius: '6px',
                    fontWeight: 800,
                    border: 'none',
                    cursor: 'pointer',
                    background: orderForm.transactionType === 'SELL' ? 'var(--accent-rose)' : 'rgba(255, 255, 255, 0.08)',
                    color: orderForm.transactionType === 'SELL' ? '#fff' : 'var(--text-muted)',
                  }}
                >
                  SELL
                </button>
              </div>

              {/* Stock Search & Autocomplete Input */}
              <div style={{ position: 'relative' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Search Stock / ETF (210 NSE F&O Stocks + ETFs) *</span>
                  {searchingStocks && <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)' }}>Searching...</span>}
                </label>
                <div style={{ position: 'relative' }}>
                  <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input
                    id="input-stock-search"
                    type="text"
                    value={searchStockQuery}
                    onChange={(e) => setSearchStockQuery(e.target.value)}
                    onFocus={() => { if (stockSearchResults.length > 0) setShowStockDropdown(true); }}
                    placeholder="Type stock name or ticker (e.g. Tata Gold, Reliance, HDFC, SBI)..."
                    className="input-field"
                    style={{ width: '100%', paddingLeft: '36px' }}
                  />
                  {searchStockQuery && (
                    <button
                      type="button"
                      onClick={() => { setSearchStockQuery(''); setShowStockDropdown(false); }}
                      style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                {/* Autocomplete Dropdown */}
                {showStockDropdown && stockSearchResults.length > 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      zIndex: 50,
                      marginTop: '4px',
                      maxHeight: '220px',
                      overflowY: 'auto',
                      background: 'rgba(15, 23, 42, 0.98)',
                      border: '1px solid var(--border-highlight)',
                      borderRadius: '8px',
                      boxShadow: '0 12px 28px rgba(0,0,0,0.7)',
                    }}
                  >
                    {stockSearchResults.map((stk) => (
                      <div
                        key={`${stk.symbol}-${stk.securityId}`}
                        id={`search-result-${stk.symbol}`}
                        onClick={() => handleSelectStock(stk)}
                        style={{
                          padding: '10px 14px',
                          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(56, 189, 248, 0.12)')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 800, color: '#fff', fontSize: '0.9rem' }}>{stk.symbol}</span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', background: 'rgba(56, 189, 248, 0.15)', padding: '1px 5px', borderRadius: '4px' }}>
                              {stk.exchangeSegment}
                            </span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.15)', padding: '1px 5px', borderRadius: '4px', fontWeight: 600 }}>
                              SecID: {stk.securityId}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {stk.companyName}
                          </div>
                        </div>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textAlign: 'right', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {stk.sector}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Selected Stock Banner Card */}
              <div
                id="selected-scrip-banner"
                style={{
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--accent-emerald)', fontWeight: 800 }}>
                      Selected Scrip:
                    </span>
                    <span style={{ fontWeight: 800, color: '#fff', fontSize: '1rem', fontFamily: 'monospace' }}>
                      {orderForm.tradingSymbol}
                    </span>
                    <span style={{ fontSize: '0.7rem', background: 'rgba(56, 189, 248, 0.2)', color: 'var(--accent-cyan)', padding: '1px 6px', borderRadius: '4px' }}>
                      {orderForm.exchangeSegment}
                    </span>
                    <span style={{ fontSize: '0.7rem', background: 'rgba(16, 185, 129, 0.2)', color: 'var(--accent-emerald)', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>
                      Dhan SecID: {orderForm.securityId}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                    {orderForm.companyName || 'Verified Asset'} • {orderForm.sector || 'NSE Segment'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                    Segment
                  </label>
                  <select
                    value={orderForm.exchangeSegment}
                    onChange={(e) => setOrderForm({ ...orderForm, exchangeSegment: e.target.value })}
                    className="input-field"
                    style={{ width: '100%' }}
                  >
                    <option value="NSE_EQ">NSE_EQ (Cash)</option>
                    <option value="NSE_FNO">NSE_FNO (F&O)</option>
                    <option value="BSE_EQ">BSE_EQ</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                    Product
                  </label>
                  <select
                    value={orderForm.productType}
                    onChange={(e) => setOrderForm({ ...orderForm, productType: e.target.value })}
                    className="input-field"
                    style={{ width: '100%' }}
                  >
                    <option value="INTRADAY">INTRADAY (MIS)</option>
                    <option value="CNC">CNC (Delivery)</option>
                    <option value="MARGIN">MARGIN (F&O)</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                    Order Type
                  </label>
                  <select
                    value={orderForm.orderType}
                    onChange={(e) => setOrderForm({ ...orderForm, orderType: e.target.value })}
                    className="input-field"
                    style={{ width: '100%' }}
                  >
                    <option value="MARKET">MARKET</option>
                    <option value="LIMIT">LIMIT</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                    Quantity
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={orderForm.quantity}
                    onChange={(e) => setOrderForm({ ...orderForm, quantity: e.target.value })}
                    className="input-field font-mono"
                    required
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              {orderForm.orderType === 'LIMIT' && (
                <div>
                  <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                    Limit Price (₹) *
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    value={orderForm.price}
                    onChange={(e) => setOrderForm({ ...orderForm, price: e.target.value })}
                    className="input-field font-mono"
                    required
                    style={{ width: '100%' }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsOrderModalOpen(false)}
                  className="btn btn-secondary"
                  style={{ padding: '8px 16px' }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={placingOrder}
                  className="btn btn-primary"
                  style={{
                    padding: '8px 24px',
                    background: orderForm.transactionType === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                  }}
                >
                  {placingOrder ? 'Routing to Dhan...' : `Place ${orderForm.transactionType} Order`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BrokerBindingView;
