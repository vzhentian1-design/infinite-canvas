ALTER TABLE request_logs ADD COLUMN upstream_request_id varchar(200);
--> statement-breakpoint
ALTER TABLE request_logs ADD COLUMN estimate_snapshot jsonb;
