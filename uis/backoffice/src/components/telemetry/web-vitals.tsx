'use client';

import { useReportWebVitals } from 'next/web-vitals';
import { telemetryService } from '@/services/telemetry';

type MetricRating = 'good' | 'needs_improvement' | 'poor';

function normalizeRating(rating?: string): MetricRating {
  if (rating === 'good') return 'good';
  if (rating === 'poor') return 'poor';
  return 'needs_improvement';
}

export function WebVitals() {
  useReportWebVitals((metric) => {
    // Only capture standardized Core Web Vitals approved in the schema
    const approvedMetrics = ['LCP', 'FID', 'CLS', 'INP', 'TTFB'] as const;
    const metricName = metric.name as (typeof approvedMetrics)[number];

    if (!approvedMetrics.includes(metricName)) {
      return;
    }

    const pageRoute = typeof window !== 'undefined' ? window.location.pathname : '/';
    const rating = normalizeRating(metric.rating);
    const metricValue = Math.max(0, metric.value);

    telemetryService.track('client_web_vitals_recorded', {
      page_route: pageRoute,
      metric_name: metricName,
      metric_value: metricValue,
      rating,
    });
  });

  return null;
}

