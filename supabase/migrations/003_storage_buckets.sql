-- Storage buckets and policies
-- Private buckets with signed URL access

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
    ('medical-records', 'medical-records', FALSE, 52428800, ARRAY[
        'application/pdf', 'image/jpeg', 'image/png', 'image/dicom',
        'text/plain', 'application/json'
    ]),
    ('patient-uploads', 'patient-uploads', FALSE, 26214400, ARRAY[
        'application/pdf', 'image/jpeg', 'image/png', 'text/plain'
    ]),
    ('lab-reports', 'lab-reports', FALSE, 26214400, ARRAY[
        'application/pdf', 'image/jpeg', 'image/png', 'text/csv'
    ]),
    ('prior-auth-documents', 'prior-auth-documents', FALSE, 52428800, ARRAY[
        'application/pdf', 'image/jpeg', 'image/png', 'text/plain'
    ])
ON CONFLICT (id) DO NOTHING;

-- Helper: patient owns storage path (path format: {user_id}/...)
CREATE OR REPLACE FUNCTION public.storage_path_owned_by_user(object_name TEXT)
RETURNS BOOLEAN AS $$
    SELECT split_part(object_name, '/', 1) = auth.uid()::text
$$ LANGUAGE sql STABLE;

-- medical-records
CREATE POLICY medical_records_storage_patient ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'medical-records'
        AND public.storage_path_owned_by_user(name)
    )
    WITH CHECK (
        bucket_id = 'medical-records'
        AND public.storage_path_owned_by_user(name)
    );

CREATE POLICY medical_records_storage_admin ON storage.objects
    FOR ALL TO authenticated
    USING (bucket_id = 'medical-records' AND public.is_admin())
    WITH CHECK (bucket_id = 'medical-records' AND public.is_admin());

-- patient-uploads
CREATE POLICY patient_uploads_storage ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'patient-uploads'
        AND public.storage_path_owned_by_user(name)
    )
    WITH CHECK (
        bucket_id = 'patient-uploads'
        AND public.storage_path_owned_by_user(name)
    );

-- lab-reports
CREATE POLICY lab_reports_storage_patient ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'lab-reports'
        AND public.storage_path_owned_by_user(name)
    )
    WITH CHECK (
        bucket_id = 'lab-reports'
        AND public.storage_path_owned_by_user(name)
    );

CREATE POLICY lab_reports_storage_doctor ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'lab-reports'
        AND public.current_user_role() = 'doctor'
    );

-- prior-auth-documents
CREATE POLICY prior_auth_docs_patient ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'prior-auth-documents'
        AND public.storage_path_owned_by_user(name)
    )
    WITH CHECK (
        bucket_id = 'prior-auth-documents'
        AND public.storage_path_owned_by_user(name)
    );

CREATE POLICY prior_auth_docs_insurance ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'prior-auth-documents'
        AND public.current_user_role() = 'insurance_agent'
    )
    WITH CHECK (
        bucket_id = 'prior-auth-documents'
        AND public.current_user_role() = 'insurance_agent'
    );

-- Service role full access for backend signed URL generation
CREATE POLICY storage_service_role ON storage.objects
    FOR ALL TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);
