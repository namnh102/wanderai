-- WanderAI Database Initialization
-- Bật các extensions cần thiết cho project

-- PostGIS: truy vấn không gian (tìm địa điểm gần, tính khoảng cách)
CREATE EXTENSION IF NOT EXISTS postgis;

-- pgvector: lưu và tìm kiếm vector embedding cho RAG (AI search)
CREATE EXTENSION IF NOT EXISTS vector;

-- uuid-ossp: tạo UUID v4 làm primary key
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verify extensions
DO $$
BEGIN
  RAISE NOTICE 'PostGIS version: %', PostGIS_Version();
  RAISE NOTICE 'pgvector installed: %', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
  RAISE NOTICE 'uuid-ossp installed: %', (SELECT extversion FROM pg_extension WHERE extname = 'uuid-ossp');
  RAISE NOTICE 'All extensions ready!';
END $$;
