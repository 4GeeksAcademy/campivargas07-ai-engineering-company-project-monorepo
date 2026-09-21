/**
 * useIncidents — React hooks for the Centralized Incident Manager
 */
'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  listIncidents,
  getIncident,
  createIncident,
  updateIncidentStatus,
  getIncidentsSummary,
  type Incident,
  type IncidentCreateRequest,
  type IncidentStatus,
  type IncidentSummary,
} from '@/lib/incidents-api';

// ---------------------------------------------------------------------------
// useIncidentList
// ---------------------------------------------------------------------------

export function useIncidentList(filters?: {
  status?: string;
  category?: string;
  branch?: string;
}) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const status = filters?.status;
  const category = filters?.category;
  const branch = filters?.branch;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listIncidents({ status, category, branch });
      setIncidents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading incidents');
    } finally {
      setLoading(false);
    }
  }, [status, category, branch]);

  useEffect(() => {
    let active = true;
    listIncidents({ status, category, branch })
      .then((data) => {
        if (active) {
          setIncidents(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Error loading incidents');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [status, category, branch]);

  return { incidents, loading, error, refresh };
}

// ---------------------------------------------------------------------------
// useIncidentDetail
// ---------------------------------------------------------------------------

export function useIncidentDetail(id: string | null) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getIncident(id);
      setIncident(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading incident');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let active = true;

    getIncident(id)
      .then((data) => {
        if (active) {
          setIncident(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Error loading incident');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [id]);

  return {
    incident: id ? incident : null,
    loading: id ? loading : false,
    error,
    refresh,
  };
}

// ---------------------------------------------------------------------------
// useIncidentMutations
// ---------------------------------------------------------------------------

export function useIncidentMutations() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(async (data: IncidentCreateRequest): Promise<Incident | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await createIncident(data);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating incident');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const transition = useCallback(
    async (id: string, newStatus: IncidentStatus): Promise<Incident | null> => {
      setLoading(true);
      setError(null);
      try {
        const result = await updateIncidentStatus(id, { status: newStatus });
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error updating status');
        return null;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { create, transition, loading, error };
}

// ---------------------------------------------------------------------------
// useIncidentSummary
// ---------------------------------------------------------------------------

export function useIncidentSummary() {
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIncidentsSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading summary');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getIncidentsSummary()
      .then((data) => {
        if (active) {
          setSummary(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Error loading summary');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return { summary, loading, error, refresh };
}
