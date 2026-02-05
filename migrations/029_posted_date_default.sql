-- Migration 029: Add DEFAULT CURRENT_DATE to posted_date
--
-- posted_date should only be set on first insert, never updated on re-scrape.
-- Adding DEFAULT ensures new rows get CURRENT_DATE automatically when
-- posted_date is omitted from the upsert payload.
--
-- Upsert behavior (PostgREST resolution=merge-duplicates):
--   INSERT (new job): posted_date not in payload -> Postgres DEFAULT applies
--   UPDATE (existing job): posted_date not in payload -> column left unchanged

ALTER TABLE enriched_jobs
ALTER COLUMN posted_date SET DEFAULT CURRENT_DATE;
