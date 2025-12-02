import React, { useState } from 'react';
import { Upload as UploadIcon } from 'lucide-react';
import { policyService } from '../services/api';
import Alert from '../components/Alert';

const UploadPolicy = () => {
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    source: 'internal',
    topic: 'aml',
    version: '1.0',
  });
  
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      const result = await policyService.uploadPolicy({
        ...formData,
        metadata: {}
      });
      
      setSuccess(`Policy "${result.title}" uploaded successfully! Created ${result.chunks_created} chunks.`);
      
      // Reset form
      setFormData({
        title: '',
        content: '',
        source: 'internal',
        topic: 'aml',
        version: '1.0',
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload policy');
    } finally {
      setLoading(false);
    }
  };
  
  const loadSamplePolicy = () => {
    setFormData({
      title: 'AML Transaction Monitoring Guidelines',
      content: `# AML Transaction Monitoring Guidelines

## Section 1: Transaction Thresholds

### 1.1 Large Transaction Reporting
All transactions exceeding USD 10,000 must be reported to the compliance team within 24 hours. Transactions above USD 50,000 require enhanced due diligence and senior management approval.

### 1.2 Structuring Detection
Multiple transactions from the same entity totaling more than USD 10,000 within a 7-day period should be aggregated and reviewed for potential structuring activity.

## Section 2: High-Risk Jurisdictions

### 2.1 Sanctioned Countries
Transactions involving the following jurisdictions are prohibited without explicit regulatory approval:
- North Korea
- Iran
- Syria
- Crimea region

### 2.2 High-Risk Countries
Enhanced due diligence is required for transactions involving:
- Countries identified by FATF as having strategic AML deficiencies
- Jurisdictions with inadequate beneficial ownership transparency

## Section 3: Suspicious Activity Indicators

### 3.1 Red Flags
The following patterns should trigger immediate review:
- Unusual transaction patterns inconsistent with customer profile
- Transactions with no apparent economic purpose
- Use of multiple accounts to move funds
- Frequent just-below-threshold transactions
- Involvement of shell companies or nominee directors

### 3.2 Customer Due Diligence
Enhanced CDD is required when:
- Customer is a Politically Exposed Person (PEP)
- Beneficial ownership structure is complex or opaque
- Source of funds cannot be adequately verified
- Customer's business activities are high-risk (e.g., MSBs, casinos, dealers in precious metals)

## Section 4: Reporting Requirements

### 4.1 Suspicious Activity Reports (SARs)
File SARs within 30 days of detecting suspicious activity. Do not inform the customer that a SAR has been filed.

### 4.2 Currency Transaction Reports (CTRs)
Report all cash transactions exceeding USD 10,000 within 15 days.

## Section 5: Record Keeping

Maintain records of all transactions and supporting documentation for a minimum of 5 years from the date of the transaction.`,
      source: 'internal',
      topic: 'aml',
      version: '1.0',
    });
  };
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Upload Policy Document</h1>
        <button
          onClick={loadSamplePolicy}
          className="btn btn-secondary"
        >
          Load Sample Policy
        </button>
      </div>
      
      {success && <Alert type="success" message={success} onClose={() => setSuccess(null)} />}
      {error && <Alert type="error" message={error} onClose={() => setError(null)} />}
      
      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Policy Title
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="e.g., AML Transaction Monitoring Policy"
              required
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Source
              </label>
              <select
                name="source"
                value={formData.source}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              >
                <option value="internal">Internal</option>
                <option value="ofac">OFAC</option>
                <option value="fatf">FATF</option>
                <option value="rbi">RBI</option>
                <option value="eu_aml">EU AML</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Topic
              </label>
              <select
                name="topic"
                value={formData.topic}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
              >
                <option value="aml">AML</option>
                <option value="kyc">KYC</option>
                <option value="sanctions">Sanctions</option>
                <option value="fraud">Fraud</option>
                <option value="general">General</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Version
              </label>
              <input
                type="text"
                name="version"
                value={formData.version}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
                placeholder="1.0"
                required
              />
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Policy Content
            </label>
            <textarea
              name="content"
              value={formData.content}
              onChange={handleChange}
              rows="20"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent font-mono text-sm"
              placeholder="Paste your policy document content here..."
              required
            />
            <p className="mt-1 text-sm text-gray-500">
              {formData.content.length} characters | ~{Math.ceil(formData.content.split(/\s+/).length / 600)} chunks will be created
            </p>
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full btn btn-primary flex items-center justify-center space-x-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Processing...</span>
              </>
            ) : (
              <>
                <UploadIcon className="w-4 h-4" />
                <span>Upload and Process Policy</span>
              </>
            )}
          </button>
        </form>
      </div>
      
      <div className="card bg-blue-50">
        <h3 className="font-semibold text-gray-900 mb-2">Tips for Policy Upload</h3>
        <ul className="space-y-2 text-sm text-gray-700">
          <li>• Use clear section headings to improve chunking quality</li>
          <li>• Include version numbers to track policy updates</li>
          <li>• Ensure content is well-formatted for better semantic understanding</li>
          <li>• Policies are automatically chunked into ~600 word segments with overlap</li>
          <li>• Each chunk is embedded and stored in the vector database for retrieval</li>
        </ul>
      </div>
    </div>
  );
};

export default UploadPolicy;
