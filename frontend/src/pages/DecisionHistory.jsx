import React, { useState, useEffect } from 'react';
import { Search, Download, Clock, AlertCircle, RefreshCw, Filter } from 'lucide-react';
import { decisionService, auditService } from '../services/api';
import RiskBadge from '../components/RiskBadge';
import Alert from '../components/Alert';

const DecisionHistory = () => {
  const [decisions, setDecisions] = useState([]);
  const [filteredDecisions, setFilteredDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('all');

  useEffect(() => {
    loadDecisions();
  }, []);

  useEffect(() => {
    filterDecisions();
  }, [searchTerm, verdictFilter, decisions]);

  const loadDecisions = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await decisionService.getAll();
      const decisionsArray = response.decisions || [];
      
      setDecisions(decisionsArray);
      setFilteredDecisions(decisionsArray);
    } catch (err) {
      console.error('Failed to load decisions:', err);
      setError('Failed to load decisions');
      setDecisions([]);
      setFilteredDecisions([]);
    } finally {
      setLoading(false);
    }
  };

  const filterDecisions = () => {
    let filtered = [...decisions];

    if (searchTerm.trim()) {
      const search = searchTerm.toLowerCase();
      filtered = filtered.filter(d => {
        const traceId = d.trace_id?.toLowerCase() || '';
        const transactionId = d.transaction?.transaction_id?.toLowerCase() || '';
        const verdict = d.decision?.verdict?.toLowerCase() || '';
        const sender = typeof d.transaction?.sender === 'string' 
          ? d.transaction.sender.toLowerCase() 
          : '';
        
        return traceId.includes(search) || 
               transactionId.includes(search) || 
               verdict.includes(search) || 
               sender.includes(search);
      });
    }

    if (verdictFilter !== 'all') {
      filtered = filtered.filter(d => 
        d.decision?.verdict?.toLowerCase() === verdictFilter.toLowerCase()
      );
    }

    setFilteredDecisions(filtered);
  };

  const handleDownloadAudit = async (traceId) => {
    try {
      const report = await auditService.getReport(traceId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit-${traceId}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download audit:', err);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const getVerdictColor = (verdict) => {
    const v = verdict?.toLowerCase();
    if (v === 'approve') return 'bg-green-100 text-green-800';
    if (v === 'flag') return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600">Loading decisions...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Decision History</h1>
          <p className="text-gray-600 mt-1">
            {decisions.length} total decision{decisions.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={loadDecisions}
          className="btn btn-secondary flex items-center space-x-2"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert type="error" message={error} onClose={() => setError(null)} />
      )}

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search by trace ID, transaction ID, sender, or verdict..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
          </div>

          {/* Verdict Filter */}
          <div className="flex items-center space-x-2">
            <Filter className="w-5 h-5 text-gray-600" />
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value="all">All Verdicts</option>
              <option value="approve">Approve</option>
              <option value="flag">Flag</option>
              <option value="needs_review">Needs Review</option>
            </select>
          </div>
        </div>
      </div>

      {/* Decisions List */}
      {filteredDecisions.length === 0 ? (
        <div className="card text-center py-12">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 text-lg">
            {decisions.length === 0 
              ? 'No decisions found. Start by evaluating a transaction.' 
              : 'No decisions match your filters.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredDecisions.map((decision) => {
            const transaction = decision.transaction || {};
            const decisionData = decision.decision || {};
            const sender = typeof transaction.sender === 'string' 
              ? transaction.sender 
              : (transaction.sender?.name || 'Unknown');
            const receiver = typeof transaction.receiver === 'string'
              ? transaction.receiver
              : (transaction.receiver?.name || 'Unknown');

            return (
              <div key={decision.trace_id} className="card hover:shadow-lg transition-shadow">
                {/* Header Row */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="font-semibold text-lg">
                        {transaction.transaction_id || decision.trace_id?.substring(0, 8)}
                      </h3>
                      <RiskBadge level={decisionData.risk_level} />
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase ${getVerdictColor(decisionData.verdict)}`}>
                        {decisionData.verdict || 'Unknown'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-600">
                      <Clock className="w-4 h-4" />
                      <span>{formatTimestamp(decision.stored_at || decision.timestamp)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDownloadAudit(decision.trace_id)}
                    className="btn btn-secondary flex items-center space-x-2"
                  >
                    <Download className="w-4 h-4" />
                    <span>Audit Report</span>
                  </button>
                </div>

                {/* Transaction Details Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Amount</p>
                    <p className="font-semibold text-gray-900">
                      ${(transaction.amount || 0).toLocaleString()}
                      {transaction.currency && transaction.currency !== 'USD' && (
                        <span className="text-xs text-gray-500 ml-1">{transaction.currency}</span>
                      )}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Sender</p>
                    <p className="font-semibold text-gray-900 truncate" title={sender}>
                      {sender}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {transaction.sender_country || transaction.sender?.country || ''}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Receiver</p>
                    <p className="font-semibold text-gray-900 truncate" title={receiver}>
                      {receiver}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {transaction.receiver_country || transaction.receiver?.country || ''}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Risk Score</p>
                    <p className="font-semibold text-gray-900">
                      {decisionData.risk_score ? (decisionData.risk_score * 100).toFixed(1) + '%' : 'N/A'}
                    </p>
                  </div>
                </div>

                {/* Reasoning */}
                {decisionData.reasoning && (
                  <div className="mt-4">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Reasoning</p>
                    <p className="text-sm text-gray-700 bg-white p-3 rounded border border-gray-200">
                      {decisionData.reasoning}
                    </p>
                  </div>
                )}

                {/* Policy Citations */}
                {decisionData.policy_citations && decisionData.policy_citations.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">
                      Policy Citations ({decisionData.policy_citations.length})
                    </p>
                    <div className="space-y-2">
                      {decisionData.policy_citations.slice(0, 3).map((citation, idx) => (
                        <div key={idx} className="bg-white p-3 rounded border border-gray-200 text-sm">
                          <p className="font-semibold text-gray-900">
                            {citation.doc_title}
                            {citation.version && (
                              <span className="text-xs text-gray-500 ml-2">v{citation.version}</span>
                            )}
                          </p>
                          {citation.section && (
                            <p className="text-xs text-gray-600 mt-1">{citation.section}</p>
                          )}
                          {citation.relevance_score && (
                            <p className="text-xs text-gray-500 mt-1">
                              Relevance: {(citation.relevance_score * 100).toFixed(1)}%
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Trace ID */}
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs text-gray-500">
                    Trace ID: <code className="bg-gray-100 px-2 py-1 rounded text-xs">{decision.trace_id}</code>
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DecisionHistory;
