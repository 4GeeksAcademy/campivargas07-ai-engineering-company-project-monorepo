'use client';

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { telemetryService } from '@/services/telemetry';

export function TelemetryBootstrap() {
  const pathname = usePathname();
  const previousRouteRef = useRef<string>('DIRECT_ENTRY');
  const routeStartTimeRef = useRef<number>(0);

  // Track page views on route change
  useEffect(() => {
    const now = typeof performance !== 'undefined' ? performance.now() : 0;
    const durationMs =
      routeStartTimeRef.current > 0 ? Math.max(0, Math.round(now - routeStartTimeRef.current)) : 0;

    telemetryService.track('backoffice_page_viewed', {
      previous_route: previousRouteRef.current,
      current_route: pathname || '/',
      navigation_duration_ms: durationMs,
    });

    previousRouteRef.current = pathname || '/';
    routeStartTimeRef.current = now;
  }, [pathname]);

  // Global uncaught error and unhandled promise rejection listeners
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handleError = (event: ErrorEvent) => {
      // Exclude telemetry own internal errors to prevent loop
      if (event.message && event.message.includes('[Telemetry]')) {
        return;
      }

      telemetryService.track('system_exception_captured', {
        exception_class: event.error?.name || 'ClientRuntimeError',
        error_code: 'UNHANDLED_CLIENT_EXCEPTION',
        origin_service: 'uis/backoffice',
      });
    };

    const handleRejection = () => {
      telemetryService.track('system_exception_captured', {
        exception_class: 'UnhandledPromiseRejection',
        error_code: 'UNHANDLED_PROMISE_REJECTION',
        origin_service: 'uis/backoffice',
      });
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleRejection);
    };
  }, []);

  return null;
}
