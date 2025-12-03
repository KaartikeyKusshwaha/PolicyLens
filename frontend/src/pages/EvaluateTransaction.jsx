import React, { useState } from 'react';
import { Send } from 'lucide-react';
import { transactionService } from '../services/api';
import Alert from '../components/Alert';
import RiskBadge from '../components/RiskBadge';

const EvaluateTransaction = () => {
  const [formData, setFormData] = useState({
    transaction_id: '',
    amount: '',
    currency: 'USD',
    sender: '',
    receiver: '',
    sender_country: '',
    receiver_country: '',
    description: '',
  });
  
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const transaction = {
        ...formData,
        amount: parseFloat(formData.amount),
        timestamp: new Date().toISOString(),
        metadata: {}
      };
      
      const response = await transactionService.evaluate(transaction);
      setResult(response);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to evaluate transaction');
    } finally {
      setLoading(false);
    }
  };
  
  const generateRandomTransaction = () => {
    const randomId = 'TXN' + Math.random().toString(36).substr(2, 9).toUpperCase();
    const amounts = [5000, 15000, 50000, 100000, 250000];
    const countries = ['USA', 'UK', 'Germany', 'Singapore', 'Japan', 'Iran', 'North Korea'];
    const names = ['John Smith', 'Acme Corp', 'Global Trading Ltd', 'Tech Solutions Inc'];
    
    setFormData({
      transaction_id: randomId,
      amount: amounts[Math.floor(Math.random() * amounts.length)],
      currency: 'USD',
      sender: names[Math.floor(Math.random() * names.length)],
      receiver: names[Math.floor(Math.random() * names.length)],
      sender_country: countries[Math.floor(Math.random() * countries.length)],
      receiver_country: countries[Math.floor(Math.random() * countries.length)],
      description: 'International wire transfer',
    });
  };
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Evaluate Transaction</h1>
        <button
          onClick={generateRandomTransaction}
          className="btn btn-secondary"
        >
          Generate Random
        </button>
      </div>
      
      {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4">Transaction Details</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Transaction ID
              </label>
              <input
                type="text"
                name="transaction_id"
                value={formData.transaction_id}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                required
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                  Amount
                </label>
                <input
                  type="number"
                  name="amount"
                  value={formData.amount}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                  Currency
                </label>
                <select
                  name="currency"
                  value={formData.currency}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                >
                  <option>USD</option>
                  <option>EUR</option>
                  <option>GBP</option>
                  <option>JPY</option>
                </select>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Sender
              </label>
              <input
                type="text"
                name="sender"
                value={formData.sender}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Sender Country
              </label>
              <input
                type="text"
                name="sender_country"
                value={formData.sender_country}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Receiver
              </label>
              <input
                type="text"
                name="receiver"
                value={formData.receiver}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Receiver Country
              </label>
              <input
                type="text"
                name="receiver_country"
                value={formData.receiver_country}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                Description
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows="3"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="w-full btn btn-primary flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Evaluate Transaction</span>
                </>
              )}
            </button>
          </form>
        </div>
        
        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Decision Summary */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4">Decision</h2>
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Verdict</p>
                  <span className={`badge ${
                    result.decision.verdict === 'flag' ? 'badge-high' :
                    result.decision.verdict === 'needs_review' ? 'badge-medium' :
                    'badge-acceptable'
                  }`}>
                    {result.decision.verdict.replace('_', ' ').toUpperCase()}
                  </span>
                </div>
                
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Risk Assessment</p>
                  <RiskBadge 
                    level={result.decision.risk_level} 
                    score={result.decision.risk_score}
                  />
                </div>
                
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Confidence</p>
                  <div className="flex items-center space-x-2">
                    <div className="flex-1 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                      <div
                        className="bg-primary h-2 rounded-full"
                        style={{ width: `${result.decision.confidence * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-medium">
                      {(result.decision.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Processing Time</p>
                  <p className="text-sm font-medium">
                    {result.processing_time_ms.toFixed(0)}ms
                  </p>
                </div>
              </div>
            </div>
            
            {/* Reasoning */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4">Reasoning</h2>
              <p className="text-gray-700 dark:text-gray-200 whitespace-pre-wrap">
                {result.decision.reasoning}
              </p>
            </div>
            
            {/* Policy Citations */}
            {result.decision.policy_citations && result.decision.policy_citations.length > 0 && (
              <div className="card">
                <h2 className="text-xl font-semibold mb-4">
                  Policy Citations ({result.decision.policy_citations.length})
                </h2>
                <div className="space-y-3">
                  {result.decision.policy_citations.map((citation, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-medium text-sm dark:text-white">{citation.doc_title}</p>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          Relevance: {(citation.relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      {citation.section && (
                        <p className="text-xs text-gray-600 dark:text-gray-300 mb-1">{citation.section}</p>
                      )}
                      <p className="text-sm text-gray-700 dark:text-gray-200">{citation.text}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Source: {citation.doc_id} | Version: {citation.version}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Similar Cases */}
            {result.decision.similar_cases && result.decision.similar_cases.length > 0 && (
              <div className="card">
                <h2 className="text-xl font-semibold mb-4">
                  Similar Cases ({result.decision.similar_cases.length})
                </h2>
                <div className="space-y-3">
                  {result.decision.similar_cases.map((case_item, idx) => (
                    <div key={idx} className="p-3 bg-blue-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-medium text-sm">{case_item.transaction_id}</p>
                        <span className="text-xs text-gray-500">
                          Similarity: {(case_item.similarity_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 mb-1">{case_item.reasoning}</p>
                      <div className="flex items-center justify-between">
                        <span className={`badge ${
                          case_item.decision === 'flag' ? 'badge-high' :
                          case_item.decision === 'needs_review' ? 'badge-medium' :
                          'badge-acceptable'
                        }`}>
                          {case_item.decision.replace('_', ' ').toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(case_item.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EvaluateTransaction;
