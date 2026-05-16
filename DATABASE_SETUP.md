# Database Setup Guide

## Prerequisites

- PostgreSQL 12+ installed and running
- Python 3.9+
- SQLAlchemy and psycopg2 installed

## Step 1: Install Dependencies

```bash
pip install -r requirements-auth.txt
```

## Step 2: Create PostgreSQL Database

### Option A: Using psql command line

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE research_agent_db;
CREATE USER research_user WITH PASSWORD 'your_secure_password_here';

# Grant privileges
ALTER ROLE research_user SET client_encoding TO 'utf8';
ALTER ROLE research_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE research_user SET default_transaction_deferrable TO on;
ALTER ROLE research_user SET default_transaction_read_only TO off;
GRANT ALL PRIVILEGES ON DATABASE research_agent_db TO research_user;

# Connect to the new database and enable UUID extension
\c research_agent_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

# Exit psql
\q
```

### Option B: Using Python script

```bash
python -c "
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect('dbname=postgres user=postgres')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

# Create database
cursor.execute('CREATE DATABASE research_agent_db;')

# Create user
cursor.execute(\"CREATE USER research_user WITH PASSWORD 'your_password';\")

# Grant privileges
cursor.execute('GRANT ALL PRIVILEGES ON DATABASE research_agent_db TO research_user;')

cursor.close()
conn.close()
print('Database created successfully')
"
```

## Step 3: Configure Environment Variables

1. Copy `.env.example` to `.env`
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your configuration:
   ```bash
   DATABASE_URL=postgresql://research_user:your_secure_password@localhost:5432/research_agent_db
   JWT_SECRET=your_super_secret_jwt_key_minimum_32_characters_long_here
   ```

## Step 4: Create Database Tables

The tables will be created automatically when you start the application for the first time:

```bash
python main.py
```

Or, if you want to create them manually:

```bash
python -c "
from auth.database import init_db
init_db()
print('Database tables created successfully')
"
```

## Step 5: Verify Database Connection

```bash
python -c "
from auth.database import init_db
import logging

logging.basicConfig(level=logging.INFO)
if init_db():
    print('✓ Database connection successful')
    print('✓ All tables created')
else:
    print('✗ Database connection failed')
"
```

## Database Schema

### users table
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
);
```

### sessions table
```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    query VARCHAR(1000) NOT NULL,
    final_answer TEXT,
    quality_score FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'running',
    tokens_used INTEGER DEFAULT 0,
    cost_estimate FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
);
```

### chat_history table
```sql
CREATE TABLE chat_history (
    history_id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id UUID NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    embedding_vector JSON,
    relevance_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);
```

### api_tokens table
```sql
CREATE TABLE api_tokens (
    token_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_used TIMESTAMP,
    is_revoked BOOLEAN DEFAULT false,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at),
    INDEX idx_is_revoked (is_revoked)
);
```

## Troubleshooting

### Connection refused
```
Error: could not connect to server: Connection refused
```
**Solution**: Make sure PostgreSQL is running
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql

# Windows
# Start PostgreSQL service from Services app
```

### Authentication failed
```
Error: FATAL: Ident authentication failed for user "research_user"
```
**Solution**: Check PostgreSQL pg_hba.conf file and change authentication method from `ident` to `md5` or `scram-sha-256`

### Database already exists
```
Error: database "research_agent_db" already exists
```
**Solution**: Drop the existing database and recreate it
```bash
psql -U postgres -c "DROP DATABASE IF EXISTS research_agent_db;"
# Then repeat the creation steps
```

## Database Backup & Restore

### Backup database
```bash
pg_dump -U research_user -h localhost research_agent_db > backup.sql
```

### Restore database
```bash
psql -U research_user -h localhost research_agent_db < backup.sql
```

## Production Deployment

For production, ensure:
1. PostgreSQL is running on a secure server (not localhost)
2. Use strong passwords for database user
3. Enable SSL connections
4. Set up regular backups
5. Monitor database performance
6. Use connection pooling (handled by SQLAlchemy)

Example production connection string:
```bash
DATABASE_URL=postgresql://research_user:strong_password@prod-db.example.com:5432/research_agent_db?sslmode=require
```
