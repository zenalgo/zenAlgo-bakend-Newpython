import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { Navbar } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';

// Partner Pages
import { PartnerDashboardPage } from './components/partner/PartnerDashboardPage';
import { ReferredClientsPage } from './components/partner/ReferredClientsPage';
import { CommissionLedgerPage } from './components/partner/CommissionLedgerPage';
import { PayoutsPage } from './components/partner/PayoutsPage';
import { MarketingLinksPage } from './components/partner/MarketingLinksPage';

// Trader Pages
import { TraderDashboardPage } from './components/trader/TraderDashboardPage';
import { StrategyMarketplacePage } from './components/trader/StrategyMarketplacePage';
import { TraderOrdersPage } from './components/trader/TraderOrdersPage';
import { TraderWalletPage } from './components/trader/TraderWalletPage';
import { BrokerBindingPage } from './components/trader/BrokerBindingPage';
import { MySubscriptionPage } from './components/trader/MySubscriptionPage';

export const App = () => {
  const { user, isAuthenticated, loading } = useAuth();
  const [currentTab, setCurrentTab] = useState('partner-dashboard');

  useEffect(() => {
    if (user?.role === 'PARTNER') {
      setCurrentTab('partner-dashboard');
    } else if (user?.role === 'TRADER' || user?.role === 'USER') {
      setCurrentTab('trader-dashboard');
    }
  }, [user?.role]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-main)', color: 'var(--text-muted)' }}>
        Loading ZenAlgo Portal...
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
      case 'partner-referrals':
        return <ReferredClientsPage />;
      case 'partner-commissions':
        return <CommissionLedgerPage />;
      case 'partner-payouts':
        return <PayoutsPage />;
      case 'partner-links':
        return <MarketingLinksPage />;

      // Trader Routes
      case 'trader-dashboard':
        return <TraderDashboardPage onNavigate={setCurrentTab} />;
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
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
