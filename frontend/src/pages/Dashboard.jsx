import React, { useState, useEffect } from 'react';
import { TrendingUp, FileText, AlertCircle, CheckCircle } from 'lucide-react';
import { policyService, healthCheck } from '../services/api';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadData();
  }, []);
  
  const loadData = async () => {
    try {
      const [statsData, healthData] = await Promise.all([
        policyService.getStats(),
        healthCheck()
      ]);
      setStats(statsData);
      setHealth(healthData);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${health?.milvus_connected ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
          <span className="text-sm text-gray-600">
            {health?.milvus_connected ? 'Connected' : 'Demo Mode'}
          </span>
        </div>
      </div>
      
      {/* System Status */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">System Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center space-x-3">
            {health?.milvus_connected ? (
              <CheckCircle className="w-5 h-5 text-green-500" />
            ) : (
              <AlertCircle className="w-5 h-5 text-yellow-500" />
            )}
            <div>
              <p className="font-medium">Vector Database</p>
              <p className="text-sm text-gray-600">
                {health?.milvus_connected ? 'Connected' : 'Running in fallback mode'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <div>
              <p className="font-medium">API Service</p>
              <p className="text-sm text-gray-600">{health?.status || 'operational'}</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Documents</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {stats?.total_documents || 0}
              </p>
            </div>
            <FileText className="w-12 h-12 text-blue-500 opacity-20" />
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Policy Chunks</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {stats?.total_chunks || 0}
              </p>
            </div>
            <TrendingUp className="w-12 h-12 text-green-500 opacity-20" />
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Active Sources</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {stats?.sources ? Object.keys(stats.sources).length : 0}
              </p>
            </div>
            <AlertCircle className="w-12 h-12 text-purple-500 opacity-20" />
          </div>
        </div>
      </div>
      
      {/* Policy Sources */}
      {stats?.sources && (
        <div className="card">
          <h2 className="text-xl font-semibold mb-4">Policy Sources</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {Object.entries(stats.sources).map(([source, count]) => (
              <div key={source} className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-primary">{count}</p>
                <p className="text-sm text-gray-600 mt-1 capitalize">{source}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="/evaluate"
            className="flex items-center space-x-3 p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
          >
            <CheckCircle className="w-6 h-6 text-blue-600" />
            <div>
              <p className="font-medium text-gray-900">Evaluate Transaction</p>
              <p className="text-sm text-gray-600">Analyze a new transaction</p>
            </div>
          </a>
          
          <a
            href="/upload"
            className="flex items-center space-x-3 p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors"
          >
            <FileText className="w-6 h-6 text-purple-600" />
            <div>
              <p className="font-medium text-gray-900">Upload Policy</p>
              <p className="text-sm text-gray-600">Add new compliance policy</p>
            </div>
          </a>
        </div>
      </div>
      
      {/* Getting Started */}
      <div className="card bg-gradient-to-r from-blue-50 to-purple-50">
        <h2 className="text-xl font-semibold mb-4">Getting Started</h2>
        <div className="space-y-3">
          <div className="flex items-start space-x-3">
            <div className="w-6 h-6 bg-primary text-white rounded-full flex items-center justify-center text-sm font-bold">1</div>
            <div>
              <p className="font-medium">Upload Policies</p>
              <p className="text-sm text-gray-600">Start by uploading your compliance documents and regulatory policies</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-6 h-6 bg-primary text-white rounded-full flex items-center justify-center text-sm font-bold">2</div>
            <div>
              <p className="font-medium">Evaluate Transactions</p>
              <p className="text-sm text-gray-600">Submit transactions for automated compliance evaluation</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <div className="w-6 h-6 bg-primary text-white rounded-full flex items-center justify-center text-sm font-bold">3</div>
            <div>
              <p className="font-medium">Review Results</p>
              <p className="text-sm text-gray-600">Get AI-powered decisions with full explainability and policy citations</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
