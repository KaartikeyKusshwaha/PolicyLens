import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Clock, FileText, MessageSquare, BarChart3 } from 'lucide-react';
import { metricsService } from '../services/api';

const Metrics = () => {
  const [counters, setCounters] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [latency, setLatency] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 15000);
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    try {
      // Fetch metrics (includes counters)
      const data = await metricsService.get();
      
      // Fetch latency statistics from database
      const latencyData = await metricsService.getLatency();
      
      // Use counters from main metrics endpoint
      setCounters(data.counters);
      setMetrics(data);
      setLatency(latencyData);
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
                {counters?.total_evaluations || 0}
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
                {counters?.total_queries || 0}
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
                {counters?.total_policy_uploads || 0}
              </p>
            </div>
            <FileText className="w-12 h-12 text-green-500 opacity-30" />
          </div>
        </div>
      </div>

      {/* Evaluation Latency */}
      <div className="card">
        <div className="flex items-center space-x-2 mb-4">
          <Clock className="w-5 h-5 text-gray-500" />
          <h2 className="text-xl font-semibold">Evaluation Latency</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Average</p>
            <p className="text-2xl font-bold text-gray-800">
              {formatLatency(latency?.evaluation?.avg_ms)}
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Median (p50)</p>
            <p className="text-2xl font-bold text-gray-800">
              {formatLatency(latency?.evaluation?.p50_ms)}
            </p>
          </div>
          <div className="bg-yellow-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">p95</p>
            <p className="text-2xl font-bold text-yellow-700">
              {formatLatency(latency?.evaluation?.p95_ms)}
            </p>
          </div>
          <div className="bg-orange-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">p99</p>
            <p className="text-2xl font-bold text-orange-700">
              {formatLatency(latency?.evaluation?.p99_ms)}
            </p>
          </div>
          <div className="bg-red-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Max</p>
            <p className="text-2xl font-bold text-red-700">
              {formatLatency(latency?.evaluation?.max_ms)}
            </p>
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-2 text-center">
          Based on {latency?.evaluation?.count || 0} samples
        </p>
      </div>

      {/* Query Latency */}
      <div className="card">
        <div className="flex items-center space-x-2 mb-4">
          <Clock className="w-5 h-5 text-gray-500" />
          <h2 className="text-xl font-semibold">Query Latency</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Average</p>
            <p className="text-2xl font-bold text-gray-800">
              {formatLatency(latency?.query?.avg_ms)}
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Median (p50)</p>
            <p className="text-2xl font-bold text-gray-800">
              {formatLatency(latency?.query?.p50_ms)}
            </p>
          </div>
          <div className="bg-yellow-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">p95</p>
            <p className="text-2xl font-bold text-yellow-700">
              {formatLatency(latency?.query?.p95_ms)}
            </p>
          </div>
          <div className="bg-orange-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">p99</p>
            <p className="text-2xl font-bold text-orange-700">
              {formatLatency(latency?.query?.p99_ms)}
            </p>
          </div>
          <div className="bg-red-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Max</p>
            <p className="text-2xl font-bold text-red-700">
              {formatLatency(latency?.query?.max_ms)}
            </p>
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-2 text-center">
          Based on {latency?.query?.count || 0} samples
        </p>
      </div>

      {/* Hourly Activity */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Hourly Activity (Last 24 Hours)</h2>
        <div className="overflow-x-auto">
          <div className="flex gap-2 min-w-full">
            {metrics?.hourly_activity?.slice(-24).filter(item => item.hour).map((item, index) => {
              const hourDate = new Date(item.hour);
              if (isNaN(hourDate.getTime())) return null;
              
              const hour = hourDate.getHours();
              const count = item.count || 0;
              const maxCount = Math.max(...(metrics?.hourly_activity?.map(h => h.count || 0) || [1]), 1);
              const height = maxCount > 0 ? (count / maxCount) * 100 : 0;
              
              return (
                <div key={index} className="flex flex-col items-center flex-1 min-w-[40px]">
                  <div className="text-xs text-gray-600 mb-1">{count}</div>
                  <div className="w-full bg-gray-200 rounded-t relative" style={{ height: '100px', display: 'flex', alignItems: 'flex-end' }}>
                    <div 
                      className={`w-full rounded-t transition-all ${count > 0 ? 'bg-blue-500 hover:bg-blue-600' : 'bg-gray-300'}`}
                      style={{ height: `${Math.max(height, count > 0 ? 5 : 0)}%` }}
                      title={`${hour}:00 - ${count} evaluations`}
                    ></div>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{hour}h</p>
                </div>
              );
            }).filter(Boolean)}
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-4 text-center">
          Total activity (evaluations, queries, policy uploads) per hour
        </p>
      </div>
    </div>
  );
};

export default Metrics;
