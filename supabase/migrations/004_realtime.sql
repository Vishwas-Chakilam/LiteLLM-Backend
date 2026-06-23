-- Enable Supabase Realtime for live updates

ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
ALTER PUBLICATION supabase_realtime ADD TABLE public.workflow_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE public.prior_authorizations;

-- Replica identity for full row data on updates
ALTER TABLE public.messages REPLICA IDENTITY FULL;
ALTER TABLE public.workflow_runs REPLICA IDENTITY FULL;
ALTER TABLE public.prior_authorizations REPLICA IDENTITY FULL;
