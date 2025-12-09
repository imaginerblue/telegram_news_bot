CREATE DATABASE IF NOT EXISTS rss;
USE rss;

CREATE TABLE IF NOT EXISTS rss_feeds (
    id INT AUTO_INCREMENT PRIMARY KEY,      -- 고유 번호
    url VARCHAR(512) NOT NULL UNIQUE,       -- RSS 주소 (중복 불가)
    title VARCHAR(255) NULL,                -- RSS 이름 (관리용, 선택사항)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP -- 등록일 (새 글 필터링용 핵심)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
