import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Clock, FileText, MessageSquare, BarChart3 } from 'lucide-react';
import { metricsService } from '../services/api';

const Metrics = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    try {
      // Fetch regular metrics
      const data = await metricsService.get();
      
      // Fetch persisted latency data from database
      const latencyData = await metricsService.getLatency();
      
      // Merge persisted latency data with real-time metrics
      const mergedMetrics = {
        ...data,
        latency: {
          evaluation: {
            ...latencyData.evaluation,
            sample_count: latencyData.evaluation.count
          },
          query: {
            ...latencyData.query,
            sample_count: latencyData.query.count
          }
        }
      };
      
      setMetrics(mergedMetrics);
    } catch (error) {
      console.error('Error loading metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading metrics...</p>
        </div>
      </div>
    );
  }

  const formatLatency = (ms) => {
    return ms ? `${ms.toFixed(0)}ms` : 'N/A';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">System Metrics</h1>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Activity className="w-4 h-4 animate-pulse text-green-500" />
          <span>Live Updates</span>
        </div>
      </div>

      {/* Operation Counters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card bg-gradient-to-br from-blue-50 to-blue-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total Evaluations</p>
              <p className="text-4xl font-bold text-blue-700">
                {metrics?.counters?.total_evaluations || 0}
              </p>
            </div>
            <BarChart3 className="w-12 h-12 text-blue-500 opacity-30" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-purple-50 to-purple-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total Queries</p>
              <p className="text-4xl font-bold text-purple-700">
                {metrics?.counters?.total_queries || 0}
              </p>
            </div>
            <MessageSquare className="w-12 h-12 text-purple-500 opacity-30" />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-green-50 to-green-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Policy Uploads</p>
              <p className="text-4xl font-bold text-green-700">
                {metrics?.counters?.total_policy_uploads || 0}
              </p>
            </div>
            <FileText className="w-12 h-12 text-green-500 opacity-30" />
          </div>
        </div>
      </div>

      {/* Evaluation Latency */}
      {metrics?.latency?.evaluation && (
        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <Clock className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold">Evaluation Latency</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Average</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatLatency(metrics.latency.evaluation.avg_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Median (p50)</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatLatency(metrics.latency.evaluation.p50_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">p95</p>
              <p className="text-2xl font-bold text-yellow-700">
                {formatLatency(metrics.latency.evaluation.p95_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">p99</p>
              <p className="text-2xl font-bold text-orange-700">
                {formatLatency(metrics.latency.evaluation.p99_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Max</p>
              <p className="text-2xl font-bold text-red-700">
                {formatLatency(metrics.latency.evaluation.max_ms)}
              </p>
            </div>
          </div>
          <div className="mt-4 text-sm text-gray-600 text-center">
            Based on {metrics.latency.evaluation.sample_count || 0} samples
          </div>
        </div>
      )}

      {/* Query Latency */}
      {metrics?.latency?.query && (
        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <Clock className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold">Query Latency</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Average</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatLatency(metrics.latency.query.avg_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Median (p50)</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatLatency(metrics.latency.query.p50_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">p95</p>
              <p className="text-2xl font-bold text-yellow-700">
                {formatLatency(metrics.latency.query.p95_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">p99</p>
              <p className="text-2xl font-bold text-orange-700">
                {formatLatency(metrics.latency.query.p99_ms)}
              </p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Max</p>
              <p className="text-2xl font-bold text-red-700">
                {formatLatency(metrics.latency.query.max_ms)}
              </p>
            </div>
          </div>
          <div className="mt-4 text-sm text-gray-600 text-center">
            Based on {metrics.latency.query.sample_count || 0} samples
          </div>
        </div>
      )}

      {/* Hourly Activity */}
      {metrics?.hourly_activity && Object.keys(metrics.hourly_activity).length > 0 && (
        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <TrendingUp className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold">Hourly Activity (Last 24h)</h2>
          </div>
          <div className="space-y-2">
            {Object.entries(metrics.hourly_activity)
              .sort((a, b) => b[0].localeCompare(a[0]))
              .slice(0, 12)
              .map(([hour, count]) => {
                const maxCount = Math.max(...Object.values(metrics.hourly_activity));
                const width = maxCount > 0 ? (count / maxCount) * 100 : 0;
                return (
                  <div key={hour} className="flex items-center space-x-4">
                    <div className="w-32 text-sm text-gray-600 font-mono">
                      {new Date(hour).toLocaleString('en-US', { 
                        month: 'short', 
                        day: 'numeric', 
                        hour: '2-digit',
                        hour12: false 
                      })}
                    </div>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                      <div 
                        className="bg-gradient-to-r from-primary to-blue-500 h-full flex items-center justify-end pr-2 transition-all duration-300"
                        style={{ width: `${width}%` }}
                      >
                        {count > 0 && (
                          <span className="text-xs font-semibold text-white">{count}</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* System Info */}
      <div className="card bg-gray-50">
        <h2 className="text-xl font-semibold mb-4">System Information</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-gray-600">Metrics Collection Started</p>
            <p className="font-mono text-gray-900">
              {metrics?.start_time ? new Date(metrics.start_time).toLocaleString() : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-gray-600">Last Updated</p>
            <p className="font-mono text-gray-900">
              {new Date().toLocaleString()}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Metrics;
