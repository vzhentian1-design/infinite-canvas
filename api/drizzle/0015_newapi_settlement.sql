ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS gateway_request_id varchar(64);
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS gateway_evidence jsonb;
CREATE INDEX IF NOT EXISTS request_logs_gateway_request_idx ON request_logs (gateway_request_id) WHERE gateway_request_id IS NOT NULL;
