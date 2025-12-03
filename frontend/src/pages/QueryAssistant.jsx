import React, { useState } from 'react';
import { Search, MessageCircle } from 'lucide-react';
import { queryService } from '../services/api';
import Alert from '../components/Alert';

const QueryAssistant = () => {
  const [query, setQuery] = useState('');
  const [topic, setTopic] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const response = await queryService.ask(query, topic || null);
      setResult(response);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process query');
    } finally {
      setLoading(false);
    }
  };
  
  const sampleQueries = [
    'What are the transaction thresholds for AML reporting?',
    'Which countries are considered high-risk jurisdictions?',
    'What documentation is required for enhanced due diligence?',
    'How long should transaction records be retained?',
    'What are the indicators of suspicious activity?',
  ];
  
  const loadSampleQuery = (sampleQuery) => {
    setQuery(sampleQuery);
  };
  
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Compliance Query Assistant</h1>
      
      {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Query Input */}
        <div className="lg:col-span-1 space-y-6">
          <div className="card">
            <h2 className="text-xl font-semibold mb-4">Ask a Question</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Your Question
                </label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows="5"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                  placeholder="Ask anything about compliance policies..."
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Topic (Optional)
                </label>
                <select
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                >
                  <option value="">All Topics</option>
                  <option value="aml">AML</option>
                  <option value="kyc">KYC</option>
                  <option value="sanctions">Sanctions</option>
                  <option value="fraud">Fraud</option>
                </select>
              </div>
              
              <button
                type="submit"
                disabled={loading}
                className="w-full btn btn-primary flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Search</span>
                  </>
                )}
              </button>
            </form>
          </div>
          
          {/* Sample Queries */}
          <div className="card">
            <h3 className="font-semibold mb-3">Sample Questions</h3>
            <div className="space-y-2">
              {sampleQueries.map((sq, idx) => (
                <button
                  key={idx}
                  onClick={() => loadSampleQuery(sq)}
                  className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg text-sm transition-colors"
                >
                  <MessageCircle className="w-4 h-4 inline mr-2 text-primary" />
                  {sq}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* Results */}
        <div className="lg:col-span-2">
          {result ? (
            <div className="space-y-6">
              {/* Answer */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold">Answer</h2>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-600">Confidence:</span>
                    <span className="font-medium">
                      {(result.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div className="prose max-w-none">
                  <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {result.answer}
                  </p>
                </div>
              </div>
              
              {/* Citations */}
              {result.citations && result.citations.length > 0 && (
                <div className="card">
                  <h2 className="text-xl font-semibold mb-4">
                    Source Citations ({result.citations.length})
                  </h2>
                  <div className="space-y-4">
                    {result.citations.map((citation, idx) => (
                      <div key={idx} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <h3 className="font-medium text-gray-900">{citation.doc_title}</h3>
                            {citation.section && (
                              <p className="text-sm text-gray-600 mt-1">{citation.section}</p>
                            )}
                          </div>
                          <span className="text-xs bg-primary text-white px-2 py-1 rounded">
                            {(citation.relevance_score * 100).toFixed(0)}% match
                          </span>
                        </div>
                        <p className="text-sm text-gray-700 mb-2">{citation.text}</p>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>Document ID: {citation.doc_id}</span>
                          <span>Version: {citation.version}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="card h-full flex items-center justify-center">
              <div className="text-center text-gray-500">
                <Search className="w-16 h-16 mx-auto mb-4 opacity-20" />
                <p className="text-lg font-medium">Ask a question to get started</p>
                <p className="text-sm mt-2">
                  The AI will search through all policies and provide an answer with citations
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default QueryAssistant;
