CREATE DATABASE IF NOT EXISTS huahua_trade DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE huahua_trade;

CREATE TABLE IF NOT EXISTS trade_stock_master (
  stock_code VARCHAR(16) NOT NULL,
  stock_name VARCHAR(128) NULL,
  source VARCHAR(32) NULL,
  updated_at DATETIME NULL,
  PRIMARY KEY (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_watchlist (
  stock_code VARCHAR(16) NOT NULL,
  created_at DATETIME NULL,
  PRIMARY KEY (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_stock_daily (
  stock_code VARCHAR(16) NOT NULL,
  trade_date DATE NOT NULL,
  close_price DOUBLE NULL,
  volume BIGINT NULL,
  rsi14 DOUBLE NULL,
  ma20 DOUBLE NULL,
  stock_name VARCHAR(128) NULL,
  PRIMARY KEY (stock_code, trade_date),
  KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_stock_financial (
  stock_code VARCHAR(16) NOT NULL,
  report_date DATE NOT NULL,
  data_source VARCHAR(32) NULL,
  payload_json JSON NULL,
  PRIMARY KEY (stock_code, report_date),
  KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_stock_news (
  stock_code VARCHAR(16) NOT NULL,
  published_at DATETIME NOT NULL,
  news_type VARCHAR(32) NULL,
  title VARCHAR(255) NULL,
  content TEXT NULL,
  PRIMARY KEY (stock_code, published_at),
  KEY idx_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_macro_indicator (
  indicator_date DATE NOT NULL,
  indicator_name VARCHAR(128) NOT NULL,
  indicator_value DOUBLE NULL,
  source VARCHAR(32) NULL,
  PRIMARY KEY (indicator_date, indicator_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_rate_daily (
  rate_date DATE NOT NULL,
  rate_name VARCHAR(128) NOT NULL,
  rate_value DOUBLE NULL,
  PRIMARY KEY (rate_date, rate_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_report_consensus (
  stock_code VARCHAR(16) NOT NULL,
  broker VARCHAR(128) NOT NULL,
  report_date DATE NOT NULL,
  rating VARCHAR(64) NULL,
  target_price DOUBLE NULL,
  PRIMARY KEY (stock_code, broker, report_date),
  KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_calendar_event (
  event_date DATE NOT NULL,
  country VARCHAR(64) NOT NULL,
  importance VARCHAR(32) NOT NULL,
  source VARCHAR(32) NOT NULL,
  title VARCHAR(255) NULL,
  payload_json JSON NULL,
  PRIMARY KEY (event_date, country, importance, source),
  KEY idx_event_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_stock_status (
  stock_code VARCHAR(16) NOT NULL,
  sector_1 VARCHAR(128) NULL,
  sector_2 VARCHAR(128) NULL,
  updated_at DATETIME NULL,
  PRIMARY KEY (stock_code),
  KEY idx_sector_1 (sector_1),
  KEY idx_sector_2 (sector_2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_sector_daily (
  sector_name VARCHAR(128) NOT NULL,
  sector_level INT NOT NULL,
  trade_date DATE NOT NULL,
  close_idx DOUBLE NULL,
  total_amount DOUBLE NULL,
  PRIMARY KEY (sector_name, sector_level, trade_date),
  KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
