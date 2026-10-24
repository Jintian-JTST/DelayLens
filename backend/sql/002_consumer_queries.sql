-- B/M SQL contract. Bind parameters through the driver, never string formatting.
SET TIME ZONE 'UTC';

-- SELECT route_id, vehicle_id, origin_observed_at, destination_observed_at,
--        ride_seconds, origin_method, destination_method
-- FROM get_segments WHERE route_id = $1 ORDER BY origin_observed_at;

SELECT route_id, vehicle_id, origin_observed_at, destination_observed_at,
       ride_seconds, origin_method, destination_method
FROM get_segments ORDER BY route_id, origin_observed_at;

SELECT route_id, trips_observed, hours_covered FROM route_coverage ORDER BY route_id;

-- Recorder coverage is prediction presence, not completed trips.
SELECT hour, line_id, direction, naptan_id, vehicles, predictions
FROM coverage_hourly ORDER BY hour, line_id, direction, naptan_id;

-- Real ingestion freshness; empty successful polls are recorded separately.
SELECT count(*) AS rows, min(polled_at) AS first_polled_at,
       max(polled_at) AS last_polled_at FROM arrival_predictions;
SELECT max(polled_at) AS last_successful_poll FROM poll_runs;

-- Actual columnstore statistics; a ratio is not available before chunks convert.
SELECT * FROM hypertable_columnstore_stats('arrival_predictions');
SELECT * FROM timescaledb_information.jobs
WHERE hypertable_name IN ('arrival_predictions', 'coverage_hourly');
