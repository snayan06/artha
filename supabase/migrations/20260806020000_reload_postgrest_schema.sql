-- Keep Supabase's REST function catalog synchronized after versioned RPC changes.
-- This changes no ledger data; it only asks PostgREST to rebuild its schema cache.
select pg_notify('pgrst', 'reload schema');
