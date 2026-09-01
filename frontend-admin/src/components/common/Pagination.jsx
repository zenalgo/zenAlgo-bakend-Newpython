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
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '14px 0 4px 0',
      borderTop: '1px solid var(--border-subtle)',
      flexWrap: 'wrap',
      gap: '12px',
      fontSize: '0.85rem',
      color: 'var(--text-muted)',
    }}>
      {/* Items range & Page Size selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span>
          Showing <strong style={{ color: '#fff' }}>{startItem}</strong> to <strong style={{ color: '#fff' }}>{endItem}</strong> of{' '}
          <strong style={{ color: '#fff' }}>{totalItems}</strong> entries
        </span>

        {onPageSizeChange && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="input-field"
              style={{ padding: '2px 8px', fontSize: '0.8rem', height: '28px', width: '70px' }}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Pagination Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 0}
          className="btn btn-secondary"
          style={{ padding: '4px 8px', height: '28px' }}
          title="Previous Page"
        >
          <ChevronLeft size={16} />
        </button>

        {Array.from({ length: totalPages }, (_, i) => i)
          .filter((p) => p === 0 || p === totalPages - 1 || Math.abs(p - currentPage) <= 1)
          .map((p, idx, arr) => {
            const showEllipsis = idx > 0 && p - arr[idx - 1] > 1;
            return (
              <React.Fragment key={p}>
                {showEllipsis && <span style={{ padding: '0 4px', color: 'var(--text-dim)' }}>...</span>}
                <button
                  onClick={() => onPageChange(p)}
                  className={`btn ${currentPage === p ? 'btn-primary' : 'btn-secondary'}`}
                  style={{
                    padding: '2px 10px',
                    height: '28px',
                    minWidth: '28px',
                    fontSize: '0.8rem',
                    fontWeight: currentPage === p ? 700 : 500,
                  }}
                >
                  {p + 1}
                </button>
              </React.Fragment>
            );
          })}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages - 1}
          className="btn btn-secondary"
          style={{ padding: '4px 8px', height: '28px' }}
          title="Next Page"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};

export default Pagination;
