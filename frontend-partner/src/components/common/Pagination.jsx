import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export const Pagination = ({
  currentPage = 0,
  pageSize = 10,
  totalItems = 0,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [5, 10, 20, 50],
}) => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const startItem = totalItems === 0 ? 0 : currentPage * pageSize + 1;
  const endItem = Math.min((currentPage + 1) * pageSize, totalItems);

  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        <span>Showing <strong style={{ color: '#fff' }}>{startItem}</strong> to <strong style={{ color: '#fff' }}>{endItem}</strong> of <strong style={{ color: '#fff' }}>{totalItems}</strong> records</span>
        
        {onPageSizeChange && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>Rows:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="input-field"
              style={{ width: '70px', padding: '4px 8px', fontSize: '0.8rem' }}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 0}
          className="btn btn-secondary"
          style={{ padding: '6px 10px', fontSize: '0.8rem', opacity: currentPage <= 0 ? 0.4 : 1 }}
        >
          <ChevronLeft size={16} />
          <span>Prev</span>
        </button>

        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', minWidth: '80px', textAlign: 'center' }}>
          Page <strong style={{ color: 'var(--accent-cyan)' }}>{currentPage + 1}</strong> of <strong>{totalPages}</strong>
        </span>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages - 1}
          className="btn btn-secondary"
          style={{ padding: '6px 10px', fontSize: '0.8rem', opacity: currentPage >= totalPages - 1 ? 0.4 : 1 }}
        >
          <span>Next</span>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};
