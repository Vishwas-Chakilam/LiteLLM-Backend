-- Seed fake hospital data: City General Hospital (single-site demo)

INSERT INTO public.hospitals (
    id, slug, name, address, city, state, zip, phone, npi, website,
    er_wait_minutes, visiting_hours, metadata
) VALUES (
    'a0000000-0000-4000-8000-000000000001',
    'city_general',
    'City General Hospital',
    '1200 Medical Center Drive',
    'Springfield',
    'IL',
    '62701',
    '(555) 100-2000',
    '1234567890',
    'https://citygeneral.example.org',
    35,
    '{"general": "8am-8pm", "icu": "visiting by appointment", "er": "24/7"}'::jsonb,
    '{"beds": 420, "trauma_level": 2, "teaching_hospital": true}'::jsonb
) ON CONFLICT (slug) DO NOTHING;

-- Accepted insurance plans
INSERT INTO public.hospital_insurance_plans (hospital_id, insurer_id, insurer_name, plan_types, in_network, notes) VALUES
    ('a0000000-0000-4000-8000-000000000001', 'aetna', 'Aetna', '["PPO", "HMO", "EPO"]', TRUE, 'Full in-network coverage for most services'),
    ('a0000000-0000-4000-8000-000000000001', 'united', 'UnitedHealthcare', '["Choice Plus", "HMO", "Medicare Advantage"]', TRUE, 'Prior auth required for MRI and specialty drugs'),
    ('a0000000-0000-4000-8000-000000000001', 'cigna', 'Cigna', '["Open Access Plus", "LocalPlus"]', TRUE, 'In-network for hospital and affiliated clinics'),
    ('a0000000-0000-4000-8000-000000000001', 'bcbs', 'Blue Cross Blue Shield', '["PPO", "Blue Choice"]', TRUE, 'State BCBS plans accepted'),
    ('a0000000-0000-4000-8000-000000000001', 'medicare', 'Medicare', '["Part A", "Part B"]', TRUE, 'Medicare assignment accepted'),
    ('a0000000-0000-4000-8000-000000000001', 'medicaid', 'Medicaid', '["State Medicaid"]', TRUE, 'Illinois Medicaid accepted'),
    ('a0000000-0000-4000-8000-000000000001', 'humana', 'Humana', '["HMO", "PPO"]', FALSE, 'Out of network — emergency stabilization only')
ON CONFLICT (hospital_id, insurer_id) DO NOTHING;

-- Departments
INSERT INTO public.hospital_departments (hospital_id, name, floor, phone, hours, services) VALUES
    ('a0000000-0000-4000-8000-000000000001', 'Emergency Department', '1', '(555) 100-2100', '24/7', '["trauma", "acute care", "stabilization"]'),
    ('a0000000-0000-4000-8000-000000000001', 'Cardiology', '3', '(555) 100-2200', 'Mon-Fri 8am-5pm', '["echo", "stress test", "cardiac cath"]'),
    ('a0000000-0000-4000-8000-000000000001', 'Radiology & Imaging', '2', '(555) 100-2300', 'Mon-Sat 7am-7pm', '["xray", "mri", "ct", "ultrasound"]'),
    ('a0000000-0000-4000-8000-000000000001', 'Laboratory', '1', '(555) 100-2400', '24/7', '["cbc", "chemistry", "pathology"]'),
    ('a0000000-0000-4000-8000-000000000001', 'Orthopedics', '4', '(555) 100-2500', 'Mon-Fri 8am-6pm', '["joint replacement", "sports medicine"]'),
    ('a0000000-0000-4000-8000-000000000001', 'Primary Care', '5', '(555) 100-2600', 'Mon-Fri 8am-8pm', '["wellness", "chronic care", "referrals"]');

-- Providers
INSERT INTO public.hospital_providers (hospital_id, name, specialty, department, npi, accepting_patients) VALUES
    ('a0000000-0000-4000-8000-000000000001', 'Dr. Sarah Chen', 'Cardiology', 'Cardiology', '1111111111', TRUE),
    ('a0000000-0000-4000-8000-000000000001', 'Dr. James Wilson', 'Orthopedic Surgery', 'Orthopedics', '2222222222', TRUE),
    ('a0000000-0000-4000-8000-000000000001', 'Dr. Maria Lopez', 'Internal Medicine', 'Primary Care', '3333333333', TRUE),
    ('a0000000-0000-4000-8000-000000000001', 'Dr. Robert Kim', 'Radiology', 'Radiology & Imaging', '4444444444', TRUE),
    ('a0000000-0000-4000-8000-000000000001', 'Dr. Emily Patel', 'Emergency Medicine', 'Emergency Department', '5555555555', TRUE);

-- Services
INSERT INTO public.hospital_services (hospital_id, service_code, name, department, requires_prior_auth, typical_cost_usd) VALUES
    ('a0000000-0000-4000-8000-000000000001', '70553', 'MRI Brain with contrast', 'Radiology & Imaging', TRUE, 2800),
    ('a0000000-0000-4000-8000-000000000001', '72148', 'MRI Lumbar Spine', 'Radiology & Imaging', TRUE, 2400),
    ('a0000000-0000-4000-8000-000000000001', '80053', 'Comprehensive Metabolic Panel', 'Laboratory', FALSE, 85),
    ('a0000000-0000-4000-8000-000000000001', '85025', 'Complete Blood Count', 'Laboratory', FALSE, 45),
    ('a0000000-0000-4000-8000-000000000001', '27447', 'Total Knee Replacement', 'Orthopedics', TRUE, 45000);

-- Hospital-specific payer rules
INSERT INTO public.hospital_payer_rules (hospital_id, insurer_id, procedure_type, rules) VALUES
    ('a0000000-0000-4000-8000-000000000001', 'aetna', 'mri', '{"requires_clinical_notes": true, "requires_prior_treatment": true, "min_weeks_conservative": 6}'::jsonb),
    ('a0000000-0000-4000-8000-000000000001', 'aetna', 'general', '{"requires_referral": false, "er_copay_applies": true}'::jsonb),
    ('a0000000-0000-4000-8000-000000000001', 'united', 'mri', '{"requires_clinical_notes": true, "requires_imaging_history": true}'::jsonb),
    ('a0000000-0000-4000-8000-000000000001', 'united', 'general', '{"requires_referral": true}'::jsonb),
    ('a0000000-0000-4000-8000-000000000001', 'cigna', 'specialty_drug', '{"requires_step_therapy": true}'::jsonb),
    ('a0000000-0000-4000-8000-000000000001', 'bcbs', 'general', '{"requires_clinical_notes": true}'::jsonb)
ON CONFLICT (hospital_id, insurer_id, procedure_type) DO NOTHING;

-- Lab reference ranges (hospital lab)
INSERT INTO public.hospital_lab_reference_ranges (hospital_id, marker, unit, low, high, critical_low, critical_high, notes) VALUES
    ('a0000000-0000-4000-8000-000000000001', 'hemoglobin', 'g/dL', 12.0, 17.5, 7.0, 20.0, 'Adult reference'),
    ('a0000000-0000-4000-8000-000000000001', 'wbc', 'cells/uL', 4500, 11000, 2000, 30000, 'White blood cell count'),
    ('a0000000-0000-4000-8000-000000000001', 'glucose', 'mg/dL', 70, 99, 50, 400, 'Fasting glucose'),
    ('a0000000-0000-4000-8000-000000000001', 'creatinine', 'mg/dL', 0.7, 1.3, 0.3, 5.0, 'Kidney function'),
    ('a0000000-0000-4000-8000-000000000001', 'platelets', 'cells/uL', 150000, 400000, 50000, 1000000, 'Platelet count')
ON CONFLICT (hospital_id, marker) DO NOTHING;

-- Demo test patients (optional profiles for playground — link to users when they sign up)
-- Note: patient_profiles require auth.users; seed via app or signup hook.
-- Store demo patient template in hospital metadata for reference:
UPDATE public.hospitals
SET metadata = metadata || '{
  "demo_patients": [
    {"name": "Jane Demo", "insurance_provider": "aetna", "age": 45, "allergies": ["penicillin"]},
    {"name": "John Demo", "insurance_provider": "united", "age": 62, "allergies": []}
  ]
}'::jsonb
WHERE slug = 'city_general';
