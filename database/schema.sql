-- Enable UUID generation extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    coins INTEGER DEFAULT 0,
    remind_daily BOOLEAN DEFAULT TRUE,
    remind_streak BOOLEAN DEFAULT TRUE,
    remind_contests BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'USER',
    is_banned BOOLEAN DEFAULT FALSE
);

-- Linked Accounts Table
CREATE TABLE IF NOT EXISTS linked_accounts (
    telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    leetcode_username VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(50),
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Problem History Table
CREATE TABLE IF NOT EXISTS problem_history (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    solved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, problem_slug)
);

-- SRS Reviews Table
CREATE TABLE IF NOT EXISTS srs_reviews (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    ease_factor DOUBLE PRECISION DEFAULT 2.5,
    interval INTEGER DEFAULT 1, -- in days
    repetitions INTEGER DEFAULT 0,
    next_review_date TIMESTAMP WITH TIME ZONE NOT NULL,
    last_quality INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, problem_slug)
);

-- Battles Table
CREATE TABLE IF NOT EXISTS battles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challenger_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    opponent_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, ACTIVE, COMPLETED, EXPIRED, PAUSED, CANCELLED, DECLINED
    winner_id BIGINT REFERENCES users(telegram_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    remaining_seconds INT,
    chat_id BIGINT,
    message_id BIGINT
);

-- Group Members Table
CREATE TABLE IF NOT EXISTS group_members (
    group_id BIGINT,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, telegram_id)
);

-- Daily Challenges Table
CREATE TABLE IF NOT EXISTS daily_challenges (
    date DATE PRIMARY KEY,
    problem_slug VARCHAR(255) NOT NULL
);

-- Group Settings Table
CREATE TABLE IF NOT EXISTS group_settings (
    group_id BIGINT,
    setting_name VARCHAR(100),
    setting_value VARCHAR(255),
    PRIMARY KEY (group_id, setting_name)
);

-- Group Battle Mutes Table
CREATE TABLE IF NOT EXISTS group_battle_mutes (
    group_id BIGINT,
    telegram_id BIGINT,
    muted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, telegram_id)
);

-- Group Battles Table
CREATE TABLE IF NOT EXISTS group_battles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id BIGINT NOT NULL,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, ACTIVE, COMPLETED, CANCELLED
    created_by BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    starts_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    message_id BIGINT
);

-- Group Battle Participants Table
CREATE TABLE IF NOT EXISTS group_battle_participants (
    group_battle_id UUID REFERENCES group_battles(id) ON DELETE CASCADE,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    solved_at TIMESTAMP WITH TIME ZONE,
    solve_time_seconds INT,
    PRIMARY KEY (group_battle_id, telegram_id)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_problem_history_solved_at ON problem_history(solved_at);
CREATE INDEX IF NOT EXISTS idx_srs_reviews_next_date ON srs_reviews(next_review_date);
CREATE INDEX IF NOT EXISTS idx_battles_status ON battles(status);
CREATE INDEX IF NOT EXISTS idx_group_members_id ON group_members(telegram_id);
CREATE INDEX IF NOT EXISTS idx_group_battles_status ON group_battles(status);
