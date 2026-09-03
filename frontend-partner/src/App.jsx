import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from './context/AuthContext';
import { useBroker } from './context/BrokerContext';
import { LoginPage } from './components/auth/LoginPage';
import { Navbar } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';
import { AlertCircle } from 'lucide-react';

// Partner Pages
import { PartnerDashboardPage } from './components/partner/PartnerDashboardPage';
import { ReferredClientsPage } from './components/partner/ReferredClientsPage';
import { CommissionLedgerPage } from './components/partner/CommissionLedgerPage';
import { PayoutsPage } from './components/partner/PayoutsPage';
import { PartnerBrokerPage } from './components/partner/PartnerBrokerPage';
import { MarketingLinksPage } from './components/partner/MarketingLinksPage';

// Trader Pages
import { TraderDashboardPage } from './components/trader/TraderDashboardPage';
import { StrategyMarketplacePage } from './components/trader/StrategyMarketplacePage';
import { TraderOrdersPage } from './components/trader/TraderOrdersPage';
import { TraderWalletPage } from './components/trader/TraderWalletPage';
import { BrokerBindingPage } from './components/trader/BrokerBindingPage';
import { MySubscriptionPage } from './components/trader/MySubscriptionPage';
import { OrderTestbedPage } from './components/trading/OrderTestbedPage';

export const App = () => {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const { isBrokerConnected, checkingBroker } = useBroker();

  const isPartner = user?.role === 'PARTNER';
  const brokerTabId = isPartner ? 'partner-broker' : 'trader-broker';
  const dashboardTabId = isPartner ? 'partner-dashboard' : 'trader-dashboard';

  const [currentTab, setCurrentTab] = useState(dashboardTabId);
  const hasInitializedTab = useRef(false);

  // Mandatory Broker Guard: If broker is NOT connected, force user to Broker Account tab!
  useEffect(() => {
    if (!checkingBroker && isAuthenticated && user) {
      if (!isBrokerConnected) {
        setCurrentTab(brokerTabId);
      } else if (!hasInitializedTab.current) {
        hasInitializedTab.current = true;
        setCurrentTab(dashboardTabId);
      }
    }
  }, [checkingBroker, isBrokerConnected, isAuthenticated, user, brokerTabId, dashboardTabId]);

  if (authLoading || (isAuthenticated && checkingBroker)) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-main)', color: 'var(--text-muted)', gap: '12px' }}>
        <div style={{ width: '36px', height: '36px', border: '3px solid rgba(56, 189, 248, 0.2)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        <div style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>Checking ZenAlgo Broker Authentication...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderContent = () => {
    switch (currentTab) {
      // Partner Routes
      case 'partner-dashboard':
        return <PartnerDashboardPage onNavigate={setCurrentTab} />;
      case 'partner-test-order':
        return <OrderTestbedPage onNavigate={setCurrentTab} />;
      case 'partner-referrals':
        return <ReferredClientsPage />;
      case 'partner-commissions':
        return <CommissionLedgerPage />;
      case 'partner-payouts':
        return <PayoutsPage />;
      case 'partner-broker':
        return <PartnerBrokerPage />;
      case 'partner-links':
        return <MarketingLinksPage />;

      // Trader Routes
      case 'trader-dashboard':
        return <TraderDashboardPage onNavigate={setCurrentTab} />;
      case 'trader-test-order':
        return <OrderTestbedPage onNavigate={setCurrentTab} />;
      case 'trader-strategies':
        return <StrategyMarketplacePage />;
      case 'trader-orders':
        return <TraderOrdersPage />;
      case 'trader-wallet':
        return <TraderWalletPage />;
      case 'trader-broker':
        return <BrokerBindingPage />;
      case 'trader-subscription':
        return <MySubscriptionPage />;

      default:
        return user?.role === 'PARTNER' ? <PartnerDashboardPage onNavigate={setCurrentTab} /> : <TraderDashboardPage onNavigate={setCurrentTab} />;
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-main)' }}>
      <Navbar />
      <div style={{ display: 'flex', flex: 1 }}>
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />
        <main style={{ flex: 1, padding: '32px', maxWidth: '1400px', width: '100%' }}>
          {!isBrokerConnected && (
            <div
              className="glass-panel"
              style={{
                marginBottom: '24px',
                padding: '14px 20px',
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                color: 'var(--accent-amber)',
              }}
            >
              <AlertCircle size={20} style={{ flexShrink: 0 }} />
              <div style={{ fontSize: '0.88rem', lineHeight: '1.4' }}>
                <strong>Dhan HQ Broker Connection Required:</strong> To access ZenAlgo trading features, copy-trading fleet, and analytics, you must connect your active Dhan HQ account below.
              </div>
            </div>
          )}
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
