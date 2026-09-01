import React from 'react';

export const StatusBadge = ({ status }) => {
  const norm = (status || 'UNKNOWN').toUpperCase();

  if (norm === 'RUNNING' || norm === 'FILLED' || norm === 'SUCCESS' || norm === 'ACTIVE' || norm === 'EXECUTED') {
    return <span className="badge badge-running"><span className="pulse-active"></span>{norm}</span>;
  }
  if (norm === 'MONITORING_ENTRY' || norm === 'PAPER') {
    return <span className="badge badge-paper"><span className="pulse-active"></span>{norm}</span>;
  }
  if (norm === 'MONITORING_EXIT' || norm === 'ORDER_PENDING') {
    return <span className="badge badge-paper" style={{ borderColor: 'var(--accent-purple)', color: 'var(--accent-purple)' }}>{norm}</span>;
  }
  if (norm === 'WAITING' || norm === 'DRAFT' || norm === 'PENDING') {
    return <span className="badge badge-waiting">{norm}</span>;
  }
  if (norm === 'FAILED' || norm === 'REJECTED' || norm === 'ERROR') {
    return <span className="badge badge-failed">{norm}</span>;
  }
  if (norm === 'ACTIVE_LIVE' || norm === 'LIVE') {
    return <span className="badge badge-live">{norm}</span>;
  }
  return <span className="badge badge-closed">{norm}</span>;
};

export default StatusBadge;
