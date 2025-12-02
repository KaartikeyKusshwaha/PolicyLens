import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const policyService = {
  uploadPolicy: async (policyData) => {
    const response = await api.post('/api/policies/upload', policyData);
    return response.data;
  },
  
  getStats: async () => {
    const response = await api.get('/api/policies/stats');
    return response.data;
  },
};

export const transactionService = {
  evaluate: async (transaction) => {
    const response = await api.post('/api/transactions/evaluate', {
      transaction
    });
    return response.data;
  },
};

export const queryService = {
  ask: async (query, topic = null) => {
    const response = await api.post('/api/query', {
      query,
      topic,
      top_k: 5
    });
    return response.data;
  },
};

export const feedbackService = {
  submit: async (feedbackData) => {
    const response = await api.post('/api/feedback', feedbackData);
    return response.data;
  },
};

export const healthCheck = async () => {
  const response = await api.get('/');
  return response.data;
};

export default api;
