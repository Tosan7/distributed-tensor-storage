require('dotenv').config();

console.log('Debug credentials:', {
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});

const { query } = require('./src/db');

async function test() {
  try {
    const res = await query('SELECT NOW() AS current_time, COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = $1', ['public']);
    console.log('Connected to PostgreSQL successfully!');
    console.log('Database time:', res.rows[0].current_time);
    console.log('Tables found in public schema:', res.rows[0].table_count);
  } catch (err) {
    console.error('Connection failed:', err.message);
  }
  process.exit(0);
}

test();