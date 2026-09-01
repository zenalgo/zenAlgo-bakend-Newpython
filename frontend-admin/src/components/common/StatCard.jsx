import React from 'react';

export const StatCard = ({ title, value, subtitle, icon: Icon, color = 'cyan', trend }) => {
  const colorMap = {
    cyan: 'var(--accent-cyan)',
    emerald: 'var(--accent-emerald)',
    amber: 'var(--accent-amber)',
    rose: 'var(--accent-rose)',
    purple: 'var(--accent-purple)',
  };

  const accent = colorMap[color] || colorMap.cyan;

  return (
    <div className="glass-panel" style={{ padding: '20px', position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {title}
          </span>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '6px', fontFamily: 'Outfit, sans-serif' }}>
            {value}
          </div>
        </div>
        {Icon && (
          <div style={{
            padding: '10px',
            borderRadius: '10px',
            background: `rgba(255, 255, 255, 0.05)`,
            color: accent,
            border: `1px solid ${accent}33`,
          }}>
            <Icon size={22} />
          </div>
        )}
      </div>
      {(subtitle || trend) && (
        <div style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          {trend && <span style={{ color: trend > 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)', fontWeight: 600 }}>{trend > 0 ? `+${trend}%` : `${trend}%`}</span>}
          <span>{subtitle}</span>
        </div>
      )}
    </div>
  );
};

export default StatCard;
