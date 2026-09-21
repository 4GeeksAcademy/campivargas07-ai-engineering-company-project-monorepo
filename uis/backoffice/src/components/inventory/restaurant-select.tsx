'use client';

import { RESTAURANT_LOCATIONS } from '@/lib/constants/restaurants';

type RestaurantSelectProps = {
  id: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  includeAll?: boolean;
};

export function RestaurantSelect({
  id,
  label,
  value,
  onValueChange,
  includeAll = false,
}: RestaurantSelectProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
      <label
        htmlFor={id}
        style={{ fontSize: '0.82rem', color: 'var(--muted)', fontWeight: 600 }}
      >
        {label}:
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        style={{
          padding: '0.4rem 0.75rem',
          borderRadius: '0.5rem',
          background: '#07111f',
          border: '1px solid var(--border)',
          color: 'var(--fg)',
          fontSize: '0.86rem',
          outline: 'none',
          cursor: 'pointer',
        }}
      >
        {includeAll ? <option value="ALL">Todas las sedes</option> : null}
        {RESTAURANT_LOCATIONS.map((location) => (
          <option key={location.id} value={location.id}>
            {location.nombre} ({location.id})
          </option>
        ))}
      </select>
    </div>
  );
}
