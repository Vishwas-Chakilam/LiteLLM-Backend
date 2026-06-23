-- Hospital master data (single-hospital deployment; hospital_id for future multi-site)

-- ---------------------------------------------------------------------------
-- hospitals
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    npi TEXT,
    website TEXT,
    er_wait_minutes INTEGER,
    visiting_hours JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hospitals_slug ON public.hospitals(slug);

-- ---------------------------------------------------------------------------
-- hospital_insurance_plans (accepted insurers at this hospital)
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_insurance_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    insurer_id TEXT NOT NULL,
    insurer_name TEXT NOT NULL,
    plan_types JSONB DEFAULT '[]'::jsonb,
    in_network BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (hospital_id, insurer_id)
);

CREATE INDEX idx_hospital_insurance_hospital ON public.hospital_insurance_plans(hospital_id);

-- ---------------------------------------------------------------------------
-- hospital_departments
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    floor TEXT,
    phone TEXT,
    hours TEXT,
    services JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hospital_departments_hospital ON public.hospital_departments(hospital_id);

-- ---------------------------------------------------------------------------
-- hospital_providers
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    department TEXT,
    npi TEXT,
    accepting_patients BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hospital_providers_hospital ON public.hospital_providers(hospital_id);
CREATE INDEX idx_hospital_providers_specialty ON public.hospital_providers(specialty);

-- ---------------------------------------------------------------------------
-- hospital_services (procedures, imaging, etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    service_code TEXT,
    name TEXT NOT NULL,
    department TEXT,
    requires_prior_auth BOOLEAN NOT NULL DEFAULT FALSE,
    typical_cost_usd NUMERIC,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hospital_services_hospital ON public.hospital_services(hospital_id);

-- ---------------------------------------------------------------------------
-- hospital_payer_rules (hospital-specific payer contracts)
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_payer_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    insurer_id TEXT NOT NULL,
    procedure_type TEXT NOT NULL DEFAULT 'general',
    rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (hospital_id, insurer_id, procedure_type)
);

CREATE INDEX idx_hospital_payer_rules_hospital ON public.hospital_payer_rules(hospital_id);

-- ---------------------------------------------------------------------------
-- hospital_lab_reference_ranges
-- ---------------------------------------------------------------------------
CREATE TABLE public.hospital_lab_reference_ranges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    marker TEXT NOT NULL,
    unit TEXT,
    low NUMERIC,
    high NUMERIC,
    critical_low NUMERIC,
    critical_high NUMERIC,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (hospital_id, marker)
);

CREATE INDEX idx_hospital_lab_ranges_hospital ON public.hospital_lab_reference_ranges(hospital_id);

-- updated_at trigger for hospitals
CREATE TRIGGER trg_hospitals_updated_at
    BEFORE UPDATE ON public.hospitals
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- RLS: hospital master data readable by authenticated users; writable by admin
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_insurance_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_payer_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_lab_reference_ranges ENABLE ROW LEVEL SECURITY;

CREATE POLICY hospitals_read ON public.hospitals
    FOR SELECT TO authenticated USING (is_active = TRUE OR public.is_admin());

CREATE POLICY hospitals_admin ON public.hospitals
    FOR ALL USING (public.is_admin());

CREATE POLICY hospitals_service ON public.hospitals
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_insurance_read ON public.hospital_insurance_plans
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_insurance_service ON public.hospital_insurance_plans
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_departments_read ON public.hospital_departments
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_departments_service ON public.hospital_departments
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_providers_read ON public.hospital_providers
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_providers_service ON public.hospital_providers
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_services_read ON public.hospital_services
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_services_service ON public.hospital_services
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_payer_rules_read ON public.hospital_payer_rules
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_payer_rules_service ON public.hospital_payer_rules
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY hospital_lab_ranges_read ON public.hospital_lab_reference_ranges
    FOR SELECT TO authenticated USING (TRUE);

CREATE POLICY hospital_lab_ranges_service ON public.hospital_lab_reference_ranges
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
