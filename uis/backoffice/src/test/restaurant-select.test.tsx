import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RestaurantSelect } from '@/components/inventory/restaurant-select';

describe('RestaurantSelect', () => {
  it('renders the configured label and available restaurants', () => {
    render(
      <RestaurantSelect
        id="restaurant"
        label="Restaurante"
        value="MED-001"
        onValueChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Restaurante:')).toHaveValue('MED-001');
    expect(screen.getByRole('option', { name: /Brasaland El Poblado/i })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Todas las sedes' })).not.toBeInTheDocument();
  });

  it('supports the aggregate option and reports value changes', () => {
    const onValueChange = vi.fn();
    render(
      <RestaurantSelect
        id="restaurant-filter"
        label="Sede"
        value="ALL"
        onValueChange={onValueChange}
        includeAll
      />,
    );

    fireEvent.change(screen.getByLabelText('Sede:'), {
      target: { value: 'MIA-001' },
    });

    expect(screen.getByRole('option', { name: 'Todas las sedes' })).toBeInTheDocument();
    expect(onValueChange).toHaveBeenCalledWith('MIA-001');
  });
});
