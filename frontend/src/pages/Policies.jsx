import React from 'react';
import { FileText, Database, AlertCircle } from 'lucide-react';

const Policies = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Policy Management</h1>
      
      <div className="card">
        <div className="flex items-center space-x-4 mb-6">
          <Database className="w-12 h-12 text-primary" />
          <div>
            <h2 className="text-xl font-semibold">Policy Database</h2>
            <p className="text-gray-600">View and manage compliance policies</p>
          </div>
        </div>
        
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-900">Policy Management Features</p>
              <ul className="mt-2 text-sm text-blue-800 space-y-1">
                <li>• View all uploaded policies with version history</li>
                <li>• Track policy updates and changes</li>
                <li>• Monitor policy effectiveness and usage</li>
                <li>• Manage policy lifecycles and deprecation</li>
              </ul>
            </div>
          </div>
        </div>
        
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
