require('dotenv').config();
const { Pool } = require('pg');

// Create a connection pool to PostgreSQL
const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT, 10),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  max: 20,                  // Maximum number of active clients in the pool
  idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
  connectionTimeoutMillis: 2000, // Return an error after 2 seconds if connection fails
});

// Helper function to run queries with error logging
const query = async (text, params) => {
  const start = Date.now();
  try {
    const res = await pool.query(text, params);
    const duration = Date.now() - start;
    // Log slow queries (> 100ms) for performance diagnostics
    if (duration > 100) {
      console.warn(`[SLOW QUERY] ${duration}ms: ${text.slice(0, 80)}...`);
    }
    return res;
  } catch (err) {
    console.error(`[DB ERROR] Failed query: ${text.slice(0, 80)}...`, err.message);
    throw err;
  }
};

module.exports = {
  pool,
  query,
};