import React, { useState, useEffect } from 'react';
import { FileText, Database, AlertCircle, CheckCircle, ChevronDown, ChevronUp, BookOpen } from 'lucide-react';
import { policyService } from '../services/api';

const Policies = () => {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('');
  const [expandedPolicy, setExpandedPolicy] = useState(null);
  const [policyContent, setPolicyContent] = useState({});
  const [loadingContent, setLoadingContent] = useState({});

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await policyService.getAll();
      setPolicies(response.policies || []);
      setMode(response.mode || 'unknown');
    } catch (err) {
      console.error('Error fetching policies:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to fetch policies. Please check if the server is running.';
      setError(errorMsg);
      setPolicies([]); // Clear policies on error
    } finally {
      setLoading(false);
    }
  };

  const getTopicColor = (topic) => {
    const colors = {
      'AML': 'bg-blue-100 text-blue-800',
      'KYC': 'bg-green-100 text-green-800',
      'SANCTIONS': 'bg-red-100 text-red-800',
      'FRAUD': 'bg-purple-100 text-purple-800'
    };
    return colors[topic] || 'bg-gray-100 text-gray-800';
  };

  const getSourceColor = (source) => {
    const colors = {
      'INTERNAL': 'bg-indigo-100 text-indigo-800',
      'OFAC': 'bg-orange-100 text-orange-800',
      'FATF': 'bg-teal-100 text-teal-800',
      'REGULATORY': 'bg-pink-100 text-pink-800'
    };
    return colors[source] || 'bg-gray-100 text-gray-800';
  };

  const togglePolicy = async (policyId) => {
    if (expandedPolicy === policyId) {
      setExpandedPolicy(null);
      return;
    }
    
    setExpandedPolicy(policyId);
    
    // Fetch content if not already loaded
    if (!policyContent[policyId]) {
      setLoadingContent(prev => ({ ...prev, [policyId]: true }));
      try {
        const response = await fetch(`/api/policies/${policyId}/content`);
        const data = await response.json();
        setPolicyContent(prev => ({ ...prev, [policyId]: data.content }));
      } catch (err) {
        console.error('Error fetching policy content:', err);
        setPolicyContent(prev => ({ ...prev, [policyId]: 'Error loading policy content. Please try again.' }));
      } finally {
        setLoadingContent(prev => ({ ...prev, [policyId]: false }));
      }
    }
  };

  const getPolicyContent = (policy) => {
    return policyContent[policy.doc_id] || 'Loading...';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Policy Database</h1>
        {mode === 'demo' && (
          <span className="px-3 py-1 bg-yellow-100 text-yellow-800 text-sm font-medium rounded-full">
            Demo Mode
          </span>
        )}
      </div>
      
      <div className="card">
        <div className="flex items-center space-x-4 mb-6">
          <Database className="w-12 h-12 text-primary" />
          <div>
            <h2 className="text-xl font-semibold">Compliance Policies</h2>
            <p className="text-gray-600">
              {loading ? 'Loading policies...' : `${policies.length} policies available`}
            </p>
          </div>
        </div>
        
        {mode === 'demo' && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-blue-900">Demo Mode Active</p>
                <p className="mt-1 text-sm text-blue-800">
                  Showing demo policies. Connect to Milvus database to manage custom policies.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-900">Error Loading Policies</p>
                <p className="mt-1 text-sm text-red-800">{error}</p>
              </div>
            </div>
          </div>
        )}
        
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading policies...</p>
          </div>
        ) : policies.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Policies Yet</h3>
            <p className="text-gray-600 mb-6">
              Upload your first policy document to get started with compliance automation
            </p>
            <a href="/upload" className="btn btn-primary">
              Upload Policy
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            {policies.map((policy) => (
              <div key={policy.doc_id} className="border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-all">
                <div 
                  className="p-6 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => togglePolicy(policy.doc_id)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
                        <h3 className="text-lg font-semibold text-gray-900">{policy.title}</h3>
                        <button 
                          className="ml-auto p-1 hover:bg-gray-200 rounded transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            togglePolicy(policy.doc_id);
                          }}
                        >
                          {expandedPolicy === policy.doc_id ? (
                            <ChevronUp className="w-5 h-5 text-gray-600" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-600" />
                          )}
                        </button>
                      </div>
                      {policy.description && (
                        <p className="text-gray-600 text-sm mb-3">{policy.description}</p>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-2 mb-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getTopicColor(policy.topic)}`}>
                      {policy.topic}
                    </span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getSourceColor(policy.source)}`}>
                      {policy.source}
                    </span>
                    <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
                      v{policy.version}
                    </span>
                    {policy.chunks && (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                        {policy.chunks} chunks
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center justify-between text-sm text-gray-500">
                    <span>Document ID: {policy.doc_id}</span>
                    <span className="flex items-center space-x-1 text-primary">
                      <BookOpen className="w-4 h-4" />
                      <span>Click to {expandedPolicy === policy.doc_id ? 'collapse' : 'read'}</span>
                    </span>
                  </div>
                </div>
                
                {expandedPolicy === policy.doc_id && (
                  <div className="border-t border-gray-200 bg-gray-50 p-6">
                    <div className="flex items-center space-x-2 mb-4">
                      <FileText className="w-5 h-5 text-primary" />
                      <h4 className="font-semibold text-gray-900">Policy Document</h4>
                    </div>
                    <div className="bg-white rounded-lg p-6 border border-gray-200">
                      {loadingContent[policy.doc_id] ? (
                        <div className="text-center py-8">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                          <p className="mt-2 text-sm text-gray-600">Loading policy content...</p>
                        </div>
                      ) : (
                        <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
                          {getPolicyContent(policy)}
                        </pre>
                      )}
                    </div>
                    <div className="mt-4 flex justify-end">
                      <button
                        onClick={() => setExpandedPolicy(null)}
                        className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-200 rounded-lg transition-colors"
                      >
                        Close Document
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="font-semibold mb-2">Version Control</h3>
          <p className="text-sm text-gray-600">
            Track policy changes and maintain historical versions for audit trails
          </p>
        </div>
        
        <div className="card">
          <h3 className="font-semibold mb-2">Auto-Indexing</h3>
          <p className="text-sm text-gray-600">
            Policies are automatically chunked and indexed for semantic search
          </p>
        </div>
        
        <div className="card">
          <h3 className="font-semibold mb-2">Impact Analysis</h3>
          <p className="text-sm text-gray-600">
            See how policy updates affect past decisions and re-evaluate transactions
          </p>
        </div>
      </div>
    </div>
  );
};

export default Policies;
