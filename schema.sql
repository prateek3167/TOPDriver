CREATE DATABASE IF NOT EXISTS support_analytics
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE support_analytics;

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id BIGINT PRIMARY KEY,
    created_time DATETIME NOT NULL,
    closed_time DATETIME NULL,
    created_by VARCHAR(100),
    product VARCHAR(100),
    campaigns VARCHAR(100),
    category VARCHAR(100),
    sub_category VARCHAR(150),
    sub_category_classification VARCHAR(150),
    subject VARCHAR(500),
    classifications VARCHAR(50),
    ticket_owner VARCHAR(100),
    category_subcategory VARCHAR(255),
    full_category_hierarchy VARCHAR(300),
    resolution_time_days DECIMAL(10, 2) GENERATED ALWAYS AS (
        TIMESTAMPDIFF(MINUTE, created_time, closed_time) / 1440.0
    ) STORED,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_created_time (created_time),
    INDEX idx_product (product),
    INDEX idx_ticket_owner (ticket_owner),
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;