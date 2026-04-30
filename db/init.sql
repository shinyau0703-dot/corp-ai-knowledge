-- 完整重建（移除密碼與角色，改為純使用者識別）
DROP TABLE IF EXISTS query_logs;
DROP TABLE IF EXISTS login_logs;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE login_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ip_address  VARCHAR(45),
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    source_path TEXT UNIQUE NOT NULL,
    product     VARCHAR(100) DEFAULT '',
    version     VARCHAR(50)  DEFAULT '',
    doc_type    VARCHAR(100) DEFAULT '',
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE query_logs (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    query            TEXT NOT NULL,
    response         TEXT,
    sources_used     JSONB,
    model            VARCHAR(100) NOT NULL,
    mode             VARCHAR(20)  NOT NULL DEFAULT 'medium',
    top_k            INTEGER      NOT NULL DEFAULT 5,
    scenario         VARCHAR(50)  NOT NULL DEFAULT 'general',
    doc_type         VARCHAR(100) NOT NULL DEFAULT '',
    product          VARCHAR(100) NOT NULL DEFAULT '',
    version          VARCHAR(50)  NOT NULL DEFAULT '',
    execution_time_ms INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
