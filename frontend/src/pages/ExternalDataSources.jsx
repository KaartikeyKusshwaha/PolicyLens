import React, { useState, useEffect } from 'react';
import { Globe, Calendar, RefreshCw, Database, AlertCircle, CheckCircle, Clock, Download, FileText } from 'lucide-react';
import Alert from '../components/Alert';

const ExternalDataSources = () => {
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [fetchHistory, setFetchHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(null);
  const [alert, setAlert] = useState(null);
  const [selectedSource, setSelectedSource] = useState(null);
  const [sourceData, setSourceData] = useState(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 120000); // Refresh every 2 minutes
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
        setFetchHistory(Array.isArray(history) ? history : []);
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
        ? `/api/external-data/fetch?source=${source}&force_refresh=true`
        : '/api/external-data/fetch?force_refresh=true';
      
      const response = await fetch(endpoint, { method: 'POST' });
      const data = await response.json();

      if (response.ok) {
        setAlert({
          type: 'success',
          message: `Successfully fetched data from ${source || 'all sources'}!`
        });
        
        // Store fetched data for display
        if (source && data.data) {
          setSelectedSource(source);
          setSourceData(data.data);
        }
        
        // Immediately refresh history to show the new fetch
        setTimeout(() => loadData(), 500); // Small delay to ensure backend has recorded it
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
              <div className={`p-4 border-b ${
                source.color === 'red' ? 'bg-red-50 border-red-100' :
                source.color === 'orange' ? 'bg-orange-50 border-orange-100' :
                'bg-blue-50 border-blue-100'
              }`}>
                <div className="flex items-center gap-3">
                  <div className={
                    source.color === 'red' ? 'text-red-600' :
                    source.color === 'orange' ? 'text-orange-600' :
                    'text-blue-600'
                  }>
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
                  className={`w-full flex items-center justify-center gap-2 px-4 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
                    source.color === 'red' ? 'bg-red-600 hover:bg-red-700' :
                    source.color === 'orange' ? 'bg-orange-600 hover:bg-orange-700' :
                    'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  <Download className={`w-4 h-4 ${isLoading ? 'animate-bounce' : ''}`} />
                  {isLoading ? 'Fetching...' : 'Fetch Now'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Data Display Modal/Section */}
            {selectedSource && sourceData && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold">{selectedSource} Data Preview</h2>
              {sourceData.from_cache && (
                <span className="text-sm text-blue-600 mt-1">📦 Loaded from cache</span>
              )}
            </div>
            <button
              onClick={() => {
                setSelectedSource(null);
                setSourceData(null);
              }}
              className="text-gray-500 hover:text-gray-700"
            >
              ✕
            </button>
          </div>          <div className="max-h-96 overflow-y-auto">
            {selectedSource === 'OFAC' && sourceData.data && (
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Showing {Math.min(20, sourceData.count || 0)} of {sourceData.count || 0} SDN entries
                </p>
                <div className="space-y-2">
                  {sourceData.data.slice(0, 20).map((entry, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded border border-gray-200">
                      <div className="font-medium text-gray-900">{entry.name}</div>
                      <div className="text-sm text-gray-600 mt-1">
                        <span className="inline-block mr-3">Type: {entry.type}</span>
                        <span className="inline-block">Program: {entry.program}</span>
                      </div>
                      {entry.remarks && (
                        <div className="text-xs text-gray-500 mt-1">{entry.remarks}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedSource === 'FATF' && (
              <div>
                <div className="mb-6">
                  <h3 className="font-semibold text-red-600 mb-3">High-Risk Jurisdictions (Call for Action)</h3>
                  <div className="space-y-2">
                    {sourceData.high_risk?.data?.map((country, idx) => (
                      <div key={idx} className="p-3 bg-red-50 rounded border border-red-200">
                        <div className="font-medium text-gray-900">{country.country}</div>
                        <div className="text-sm text-gray-600">{country.description}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-orange-600 mb-3">Jurisdictions under Increased Monitoring</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {sourceData.monitored?.data?.map((country, idx) => (
                      <div key={idx} className="p-2 bg-orange-50 rounded border border-orange-200 text-sm">
                        {country.country}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {selectedSource === 'RBI' && sourceData.data && (
              <div>
                {sourceData.count === 0 ? (
                  <p className="text-gray-500 text-center py-8">No RBI circulars found</p>
                ) : (
                  <div className="space-y-2">
                    {sourceData.data.slice(0, 20).map((circular, idx) => (
                      <div key={idx} className="p-3 bg-blue-50 rounded border border-blue-200">
                        <div className="font-medium text-gray-900">{circular.title}</div>
                        <div className="text-sm text-gray-600 mt-1">
                          Date: {circular.date} | Ref: {circular.reference}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

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
