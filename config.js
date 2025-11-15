// API Configuration - Vercel Deployment
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:3000'  // Local development
    : '/api';  // Use /api prefix for Vercel deployment

console.log('Using API Base URL:', API_BASE_URL);
