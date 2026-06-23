-- Healthcare Multi-Agent Platform — Core Schema
-- Run in Supabase SQL Editor or via supabase db push

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- A. users (profiles linked to Supabase Auth)
-- ---------------------------------------------------------------------------
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'patient'
        CHECK (role IN ('patient', 'doctor', 'admin', 'insurance_agent', 'support')),
    phone TEXT,
    organization TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON public.users(email);
CREATE INDEX idx_users_role ON public.users(role);

-- ---------------------------------------------------------------------------
-- B. conversations
-- ---------------------------------------------------------------------------
CREATE TABLE public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'escalated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX idx_conversations_session_id ON public.conversations(session_id);
CREATE INDEX idx_conversations_status ON public.conversations(status);

-- ---------------------------------------------------------------------------
-- C. messages
-- ---------------------------------------------------------------------------
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL
        CHECK (sender_type IN ('user', 'assistant', 'agent', 'system')),
    sender_agent_id TEXT,
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX idx_messages_created_at ON public.messages(created_at);
CREATE INDEX idx_messages_sender_type ON public.messages(sender_type);

-- ---------------------------------------------------------------------------
-- D. agent_registry
-- ---------------------------------------------------------------------------
CREATE TABLE public.agent_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    capabilities JSONB DEFAULT '[]'::jsonb,
    tools JSONB DEFAULT '[]'::jsonb,
    preferred_model TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    safety_level TEXT DEFAULT 'standard',
    version TEXT DEFAULT '1.0.0',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_registry_domain ON public.agent_registry(domain);
CREATE INDEX idx_agent_registry_is_active ON public.agent_registry(is_active);
CREATE INDEX idx_agent_registry_capabilities ON public.agent_registry USING GIN (capabilities);

-- ---------------------------------------------------------------------------
-- E. agent_execution_logs
-- ---------------------------------------------------------------------------
CREATE TABLE public.agent_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    agent_id TEXT NOT NULL,
    input JSONB DEFAULT '{}'::jsonb,
    output JSONB DEFAULT '{}'::jsonb,
    execution_time_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'success'
        CHECK (status IN ('success', 'failed', 'timeout')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_execution_logs_conversation ON public.agent_execution_logs(conversation_id);
CREATE INDEX idx_agent_execution_logs_agent_id ON public.agent_execution_logs(agent_id);
CREATE INDEX idx_agent_execution_logs_status ON public.agent_execution_logs(status);

-- ---------------------------------------------------------------------------
-- F. patient_profiles
-- ---------------------------------------------------------------------------
CREATE TABLE public.patient_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    age INTEGER,
    gender TEXT,
    medical_history JSONB DEFAULT '[]'::jsonb,
    allergies JSONB DEFAULT '[]'::jsonb,
    current_medications JSONB DEFAULT '[]'::jsonb,
    insurance_provider TEXT,
    emergency_contact JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_patient_profiles_user_id ON public.patient_profiles(user_id);

-- Doctor-patient assignment for RBAC
CREATE TABLE public.doctor_patient_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES public.patient_profiles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doctor_id, patient_id)
);

CREATE INDEX idx_doctor_patient_doctor ON public.doctor_patient_assignments(doctor_id);
CREATE INDEX idx_doctor_patient_patient ON public.doctor_patient_assignments(patient_id);

-- ---------------------------------------------------------------------------
-- G. medical_records
-- ---------------------------------------------------------------------------
CREATE TABLE public.medical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES public.patient_profiles(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL
        CHECK (record_type IN ('blood_report', 'xray', 'prescription', 'discharge_summary')),
    file_url TEXT,
    summary TEXT,
    structured_data JSONB DEFAULT '{}'::jsonb,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_medical_records_patient_id ON public.medical_records(patient_id);
CREATE INDEX idx_medical_records_record_type ON public.medical_records(record_type);

-- ---------------------------------------------------------------------------
-- H. prior_authorizations
-- ---------------------------------------------------------------------------
CREATE TABLE public.prior_authorizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES public.patient_profiles(id) ON DELETE CASCADE,
    insurer TEXT NOT NULL,
    diagnosis_codes JSONB DEFAULT '[]'::jsonb,
    procedure_codes JSONB DEFAULT '[]'::jsonb,
    clinical_notes TEXT,
    approval_probability FLOAT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'denied', 'incomplete')),
    missing_documents JSONB DEFAULT '[]'::jsonb,
    denial_risk TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prior_auth_patient_id ON public.prior_authorizations(patient_id);
CREATE INDEX idx_prior_auth_status ON public.prior_authorizations(status);
CREATE INDEX idx_prior_auth_insurer ON public.prior_authorizations(insurer);

-- ---------------------------------------------------------------------------
-- I. tool_logs
-- ---------------------------------------------------------------------------
CREATE TABLE public.tool_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT,
    tool_name TEXT NOT NULL,
    request JSONB DEFAULT '{}'::jsonb,
    response JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'success',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_logs_agent_id ON public.tool_logs(agent_id);
CREATE INDEX idx_tool_logs_tool_name ON public.tool_logs(tool_name);

-- ---------------------------------------------------------------------------
-- J. audit_logs
-- ---------------------------------------------------------------------------
CREATE TABLE public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at);

-- ---------------------------------------------------------------------------
-- K. workflow_runs
-- ---------------------------------------------------------------------------
CREATE TABLE public.workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    workflow_name TEXT NOT NULL,
    state JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_workflow_runs_conversation ON public.workflow_runs(conversation_id);
CREATE INDEX idx_workflow_runs_status ON public.workflow_runs(status);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON public.conversations
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_patient_profiles_updated_at
    BEFORE UPDATE ON public.patient_profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_prior_auth_updated_at
    BEFORE UPDATE ON public.prior_authorizations
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Auto-create user profile on signup
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, email, full_name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'role', 'patient')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
