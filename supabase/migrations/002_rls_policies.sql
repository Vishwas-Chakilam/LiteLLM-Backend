-- Row Level Security Policies
-- Healthcare Multi-Agent Platform

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_execution_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_patient_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prior_authorizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tool_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;

-- Helper: current user role
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT AS $$
    SELECT role FROM public.users WHERE id = auth.uid()
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper: is admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT public.current_user_role() = 'admin'
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper: doctor has access to patient
CREATE OR REPLACE FUNCTION public.doctor_can_access_patient(p_patient_profile_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.doctor_patient_assignments dpa
        WHERE dpa.doctor_id = auth.uid()
          AND dpa.patient_id = p_patient_profile_id
    )
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE POLICY users_select_own ON public.users
    FOR SELECT USING (id = auth.uid() OR public.is_admin());

CREATE POLICY users_select_doctor_patients ON public.users
    FOR SELECT USING (
        public.current_user_role() = 'doctor'
        AND EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            JOIN public.doctor_patient_assignments dpa ON dpa.patient_id = pp.id
            WHERE pp.user_id = users.id AND dpa.doctor_id = auth.uid()
        )
    );

CREATE POLICY users_update_own ON public.users
    FOR UPDATE USING (id = auth.uid() OR public.is_admin());

CREATE POLICY users_admin_all ON public.users
    FOR ALL USING (public.is_admin());

-- ---------------------------------------------------------------------------
-- conversations
-- ---------------------------------------------------------------------------
CREATE POLICY conversations_patient_own ON public.conversations
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY conversations_patient_insert ON public.conversations
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY conversations_patient_update ON public.conversations
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY conversations_admin_all ON public.conversations
    FOR ALL USING (public.is_admin());

CREATE POLICY conversations_doctor_assigned ON public.conversations
    FOR SELECT USING (
        public.current_user_role() = 'doctor'
        AND EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            JOIN public.doctor_patient_assignments dpa ON dpa.patient_id = pp.id
            WHERE pp.user_id = conversations.user_id AND dpa.doctor_id = auth.uid()
        )
    );

-- ---------------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------------
CREATE POLICY messages_via_conversation ON public.messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.conversations c
            WHERE c.id = messages.conversation_id
              AND (
                  c.user_id = auth.uid()
                  OR public.is_admin()
                  OR (
                      public.current_user_role() = 'doctor'
                      AND EXISTS (
                          SELECT 1 FROM public.patient_profiles pp
                          JOIN public.doctor_patient_assignments dpa ON dpa.patient_id = pp.id
                          WHERE pp.user_id = c.user_id AND dpa.doctor_id = auth.uid()
                      )
                  )
              )
        )
    );

CREATE POLICY messages_insert_own ON public.messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.conversations c
            WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
        )
        OR public.is_admin()
    );

CREATE POLICY messages_admin_all ON public.messages
    FOR ALL USING (public.is_admin());

-- ---------------------------------------------------------------------------
-- agent_registry (read for authenticated, write for admin)
-- ---------------------------------------------------------------------------
CREATE POLICY agent_registry_read ON public.agent_registry
    FOR SELECT TO authenticated USING (is_active = TRUE OR public.is_admin());

CREATE POLICY agent_registry_admin_write ON public.agent_registry
    FOR ALL USING (public.is_admin());

-- Service role bypass for backend registration
CREATE POLICY agent_registry_service_insert ON public.agent_registry
    FOR INSERT TO service_role WITH CHECK (TRUE);

CREATE POLICY agent_registry_service_update ON public.agent_registry
    FOR UPDATE TO service_role USING (TRUE);

-- ---------------------------------------------------------------------------
-- agent_execution_logs
-- ---------------------------------------------------------------------------
CREATE POLICY agent_logs_via_conversation ON public.agent_execution_logs
    FOR SELECT USING (
        public.is_admin()
        OR EXISTS (
            SELECT 1 FROM public.conversations c
            WHERE c.id = agent_execution_logs.conversation_id
              AND c.user_id = auth.uid()
        )
    );

CREATE POLICY agent_logs_service_insert ON public.agent_execution_logs
    FOR INSERT TO service_role WITH CHECK (TRUE);

-- ---------------------------------------------------------------------------
-- patient_profiles
-- ---------------------------------------------------------------------------
CREATE POLICY patient_profiles_own ON public.patient_profiles
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY patient_profiles_own_update ON public.patient_profiles
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY patient_profiles_own_insert ON public.patient_profiles
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY patient_profiles_doctor ON public.patient_profiles
    FOR SELECT USING (public.doctor_can_access_patient(id));

CREATE POLICY patient_profiles_admin ON public.patient_profiles
    FOR ALL USING (public.is_admin());

-- ---------------------------------------------------------------------------
-- doctor_patient_assignments
-- ---------------------------------------------------------------------------
CREATE POLICY dpa_admin ON public.doctor_patient_assignments
    FOR ALL USING (public.is_admin());

CREATE POLICY dpa_doctor_read ON public.doctor_patient_assignments
    FOR SELECT USING (doctor_id = auth.uid());

-- ---------------------------------------------------------------------------
-- medical_records
-- ---------------------------------------------------------------------------
CREATE POLICY medical_records_patient ON public.medical_records
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            WHERE pp.id = medical_records.patient_id AND pp.user_id = auth.uid()
        )
    );

CREATE POLICY medical_records_doctor ON public.medical_records
    FOR SELECT USING (public.doctor_can_access_patient(patient_id));

CREATE POLICY medical_records_admin ON public.medical_records
    FOR ALL USING (public.is_admin());

CREATE POLICY medical_records_patient_insert ON public.medical_records
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            WHERE pp.id = medical_records.patient_id AND pp.user_id = auth.uid()
        )
    );

-- ---------------------------------------------------------------------------
-- prior_authorizations (insurance agents + patients + doctors + admin)
-- ---------------------------------------------------------------------------
CREATE POLICY prior_auth_patient ON public.prior_authorizations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            WHERE pp.id = prior_authorizations.patient_id AND pp.user_id = auth.uid()
        )
    );

CREATE POLICY prior_auth_insurance ON public.prior_authorizations
    FOR ALL USING (public.current_user_role() = 'insurance_agent');

CREATE POLICY prior_auth_doctor ON public.prior_authorizations
    FOR SELECT USING (public.doctor_can_access_patient(patient_id));

CREATE POLICY prior_auth_admin ON public.prior_authorizations
    FOR ALL USING (public.is_admin());

CREATE POLICY prior_auth_patient_insert ON public.prior_authorizations
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.patient_profiles pp
            WHERE pp.id = prior_authorizations.patient_id AND pp.user_id = auth.uid()
        )
        OR public.current_user_role() IN ('doctor', 'insurance_agent', 'admin')
    );

-- ---------------------------------------------------------------------------
-- tool_logs (admin + service role)
-- ---------------------------------------------------------------------------
CREATE POLICY tool_logs_admin ON public.tool_logs
    FOR SELECT USING (public.is_admin());

CREATE POLICY tool_logs_service_insert ON public.tool_logs
    FOR INSERT TO service_role WITH CHECK (TRUE);

-- ---------------------------------------------------------------------------
-- audit_logs (admin read; service insert)
-- ---------------------------------------------------------------------------
CREATE POLICY audit_logs_admin ON public.audit_logs
    FOR SELECT USING (public.is_admin());

CREATE POLICY audit_logs_own ON public.audit_logs
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY audit_logs_service_insert ON public.audit_logs
    FOR INSERT TO service_role WITH CHECK (TRUE);

-- ---------------------------------------------------------------------------
-- workflow_runs
-- ---------------------------------------------------------------------------
CREATE POLICY workflow_runs_via_conversation ON public.workflow_runs
    FOR SELECT USING (
        public.is_admin()
        OR EXISTS (
            SELECT 1 FROM public.conversations c
            WHERE c.id = workflow_runs.conversation_id AND c.user_id = auth.uid()
        )
    );

CREATE POLICY workflow_runs_service ON public.workflow_runs
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
