import React, { useState, useEffect } from 'react';
import { MessageSquare, ThumbsUp, ThumbsDown, Clock, Search } from 'lucide-react';
import { feedbackService } from '../services/api';
import Alert from '../components/Alert';

const FeedbackViewer = () => {
  const [feedback, setFeedback] = useState([]);
  const [filteredFeedback, setFilteredFeedback] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    loadFeedback();
  }, []);

  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredFeedback(feedback);
    } else {
      const filtered = feedback.filter(f => 
        f.trace_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        f.comments?.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredFeedback(filtered);
    }
  }, [searchTerm, feedback]);

  const loadFeedback = async () => {
    try {
      setLoading(true);
      const data = await feedbackService.getAll();
      const feedbackArray = data.feedback || [];
      setFeedback(feedbackArray);
      setFilteredFeedback(feedbackArray);
    } catch (error) {
      console.error('Error loading feedback:', error);
      setAlert({ type: 'error', message: 'Failed to load feedback' });
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getAgreementStats = () => {
    const total = feedback.length;
    const agreed = feedback.filter(f => f.agreed).length;
    const disagreed = total - agreed;
    return { total, agreed, disagreed, agreementRate: total > 0 ? (agreed / total * 100).toFixed(1) : 0 };
  };

  const stats = getAgreementStats();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading feedback...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">User Feedback</h1>
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <MessageSquare className="w-4 h-4" />
          <span>{stats.total} total responses</span>
        </div>
      </div>

      {alert && (
        <Alert
          type={alert.type}
          message={alert.message}
          onClose={() => setAlert(null)}
        />
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card bg-gradient-to-br from-blue-50 to-blue-100">
          <p className="text-sm text-gray-600 mb-1">Total Feedback</p>
          <p className="text-3xl font-bold text-blue-700">{stats.total}</p>
        </div>
        <div className="card bg-gradient-to-br from-green-50 to-green-100">
          <p className="text-sm text-gray-600 mb-1">Agreed</p>
          <p className="text-3xl font-bold text-green-700">{stats.agreed}</p>
        </div>
        <div className="card bg-gradient-to-br from-red-50 to-red-100">
          <p className="text-sm text-gray-600 mb-1">Disagreed</p>
          <p className="text-3xl font-bold text-red-700">{stats.disagreed}</p>
        </div>
        <div className="card bg-gradient-to-br from-purple-50 to-purple-100">
          <p className="text-sm text-gray-600 mb-1">Agreement Rate</p>
          <p className="text-3xl font-bold text-purple-700">{stats.agreementRate}%</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search by trace ID or comments..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>
      </div>

      {/* Feedback List */}
      {filteredFeedback.length === 0 ? (
        <div className="card text-center py-12">
          <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {feedback.length === 0 ? 'No feedback submitted yet.' : 'No feedback matches your search.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredFeedback.map((item, index) => (
            <div key={index} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  {item.agreed ? (
                    <div className="flex items-center space-x-2 bg-green-100 text-green-700 px-3 py-1 rounded-full">
                      <ThumbsUp className="w-4 h-4" />
                      <span className="text-sm font-semibold">Agreed</span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-2 bg-red-100 text-red-700 px-3 py-1 rounded-full">
                      <ThumbsDown className="w-4 h-4" />
                      <span className="text-sm font-semibold">Disagreed</span>
                    </div>
                  )}
                  {item.correct_decision && (
                    <span className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm font-semibold">
                      Correct: {item.correct_decision}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <Clock className="w-4 h-4" />
                  <span>{formatDate(item.timestamp)}</span>
                </div>
              </div>

              <div className="mb-3">
                <p className="text-sm text-gray-600">
                  Trace ID: <code className="bg-gray-100 px-2 py-0.5 rounded">{item.trace_id}</code>
                </p>
              </div>

              {item.comments && (
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm font-medium text-gray-700 mb-1">Comments:</p>
                  <p className="text-sm text-gray-600">{item.comments}</p>
                </div>
              )}

              {!item.comments && (
                <p className="text-sm text-gray-400 italic">No comments provided</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FeedbackViewer;
