import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Search,
  Building2,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Wallet,
  ArrowRight,
  TrendingUp,
  X,
  FileText,
  Clock,
  Layers,
  Percent,
  DollarSign,
  Tag,
  Calculator
} from 'lucide-react';
import { brokerApi } from '../../api/brokerApi';
import { useBroker } from '../../context/BrokerContext';
import { useToast } from '../../context/ToastContext';

export const OrderTestbedPage = ({ onNavigate }) => {
  const { isBrokerConnected, brokerSession } = useBroker();
  const { addToast } = useToast();

  // Live Funds State
  const [funds, setFunds] = useState(null);
  const [loadingFunds, setLoadingFunds] = useState(false);

  // Stock Search & Autocomplete State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loadingQuote, setLoadingQuote] = useState(false);

  // Selected Stock State
  const [selectedStock, setSelectedStock] = useState({
    symbol: 'TATAGOLD',
    companyName: 'Tata Gold ETF',
    securityId: '21401',
    exchangeSegment: 'NSE_EQ',
    sector: 'Commodities & ETFs',
    lotSize: 1,
    lastPrice: 14.82,
    prevClose: 14.54,
    changePct: 1.93,
    dayHigh: 14.90,
    dayLow: 14.53,
  });

  // Sector Filter
  const [sectors, setSectors] = useState([]);
  const [selectedSector, setSelectedSector] = useState('ALL');

  // Order Parameters
  const [transactionType, setTransactionType] = useState('BUY'); // BUY | SELL
  const [orderType, setOrderType] = useState('MARKET'); // MARKET | LIMIT
  const [productType, setProductType] = useState('CNC'); // CNC | INTRADAY | MARGIN
  const [quantity, setQuantity] = useState(2); // Default to 2 shares as user requested
  const [limitPrice, setLimitPrice] = useState(14.82);
  const [validity, setValidity] = useState('DAY');

  // Execution & Recent Orders State
  const [submitting, setSubmitting] = useState(false);
  const [lastExecutionResult, setLastExecutionResult] = useState(null);
  const [recentOrders, setRecentOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);

  const searchDebounceTimer = useRef(null);

  // Popular Quick-Picks
  const quickPicks = [
    { symbol: 'SUZLON', name: 'Suzlon Energy Limited', secId: '12018', price: 46.03, changePct: 1.25 },
    { symbol: 'TATAGOLD', name: 'Tata Gold ETF', secId: '21401', price: 14.82, changePct: 1.93 },
    { symbol: 'RELIANCE', name: 'Reliance Industries', secId: '2885', price: 2980.0, changePct: 0.45 },
    { symbol: 'HDFCBANK', name: 'HDFC Bank Limited', secId: '1333', price: 1650.0, changePct: -0.20 },
    { symbol: 'SBIN', name: 'State Bank of India', secId: '3045', price: 820.0, changePct: 0.80 },
    { symbol: 'MARUTI', name: 'Maruti Suzuki India Limited', secId: '10999', price: 12850.0, changePct: 0.15 },
  ];

  // Fetch Live Funds
  const fetchFunds = async () => {
    if (!isBrokerConnected) return;
    setLoadingFunds(true);
    try {
      const res = await brokerApi.getDhanFunds();
      const fundsData = res?.data || res;
      setFunds(fundsData);
    } catch (err) {
      console.warn('Could not load live funds:', err);
    } finally {
      setLoadingFunds(false);
    }
  };

  // Fetch Sectors
  const fetchSectors = async () => {
    try {
      const res = await brokerApi.getInstrumentSectors();
      const data = res?.data || res;
      setSectors(Array.isArray(data) ? data : []);
    } catch (err) {
      console.warn('Could not load sectors:', err);
    }
  };

  // Fetch Recent Orders
  const fetchRecentOrders = async () => {
    if (!isBrokerConnected) return;
    setLoadingOrders(true);
    try {
      const res = await brokerApi.getDhanOrders();
      const orderList = res?.data || res;
      setRecentOrders(Array.isArray(orderList) ? orderList : []);
    } catch (err) {
      console.warn('Could not load recent orders:', err);
    } finally {
      setLoadingOrders(false);
    }
  };

  // Fetch full live quote for currently selected stock
  const fetchSelectedStockQuote = async (symbol) => {
    setLoadingQuote(true);
    try {
      const res = await brokerApi.getInstrumentQuote(symbol, 'DHAN');
      const quote = res?.data || res;
      if (quote && quote.lastPrice) {
        setSelectedStock((prev) => ({
          ...prev,
          lastPrice: quote.lastPrice,
          prevClose: quote.prevClose,
          change: quote.change,
          changePct: quote.changePct,
          dayHigh: quote.dayHigh,
          dayLow: quote.dayLow,
          lotSize: quote.lotSize || 1,
        }));
        setLimitPrice(quote.lastPrice);
      }
    } catch (err) {
      console.warn(`Could not fetch quote for ${symbol}:`, err);
    } finally {
      setLoadingQuote(false);
    }
  };

  useEffect(() => {
    fetchFunds();
    fetchSectors();
    fetchRecentOrders();
    fetchSelectedStockQuote(selectedStock.symbol);
  }, [isBrokerConnected]);

  // Live Stock Autocomplete with 200ms debounce
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    if (searchDebounceTimer.current) {
      clearTimeout(searchDebounceTimer.current);
    }

    searchDebounceTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await brokerApi.searchInstruments(searchQuery.trim(), 'DHAN', 12);
        const results = res?.data || res;
        setSearchResults(Array.isArray(results) ? results : []);
        setShowDropdown(true);
      } catch (err) {
        console.warn('Stock search error:', err);
      } finally {
        setSearching(false);
      }
    }, 200);

    return () => {
      if (searchDebounceTimer.current) clearTimeout(searchDebounceTimer.current);
    };
  }, [searchQuery]);

  const handleSelectStock = async (stk) => {
    const initialPrice = stk.lastPrice || stk.price || 100.0;
    setSelectedStock({
      symbol: stk.symbol,
      companyName: stk.companyName || stk.name,
      securityId: stk.securityId || stk.secId,
      exchangeSegment: stk.exchangeSegment || 'NSE_EQ',
      sector: stk.sector || 'NSE F&O',
      lotSize: stk.lotSize || 1,
      lastPrice: initialPrice,
      prevClose: stk.prevClose,
      changePct: stk.changePct,
      dayHigh: stk.dayHigh,
      dayLow: stk.dayLow,
    });
    setLimitPrice(initialPrice);
    setSearchQuery('');
    setShowDropdown(false);

    // Fetch live quote for selected stock
    await fetchSelectedStockQuote(stk.symbol);
  };

  // Calculations for Current Price & Total Price & 50% Balance Allocation Rule
  const currentStockPrice = Number(selectedStock?.lastPrice || limitPrice || 0);
  const effectivePricePerShare = orderType === 'LIMIT' ? Number(limitPrice || currentStockPrice) : currentStockPrice;
  const calculatedTotalPrice = Number(quantity) * effectivePricePerShare;

  const availableBalance = Number(funds?.availableBalance || funds?.sodLimit || 0);
  const maxAllowedAllocation = availableBalance * 0.5;
  const allocationPercentage = availableBalance > 0 ? ((calculatedTotalPrice / availableBalance) * 100).toFixed(1) : 0;
  const exceedsFiftyPercent = availableBalance > 0 && calculatedTotalPrice > maxAllowedAllocation;

  // Handle Order Submission
  const handlePlaceOrder = async (e) => {
    e.preventDefault();
    if (!isBrokerConnected) {
      addToast('Please connect your Dhan HQ account before placing orders.', 'warning');
      return;
    }

    if (!selectedStock || !selectedStock.securityId) {
      addToast('Please search and select a valid stock.', 'error');
      return;
    }

    if (quantity <= 0) {
      addToast('Order quantity must be at least 1.', 'error');
      return;
    }

    setSubmitting(true);
    setLastExecutionResult(null);

    const payload = {
      tradingSymbol: selectedStock.symbol,
      securityId: String(selectedStock.securityId),
      exchangeSegment: selectedStock.exchangeSegment || 'NSE_EQ',
      transactionType: transactionType,
      quantity: Number(quantity),
      orderType: orderType,
      productType: productType,
      price: orderType === 'LIMIT' ? Number(limitPrice) : 0,
      validity: validity,
    };

    try {
      const res = await brokerApi.placeDhanOrder(payload);
      const data = res?.data || res;
      setLastExecutionResult({
        success: true,
        orderId: data.brokerOrderId || data.orderId,
        status: data.orderStatus || 'PENDING',
        message: 'Order successfully dispatched to Dhan HQ!',
        tradingSymbol: selectedStock.symbol,
        quantity: quantity,
        price: effectivePricePerShare,
        orderValue: calculatedTotalPrice,
        timestamp: new Date().toLocaleTimeString(),
      });
      addToast(`Order placed successfully on Dhan! Order ID: ${data.brokerOrderId || data.orderId}`, 'success');
      fetchRecentOrders();
      fetchFunds();
    } catch (err) {
      const errorMsg = err.message || err.detail || 'Order placement rejected.';
      setLastExecutionResult({
        success: false,
        status: 'REJECTED',
        message: errorMsg,
        tradingSymbol: selectedStock.symbol,
        quantity: quantity,
        price: effectivePricePerShare,
        orderValue: calculatedTotalPrice,
        timestamp: new Date().toLocaleTimeString(),
      });
      addToast(errorMsg, 'error');
      fetchRecentOrders();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Manual Order Placement Terminal</h1>
            <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', fontSize: '0.75rem', fontWeight: 700 }}>
              TESTBED MODE
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            Live Stock Price (LTP) & Total Price Calculator. Execute manual test orders with real-time 50% balance allocation guard.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => {
              fetchFunds();
              fetchRecentOrders();
              if (selectedStock?.symbol) fetchSelectedStockQuote(selectedStock.symbol);
            }}
            disabled={loadingFunds || loadingOrders || loadingQuote}
            className="btn btn-secondary"
            style={{ padding: '8px 14px' }}
          >
            <RefreshCw size={15} className={loadingFunds || loadingOrders || loadingQuote ? 'animate-spin' : ''} />
            <span>Sync Live Prices & Margin</span>
          </button>
        </div>
      </div>

      {/* Broker Connection HUD Banner */}
      {!isBrokerConnected && (
        <div
          className="glass-panel"
          style={{
            padding: '16px 20px',
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            borderRadius: '10px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <AlertTriangle size={24} color="var(--accent-amber)" />
            <div>
              <div style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>Dhan HQ Account Disconnected</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                You must connect your active Dhan HQ broker session for today before submitting live orders.
              </div>
            </div>
          </div>
          {onNavigate && (
            <button
              onClick={() => onNavigate('trader-broker')}
              className="btn btn-amber"
              style={{ padding: '8px 16px' }}
            >
              <span>Connect Dhan Broker &rarr;</span>
            </button>
          )}
        </div>
      )}

      {/* Real-Time Balance, Current Price & Total Price HUD Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {/* Available Live Margin */}
        <div className="glass-panel" style={{ padding: '18px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700 }}>
            <span>AVAILABLE TRADING MARGIN</span>
            <Wallet size={16} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '8px' }}>
            ₹{availableBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            Live cash balance from connected Dhan HQ
          </div>
        </div>

        {/* Max 50% Allowed Order Value */}
        <div className="glass-panel" style={{ padding: '18px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700 }}>
            <span>50% ALLOCATION LIMIT</span>
            <ShieldCheck size={16} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '8px' }}>
            ₹{maxAllowedAllocation.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>● Max single order value allowed</span>
          </div>
        </div>

        {/* Current Stock Price (LTP) */}
        <div className="glass-panel" style={{ padding: '18px', borderLeft: '4px solid var(--accent-purple)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700 }}>
            <span>CURRENT STOCK PRICE (LTP)</span>
            <TrendingUp size={16} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-purple)', marginTop: '8px', display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            ₹{currentStockPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>/ share</span>
          </div>
          <div style={{ fontSize: '0.72rem', marginTop: '4px', display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, color: (selectedStock?.changePct || 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
              {(selectedStock?.changePct || 0) >= 0 ? '▲ +' : '▼ '}{Number(selectedStock?.changePct || 0).toFixed(2)}% Today
            </span>
            <span style={{ color: 'var(--text-dim)' }}>({selectedStock?.symbol})</span>
          </div>
        </div>

        {/* Calculated Total Price & 50% Rule Status */}
        <div
          className="glass-panel"
          style={{
            padding: '18px',
            borderLeft: `4px solid ${exceedsFiftyPercent ? 'var(--accent-rose)' : 'var(--accent-emerald)'}`,
            background: exceedsFiftyPercent ? 'rgba(244, 63, 94, 0.08)' : 'var(--bg-card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700 }}>
            <span>TOTAL PRICE ({quantity} SHARES)</span>
            <Calculator size={16} color={exceedsFiftyPercent ? 'var(--accent-rose)' : 'var(--accent-emerald)'} />
          </div>
          <div
            style={{
              fontSize: '1.6rem',
              fontWeight: 900,
              color: exceedsFiftyPercent ? 'var(--accent-rose)' : 'var(--accent-emerald)',
              marginTop: '8px',
            }}
          >
            ₹{calculatedTotalPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.72rem', color: exceedsFiftyPercent ? 'var(--accent-rose)' : 'var(--accent-emerald)', marginTop: '4px', fontWeight: 700 }}>
            {exceedsFiftyPercent ? `❌ EXCEEDS 50% CAP (${allocationPercentage}%)` : `✅ WITHIN 50% CAP (${allocationPercentage}%)`}
          </div>
        </div>
      </div>

      {/* Main Order Workspace Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '24px' }}>
        {/* Left Column: Stock Search & Selection */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '14px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Search size={18} color="var(--accent-cyan)" />
              <span>Step 1: Search Stock & View Live Price</span>
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Search across 210 NSE F&O stocks and ETFs. Live Market Price (LTP) is displayed for each stock.
            </p>
          </div>

          {/* Autocomplete Search Bar */}
          <div style={{ position: 'relative' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
              <span>Search Stock / ETF Ticker or Company Name</span>
              {searching && <span style={{ color: 'var(--accent-cyan)', fontSize: '0.75rem' }}>Fetching live prices...</span>}
            </label>
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                id="testbed-stock-search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => { if (searchResults.length > 0) setShowDropdown(true); }}
                placeholder="Type 'Suzlon', 'Tata Gold', 'Reliance', 'Maruti', 'HDFC'..."
                className="input-field"
                style={{
                  width: '100%',
                  padding: '12px 14px 12px 38px',
                  background: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '0.9rem',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => { setSearchQuery(''); setShowDropdown(false); }}
                  style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <X size={15} />
                </button>
              )}
            </div>

            {/* Dropdown Results with Live Prices */}
            {showDropdown && searchResults.length > 0 && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  zIndex: 50,
                  marginTop: '6px',
                  maxHeight: '280px',
                  overflowY: 'auto',
                  background: 'rgba(15, 23, 42, 0.98)',
                  border: '1px solid var(--border-highlight)',
                  borderRadius: '8px',
                  boxShadow: '0 16px 36px rgba(0,0,0,0.8)',
                }}
              >
                {searchResults.map((stk) => (
                  <div
                    key={`${stk.symbol}-${stk.securityId}`}
                    onClick={() => handleSelectStock(stk)}
                    style={{
                      padding: '12px 16px',
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
                        <span style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>{stk.symbol}</span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', background: 'rgba(56, 189, 248, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>
                          {stk.exchangeSegment}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.15)', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                          SecID: {stk.securityId}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                        {stk.companyName}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      {stk.lastPrice != null ? (
                        <>
                          <div style={{ fontSize: '1rem', fontWeight: 900, color: 'var(--accent-emerald)' }}>
                            ₹{Number(stk.lastPrice).toFixed(2)}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            1 Share per Lot
                          </div>
                        </>
                      ) : (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                          {stk.sector}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick-Pick Popular Stocks with Live Prices */}
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '8px' }}>
              POPULAR QUICK PICKS:
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {quickPicks.map((p) => (
                <button
                  key={p.symbol}
                  type="button"
                  onClick={() => handleSelectStock(p)}
                  className="btn"
                  style={{
                    padding: '6px 12px',
                    fontSize: '0.75rem',
                    borderRadius: '6px',
                    background: selectedStock?.symbol === p.symbol ? 'rgba(56, 189, 248, 0.25)' : 'rgba(30, 41, 59, 0.6)',
                    borderColor: selectedStock?.symbol === p.symbol ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                    color: selectedStock?.symbol === p.symbol ? 'var(--accent-cyan)' : 'var(--text-muted)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    gap: '2px',
                  }}
                >
                  <span style={{ fontWeight: 800, color: selectedStock?.symbol === p.symbol ? 'var(--accent-cyan)' : '#fff' }}>
                    {p.symbol}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)' }}>
                    ₹{p.price.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Selected Stock Live Price & Details Card */}
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(5, 150, 105, 0.02) 100%)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '10px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>SELECTED SCRIP</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 900, color: '#fff', marginTop: '2px' }}>
                  {selectedStock?.symbol}
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {selectedStock?.companyName}
                </div>
              </div>

              <span className="badge badge-active" style={{ fontSize: '0.75rem' }}>
                {selectedStock?.exchangeSegment || 'NSE_EQ'}
              </span>
            </div>

            {/* Prominent Live Price & Trade Unit Box */}
            <div
              style={{
                background: 'rgba(15, 23, 42, 0.85)',
                border: '1px solid var(--border-highlight)',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                  CURRENT MARKET PRICE (LTP)
                </div>
                <div style={{ fontSize: '1.7rem', fontWeight: 900, color: 'var(--accent-emerald)', marginTop: '2px' }}>
                  ₹{currentStockPrice.toFixed(2)}
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500, marginLeft: '6px' }}>/ share</span>
                </div>
                {selectedStock?.changePct != null && (
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: (selectedStock.changePct || 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)', marginTop: '2px' }}>
                    {(selectedStock.changePct || 0) >= 0 ? '▲ +' : '▼ '}{Number(selectedStock.changePct).toFixed(2)}% Today
                  </div>
                )}
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>TRADE UNIT</div>
                <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                  1 Share per Lot
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', marginTop: '2px' }}>
                  Buy any quantity (1, 2, 5, 10...)
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', paddingTop: '4px', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                Dhan SecID: {selectedStock?.securityId}
              </span>
              <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                Sector: {selectedStock?.sector}
              </span>
              {selectedStock?.dayHigh && (
                <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
                  High: ₹{selectedStock.dayHigh} | Low: ₹{selectedStock.dayLow}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Order Configuration & Total Price Calculator Form */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '14px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calculator size={18} color="var(--accent-emerald)" />
              <span>Step 2: Choose Quantity & View Total Price</span>
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Configure quantity to buy (e.g. 2 shares) and see the exact total price before placing order.
            </p>
          </div>

          <form onSubmit={handlePlaceOrder} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Side Toggle: BUY vs SELL */}
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                Order Side (Transaction Type) *
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setTransactionType('BUY')}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    fontWeight: 800,
                    fontSize: '0.95rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    border: transactionType === 'BUY' ? '2px solid var(--accent-emerald)' : '1px solid var(--border-subtle)',
                    background: transactionType === 'BUY' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                    color: transactionType === 'BUY' ? 'var(--accent-emerald)' : 'var(--text-muted)',
                  }}
                >
                  BUY (LONG)
                </button>

                <button
                  type="button"
                  onClick={() => setTransactionType('SELL')}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    fontWeight: 800,
                    fontSize: '0.95rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    border: transactionType === 'SELL' ? '2px solid var(--accent-rose)' : '1px solid var(--border-subtle)',
                    background: transactionType === 'SELL' ? 'rgba(244, 63, 94, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                    color: transactionType === 'SELL' ? 'var(--accent-rose)' : 'var(--text-muted)',
                  }}
                >
                  SELL (SHORT)
                </button>
              </div>
            </div>

            {/* Product Type & Order Type */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                  Product Type *
                </label>
                <select
                  value={productType}
                  onChange={(e) => setProductType(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    background: 'rgba(15, 23, 42, 0.9)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="CNC">CNC (Delivery / Cash & Carry)</option>
                  <option value="INTRADAY">INTRADAY (MIS)</option>
                  <option value="MARGIN">MARGIN (MTF)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                  Order Type *
                </label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    background: 'rgba(15, 23, 42, 0.9)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="MARKET">MARKET (Execute at Current LTP)</option>
                  <option value="LIMIT">LIMIT (Specific Price)</option>
                </select>
              </div>
            </div>

            {/* Quantity Stepper & Quick Quantity Chips */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Quantity to Buy (Shares) *</label>
                <div style={{ display: 'flex', gap: '6px' }}>
                  {[1, 2, 5, 10, 25, 50, 100].map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setQuantity(q)}
                      style={{
                        padding: '2px 8px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        background: quantity === q ? 'rgba(56, 189, 248, 0.25)' : 'rgba(30, 41, 59, 0.6)',
                        border: '1px solid',
                        borderColor: quantity === q ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                        color: quantity === q ? 'var(--accent-cyan)' : 'var(--text-muted)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  className="btn btn-secondary"
                  style={{ padding: '8px 14px' }}
                >
                  -
                </button>
                <input
                  id="testbed-quantity-input"
                  type="number"
                  min="1"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: '6px',
                    background: 'rgba(15, 23, 42, 0.9)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    fontWeight: 700,
                    textAlign: 'center',
                    fontSize: '1.05rem',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setQuantity(quantity + 1)}
                  className="btn btn-secondary"
                  style={{ padding: '8px 14px' }}
                >
                  +
                </button>
              </div>
            </div>

            {/* Price (Locked to LTP for MARKET, or Editable for LIMIT) */}
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                <span>{orderType === 'LIMIT' ? 'Limit Price (₹ / share) *' : 'Current Market Execution Price (₹ / share)'}</span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                  {orderType === 'MARKET' ? 'Auto-synced with live stock quote' : 'Enter desired execution price'}
                </span>
              </label>
              <input
                type="number"
                step="0.05"
                min="0.05"
                value={orderType === 'MARKET' ? currentStockPrice : limitPrice}
                disabled={orderType === 'MARKET'}
                onChange={(e) => setLimitPrice(parseFloat(e.target.value) || 0)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  background: orderType === 'MARKET' ? 'rgba(30, 41, 59, 0.4)' : 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                }}
              />
            </div>

            {/* Total Price & Investment Summary Box */}
            <div
              style={{
                background: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                borderRadius: '8px',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Stock Current Price:</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#fff' }}>
                  ₹{effectivePricePerShare.toFixed(2)} / share
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Quantity to Buy:</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                  {quantity} shares
                </span>
              </div>

              <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#fff' }}>TOTAL PRICE (Investment):</span>
                <span
                  style={{
                    fontSize: '1.45rem',
                    fontWeight: 900,
                    color: exceedsFiftyPercent ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                  }}
                >
                  ₹{calculatedTotalPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textAlign: 'right' }}>
                ({quantity} shares &times; ₹{effectivePricePerShare.toFixed(2)} = ₹{calculatedTotalPrice.toFixed(2)})
              </div>
            </div>

            {/* Dynamic 50% Rule Warning / Confirmation Banner */}
            {exceedsFiftyPercent ? (
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '8px',
                  background: 'rgba(244, 63, 94, 0.12)',
                  border: '1px solid rgba(244, 63, 94, 0.4)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  color: 'var(--accent-rose)',
                  fontSize: '0.82rem',
                  lineHeight: '1.4',
                }}
              >
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong>50% Balance Cap Exceeded:</strong> Total Price of ₹{calculatedTotalPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })} exceeds your 50% allocation limit (Max: ₹{maxAllowedAllocation.toLocaleString('en-IN', { minimumFractionDigits: 2 })}).
                  The risk engine will block this order and save the audit rejection in DB.
                </div>
              </div>
            ) : (
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '8px',
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: 'var(--accent-emerald)',
                  fontSize: '0.82rem',
                }}
              >
                <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
                <div>
                  <strong>Risk Rule Verified:</strong> Total Price (₹{calculatedTotalPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}) is well within 50% of your available margin (Max Allowed: ₹{maxAllowedAllocation.toLocaleString('en-IN', { minimumFractionDigits: 2 })}).
                </div>
              </div>
            )}

            {/* Submit Button */}
            <button
              id="btn-submit-test-order"
              type="submit"
              disabled={submitting || !isBrokerConnected}
              className={transactionType === 'BUY' ? 'btn-emerald' : 'btn-danger'}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: '8px',
                fontSize: '1rem',
                fontWeight: 800,
                justifyContent: 'center',
                marginTop: '6px',
                cursor: !isBrokerConnected ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  <span>Transmitting to Dhan HQ...</span>
                </>
              ) : (
                <>
                  <Send size={18} />
                  <span>
                    Submit {transactionType} Order for {quantity} &times; {selectedStock?.symbol} (₹{calculatedTotalPrice.toFixed(2)})
                  </span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* Execution Response Banner Card */}
      {lastExecutionResult && (
        <div
          className="glass-panel"
          style={{
            padding: '20px 24px',
            border: `1px solid ${lastExecutionResult.success ? 'rgba(16, 185, 129, 0.5)' : 'rgba(244, 63, 94, 0.5)'}`,
            background: lastExecutionResult.success
              ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.04) 100%)'
              : 'linear-gradient(135deg, rgba(244, 63, 94, 0.12) 0%, rgba(190, 18, 60, 0.04) 100%)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            {lastExecutionResult.success ? (
              <CheckCircle2 size={32} color="var(--accent-emerald)" />
            ) : (
              <XCircle size={32} color="var(--accent-rose)" />
            )}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 800, color: lastExecutionResult.success ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                {lastExecutionResult.success ? 'ORDER PLACEMENT CONFIRMED' : 'ORDER PLACEMENT REJECTED'} (AT {lastExecutionResult.timestamp})
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                {lastExecutionResult.message}
              </div>
              {lastExecutionResult.orderId && (
                <div style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', marginTop: '4px', fontFamily: 'monospace' }}>
                  Dhan Order ID: {lastExecutionResult.orderId} | Status: {lastExecutionResult.status}
                </div>
              )}
            </div>
          </div>

          <button
            onClick={() => setLastExecutionResult(null)}
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.75rem' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Recent Orders Audit Table */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={18} color="var(--accent-cyan)" />
              <span>Today's Placed & Tested Orders (Live Audit Trail)</span>
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Real-time synchronization with Dhan HQ order book and database audit records.
            </p>
          </div>

          <button
            onClick={fetchRecentOrders}
            disabled={loadingOrders}
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <RefreshCw size={13} className={loadingOrders ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          {recentOrders.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '36px 20px', color: 'var(--text-muted)' }}>
              No orders placed today yet. Submit a test order above to verify execution.
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  <th style={{ padding: '10px 8px' }}>ORDER ID</th>
                  <th style={{ padding: '10px 8px' }}>SYMBOL</th>
                  <th style={{ padding: '10px 8px' }}>SIDE</th>
                  <th style={{ padding: '10px 8px' }}>PRODUCT</th>
                  <th style={{ padding: '10px 8px' }}>TYPE</th>
                  <th style={{ padding: '10px 8px' }}>QTY</th>
                  <th style={{ padding: '10px 8px' }}>PRICE</th>
                  <th style={{ padding: '10px 8px' }}>STATUS</th>
                  <th style={{ padding: '10px 8px' }}>DETAILS / REJECTION</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((o, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                    <td style={{ padding: '12px 8px', fontFamily: 'monospace', color: 'var(--accent-cyan)', fontSize: '0.8rem' }}>
                      {o.orderId || o.brokerOrderId || 'N/A'}
                    </td>
                    <td style={{ padding: '12px 8px', fontWeight: 800, color: '#fff' }}>
                      {o.tradingSymbol}
                    </td>
                    <td style={{ padding: '12px 8px' }}>
                      <span
                        style={{
                          fontWeight: 800,
                          color: (o.transactionType || '').toUpperCase() === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        }}
                      >
                        {o.transactionType}
                      </span>
                    </td>
                    <td style={{ padding: '12px 8px', color: 'var(--text-muted)' }}>{o.productType}</td>
                    <td style={{ padding: '12px 8px', color: 'var(--text-muted)' }}>{o.orderType}</td>
                    <td style={{ padding: '12px 8px', fontWeight: 700 }}>{o.quantity}</td>
                    <td style={{ padding: '12px 8px', fontFamily: 'monospace' }}>₹{Number(o.price || 0).toFixed(2)}</td>
                    <td style={{ padding: '12px 8px' }}>
                      <span
                        className="badge"
                        style={{
                          background:
                            o.orderStatus === 'TRADED' || o.orderStatus === 'FILLED'
                              ? 'rgba(16, 185, 129, 0.15)'
                              : o.orderStatus === 'REJECTED'
                              ? 'rgba(244, 63, 94, 0.15)'
                              : 'rgba(245, 158, 11, 0.15)',
                          color:
                            o.orderStatus === 'TRADED' || o.orderStatus === 'FILLED'
                              ? 'var(--accent-emerald)'
                              : o.orderStatus === 'REJECTED'
                              ? 'var(--accent-rose)'
                              : 'var(--accent-amber)',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                        }}
                      >
                        {o.orderStatus}
                      </span>
                    </td>
                    <td style={{ padding: '12px 8px', color: 'var(--text-muted)', fontSize: '0.75rem', maxWidth: '240px' }}>
                      {o.rejectionReason ? (
                        <span style={{ color: 'var(--accent-rose)' }}>{o.rejectionReason}</span>
                      ) : (
                        <span>Executed on {o.exchangeSegment || 'NSE_EQ'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
