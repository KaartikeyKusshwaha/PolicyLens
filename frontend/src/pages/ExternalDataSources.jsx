import React, { useState, useEffect } from 'react';
import { Globe, Calendar, RefreshCw, Database, AlertCircle, CheckCircle, Clock, Download, FileText } from 'lucide-react';
import Alert from '../components/Alert';

const ExternalDataSources = () => {
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [fetchHistory, setFetchHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(null);
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statusRes, historyRes] = await Promise.all([
        fetch('/api/external-data/scheduler/status'),
        fetch('/api/external-data/history')
      ]);

      if (statusRes.ok) {
        const status = await statusRes.json();
        setSchedulerStatus(status);
      }

      if (historyRes.ok) {
        const history = await historyRes.json();
        setFetchHistory(history.fetch_history || []);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFetch = async (source = null) => {
    setFetching(source || 'all');
    setAlert(null);

    try {
      const endpoint = source 
        ? `/api/external-data/fetch?source=${source}`
        : '/api/external-data/fetch';
      
      const response = await fetch(endpoint, { method: 'POST' });
      const data = await response.json();

      if (response.ok) {
        setAlert({
          type: 'success',
          message: `Successfully fetched data from ${source || 'all sources'}!`
        });
        loadData(); // Refresh data
      } else {
        setAlert({
          type: 'error',
          message: `Failed to fetch data: ${data.detail || 'Unknown error'}`
        });
      }
    } catch (error) {
      setAlert({
        type: 'error',
        message: `Error: ${error.message}`
      });
    } finally {
      setFetching(null);
    }
  };

  const handleSync = async () => {
    setFetching('sync');
    setAlert(null);

    try {
      const response = await fetch('/api/external-data/sync', { method: 'POST' });
      const data = await response.json();

      if (response.ok) {
        setAlert({
          type: 'success',
          message: 'Full sync completed! Policies updated with latest data.'
        });
        loadData();
      } else {
        setAlert({
          type: 'error',
          message: `Sync failed: ${data.detail || 'Unknown error'}`
        });
      }
    } catch (error) {
      setAlert({
        type: 'error',
        message: `Error: ${error.message}`
      });
    } finally {
      setFetching(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'Not yet run';
    return new Date(isoString).toLocaleString();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success': return 'text-green-600 bg-green-50';
      case 'failed': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading external data sources...</p>
        </div>
      </div>
    );
  }

  const sources = [
    {
      id: 'OFAC',
      name: 'OFAC Sanctions',
      icon: <AlertCircle className="w-6 h-6" />,
      description: 'US Treasury Specially Designated Nationals (SDN) list',
      color: 'red',
      schedule: 'Daily at 2 AM'
    },
    {
      id: 'FATF',
      name: 'FATF Jurisdictions',
      icon: <Globe className="w-6 h-6" />,
      description: 'High-risk and monitored countries',
      color: 'orange',
      schedule: 'Weekly on Monday 3 AM'
    },
    {
      id: 'RBI',
      name: 'RBI Circulars',
      icon: <FileText className="w-6 h-6" />,
      description: 'Reserve Bank of India AML/KYC regulations',
      color: 'blue',
      schedule: 'Daily at 4 AM'
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">External Data Sources</h1>
          <p className="mt-2 text-gray-600">
            Automated compliance data from OFAC, FATF, and RBI
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={fetching !== null}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-5 h-5 ${fetching === 'sync' ? 'animate-spin' : ''}`} />
          Full Sync
        </button>
      </div>

      {alert && (
        <Alert
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      {/* Scheduler Status */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Clock className="w-6 h-6 text-blue-600" />
          <h2 className="text-xl font-semibold">Scheduler Status</h2>
          {schedulerStatus?.running && (
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              Running
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {schedulerStatus?.jobs?.map((job) => (
            <div key={job.id} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <p className="font-medium text-gray-900 mb-1">{job.name}</p>
              <p className="text-sm text-gray-600">
                Next: {formatDate(job.next_run)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Data Sources Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {sources.map((source) => {
          const lastFetch = schedulerStatus?.last_fetch_times?.[source.id];
          const isLoading = fetching === source.id;

          return (
            <div key={source.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className={`p-4 bg-${source.color}-50 border-b border-${source.color}-100`}>
                <div className="flex items-center gap-3">
                  <div className={`text-${source.color}-600`}>
                    {source.icon}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{source.name}</h3>
                    <p className="text-sm text-gray-600">{source.schedule}</p>
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-4">
                <p className="text-sm text-gray-600">{source.description}</p>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Last Fetch:</span>
                    <span className="font-medium text-gray-900">
                      {lastFetch ? formatDate(lastFetch) : 'Not yet run'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleFetch(source.id)}
                  disabled={isLoading || fetching !== null}
                  className={`w-full flex items-center justify-center gap-2 px-4 py-2 bg-${source.color}-600 text-white rounded-lg hover:bg-${source.color}-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
                >
                  <Download className={`w-4 h-4 ${isLoading ? 'animate-bounce' : ''}`} />
                  {isLoading ? 'Fetching...' : 'Fetch Now'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Fetch History */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Database className="w-6 h-6 text-gray-600" />
          <h2 className="text-xl font-semibold">Recent Fetch History</h2>
        </div>

        {fetchHistory.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No fetch history available</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Records</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {fetchHistory.slice(-10).reverse().map((record, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {new Date(record.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="font-medium text-gray-900">{record.source}</span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(record.status)}`}>
                        {record.status === 'success' ? (
                          <CheckCircle className="w-3 h-3" />
                        ) : (
                          <AlertCircle className="w-3 h-3" />
                        )}
                        {record.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {record.records_fetched || 0}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {record.duration_seconds?.toFixed(2) || '0.00'}s
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ExternalDataSources;
