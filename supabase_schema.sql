-- Create a table for resumes
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a table for job descriptions
CREATE TABLE IF NOT EXISTS job_descriptions (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a table for tailored resumes
CREATE TABLE IF NOT EXISTS tailored_resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    job_id INTEGER NOT NULL,
    base_resume_id UUID NOT NULL REFERENCES resumes(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (job_id) REFERENCES job_descriptions(id)
);

-- Create a table for resume analysis
CREATE TABLE IF NOT EXISTS resume_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id UUID REFERENCES resumes(id),
    analysis TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_resume_analysis_resume_id ON resume_analysis(resume_id);
CREATE INDEX IF NOT EXISTS idx_job_descriptions_id ON job_descriptions(id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_user_job ON tailored_resumes(user_id, job_id);

-- Function to list all tables in the database
CREATE OR REPLACE FUNCTION get_tables()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN (
        SELECT jsonb_agg(table_name)
        FROM information_schema.tables
        WHERE table_schema = 'public'
    );
END;
$$;

-- Function to execute arbitrary SQL queries (with security safeguards)
CREATE OR REPLACE FUNCTION run_sql_query(sql_query TEXT, params JSONB DEFAULT '{}'::JSONB)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
    forbidden_keywords TEXT[] = ARRAY['DROP', 'TRUNCATE', 'DELETE FROM', 'UPDATE', 'ALTER USER', 'CREATE USER', 'GRANT', 'REVOKE', 'ROLE'];
    keyword TEXT;
BEGIN
    -- Basic security check to prevent destructive operations
    FOREACH keyword IN ARRAY forbidden_keywords LOOP
        IF position(upper(keyword) in upper(sql_query)) > 0 THEN
            RAISE EXCEPTION 'Forbidden SQL operation: %', keyword;
        END IF;
    END LOOP;

    -- Execute the query and capture results as JSON
    EXECUTE 'SELECT to_jsonb(array_agg(row_to_json(t))) FROM (' || sql_query || ') t'
    INTO result;
    
    RETURN COALESCE(result, '[]'::JSONB);
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object('error', SQLERRM);
END;
$$;

-- Create a function to get schema information
CREATE OR REPLACE FUNCTION get_schema_info()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    -- Get tables and their columns
    SELECT jsonb_object_agg(tables.table_name, columns.column_info)
    INTO result
    FROM (
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
    ) tables
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(
            jsonb_build_object(
                'column_name', column_name,
                'data_type', data_type,
                'is_nullable', is_nullable
            )
        ) AS column_info
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = tables.table_name
    ) columns ON true;
    
    RETURN result;
END;
$$; 