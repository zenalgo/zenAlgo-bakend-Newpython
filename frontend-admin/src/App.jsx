import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { Navbar } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';
import { DashboardPage } from './components/dashboard/DashboardPage';
import { StrategyListPage } from './components/strategy/StrategyListPage';
import { StrategyBuilderPage } from './components/strategy/StrategyBuilderPage';
import { PlacedOrdersPage } from './components/execution/PlacedOrdersPage';
import { BatchAuditingPage } from './components/execution/BatchAuditingPage';
import { SubscriptionPlansPage } from './components/plans/SubscriptionPlansPage';
import { SubscriptionApprovalsPage } from './components/subscriptions/SubscriptionApprovalsPage';
import { PaymentSettingsPage } from './components/payments/PaymentSettingsPage';
import { WalletPage } from './components/wallets/WalletPage';
import { UserManagementPage } from './components/users/UserManagementPage';
import { BrokerSettingsPage } from './components/brokers/BrokerSettingsPage';
import { SimulateExecutionModal } from './components/common/SimulateExecutionModal';
import { ExecutionLogsPage } from './components/execution/ExecutionLogsPage';
import { ConnectedBrokersPage } from './components/brokers/ConnectedBrokersPage';
import { ReportsPage } from './components/reports/ReportsPage';
import { CalculationEnginePage } from './components/calculation-engine/CalculationEnginePage';

export const App = () => {
  const { isAuthenticated } = useAuth();
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [selectedStrategyId, setSelectedStrategyId] = useState(null);
  const [editingStrategyId, setEditingStrategyId] = useState(null);
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return <DashboardPage onNavigate={setCurrentTab} />;
      case 'strategies':
        return (
          <StrategyListPage
            onNavigateToBuilder={(editId) => {
              setEditingStrategyId(editId || null);
              setCurrentTab('builder');
            }}
            onNavigateToOrders={(stratId) => {
              setSelectedStrategyId(stratId);
              setCurrentTab('placed-orders');
            }}
            onNavigateToBatches={(stratId) => {
              setSelectedStrategyId(stratId);
              setCurrentTab('batches');
            }}
          />
        );
      case 'builder':
        return (
          <StrategyBuilderPage
            onNavigate={setCurrentTab}
            editingStrategyId={editingStrategyId}
            onClearEditing={() => setEditingStrategyId(null)}
          />
        );
      case 'placed-orders':
        return <PlacedOrdersPage selectedStrategyId={selectedStrategyId} />;
      case 'batches':
        return <BatchAuditingPage selectedStrategyId={selectedStrategyId} />;
      case 'approvals':
        return <SubscriptionApprovalsPage />;
      case 'payment-settings':
        return <PaymentSettingsPage />;
      case 'plans':
        return <SubscriptionPlansPage />;
      case 'wallets':
        return <WalletPage />;
      case 'users':
        return <UserManagementPage />;
      case 'brokers':
        return <BrokerSettingsPage />;
      case 'execution-logs':
        return <ExecutionLogsPage />;
      case 'connected-brokers':
        return <ConnectedBrokersPage />;
      case 'reports':
        return <ReportsPage />;
      case 'calc-engine':
        return <CalculationEnginePage />;
      default:
        return <DashboardPage onNavigate={setCurrentTab} />;
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-main)' }}>
      <Navbar onOpenSimulate={() => setIsSimulateOpen(true)} />
      <div style={{ display: 'flex', flex: 1 }}>
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />
        <main style={{ flex: 1, padding: '32px', maxWidth: '1400px', width: '100%' }}>
          {renderContent()}
        </main>
      </div>

      <SimulateExecutionModal
        isOpen={isSimulateOpen}
        onClose={() => setIsSimulateOpen(false)}
        onRefreshData={() => {}}
      />
    </div>
  );
};

export default App;
