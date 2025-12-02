import React, { useState, useEffect } from 'react';
import { Search, Download, Clock, AlertCircle } from 'lucide-react';
import { decisionService, auditService } from '../services/api';
import RiskBadge from '../components/RiskBadge';
import Alert from '../components/Alert';

const DecisionHistory = () => {
  const [decisions, setDecisions] = useState([]);
  const [filteredDecisions, setFilteredDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    loadDecisions();
  }, []);

  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredDecisions(decisions);
    } else {
      const filtered = decisions.filter(d => 
        d.trace_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        d.decision.verdict.toLowerCase().includes(searchTerm.toLowerCase()) ||
        d.transaction.transaction_id?.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredDecisions(filtered);
    }
  }, [searchTerm, decisions]);

  const loadDecisions = async () => {
    try {
      setLoading(true);
      const data = await decisionService.getAll();
      setDecisions(data.decisions || []);
      setFilteredDecisions(data.decisions || []);
    } catch (error) {
      console.error('Error loading decisions:', error);
      setAlert({ type: 'error', message: 'Failed to load decision history' });
    } finally {
      setLoading(false);
    }
  };

  const downloadAuditReport = async (traceId) => {
    try {
      const report = await auditService.getReport(traceId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-report-${traceId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setAlert({ type: 'success', message: 'Audit report downloaded successfully' });
    } catch (error) {
      console.error('Error downloading audit report:', error);
      setAlert({ type: 'error', message: 'Failed to download audit report' });
    }
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading decision history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Decision History</h1>
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <Clock className="w-4 h-4" />
          <span>{decisions.length} total decisions</span>
        </div>
      </div>

      {alert && (
        <Alert
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      {/* Search Bar */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search by trace ID, transaction ID, or verdict..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>
      </div>

      {/* Decisions List */}
      {filteredDecisions.length === 0 ? (
        <div className="card text-center py-12">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {decisions.length === 0 ? 'No decisions found. Start by evaluating a transaction.' : 'No decisions match your search.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredDecisions.map((decision) => (
            <div key={decision.trace_id} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className="font-semibold text-lg">
                      {decision.transaction.transaction_id || decision.trace_id.substring(0, 8)}
                    </h3>
                    <RiskBadge level={decision.decision.risk_level} />
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      decision.decision.verdict === 'approve' ? 'bg-green-100 text-green-800' :
                      decision.decision.verdict === 'flag' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {decision.decision.verdict.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    Trace ID: <code className="bg-gray-100 px-2 py-0.5 rounded">{decision.trace_id}</code>
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    {formatDate(decision.timestamp)}
                  </p>
                </div>
                <button
                  onClick={() => downloadAuditReport(decision.trace_id)}
                  className="btn btn-secondary flex items-center space-x-2"
                  title="Download Audit Report"
                >
                  <Download className="w-4 h-4" />
                  <span>Audit Report</span>
                </button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">Amount</p>
                  <p className="font-semibold">${decision.transaction.amount?.toLocaleString() || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Type</p>
                  <p className="font-semibold capitalize">{decision.transaction.transaction_type || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Risk Score</p>
                  <p className="font-semibold">{(decision.decision.risk_score * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Confidence</p>
                  <p className="font-semibold">{(decision.decision.confidence * 100).toFixed(0)}%</p>
                </div>
              </div>

              <div className="mb-3">
                <p className="text-sm font-medium text-gray-700 mb-1">Reasoning:</p>
                <p className="text-sm text-gray-600 bg-blue-50 p-3 rounded">
                  {decision.decision.reasoning}
                </p>
              </div>

              {decision.decision.policy_citations && decision.decision.policy_citations.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Policy Citations ({decision.decision.policy_citations.length}):
                  </p>
                  <div className="space-y-2">
                    {decision.decision.policy_citations.slice(0, 3).map((citation, idx) => (
                      <div key={idx} className="text-xs bg-gray-50 p-2 rounded">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-gray-700">{citation.policy_name}</span>
                          <span className="text-gray-500">Score: {citation.relevance_score?.toFixed(3)}</span>
                        </div>
                        <p className="text-gray-600">{citation.content.substring(0, 150)}...</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DecisionHistory;
