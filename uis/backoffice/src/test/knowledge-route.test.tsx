import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import KnowledgePage from '@/app/backoffice/knowledge/page';
const state = vi.hoisted(() => ({ user: null as object | null, loading: false, replace: vi.fn() }));
vi.mock('@/lib/auth', () => ({ useAuth: () => state }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: state.replace }) }));

beforeEach(() => { state.user = null; state.loading = false; state.replace.mockClear(); });
it('does not mount the form before session verification', () => {
  state.loading = true;
  render(<KnowledgePage />);
  expect(screen.queryByLabelText('Tu pregunta')).toBeNull();
  expect(state.replace).not.toHaveBeenCalled();
});
it('redirects anonymous users', () => {
  render(<KnowledgePage />);
  expect(screen.queryByLabelText('Tu pregunta')).toBeNull();
  expect(state.replace).toHaveBeenCalledWith('/login');
});
it('shows the form and navigation to authenticated users', () => {
  state.user = {};
  render(<KnowledgePage />);
  expect(screen.getByLabelText('Tu pregunta')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Conocimiento' })).toHaveClass('nav-link-active');
});
