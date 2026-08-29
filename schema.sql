-- =========================================================
-- Schema & Table Initialization for AgreementAI Platform
-- Schema: agreement | All tables prefixed with agr_
-- =========================================================

CREATE SCHEMA IF NOT EXISTS agreement;

SET search_path TO agreement, public;

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS agreement.agr_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone_number VARCHAR(20),
    role VARCHAR(50) DEFAULT 'user', -- 'user', 'landlord', 'tenant', 'agent', 'admin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Templates Master Table
CREATE TABLE IF NOT EXISTS agreement.agr_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_code VARCHAR(100) UNIQUE NOT NULL, -- e.g., 'RESIDENTIAL_RENTAL_11M', 'COMMERCIAL_LEASE'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL, -- 'Residential', 'Commercial', 'Sale', 'POA'
    state_code VARCHAR(10) DEFAULT 'KA',
    template_body TEXT NOT NULL,
    placeholder_schema JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Master Agreements Table
CREATE TABLE IF NOT EXISTS agreement.agr_agreements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_number VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID REFERENCES agreement.agr_users(id) ON DELETE SET NULL,
    template_id UUID REFERENCES agreement.agr_templates(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    state_code VARCHAR(10) NOT NULL DEFAULT 'KA',
    city VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'AI_AUDITED', 'PENDING_STAMP', 'COMPLETED'
    monthly_rent NUMERIC(12, 2) DEFAULT 0.00,
    security_deposit NUMERIC(12, 2) DEFAULT 0.00,
    escalation_percentage NUMERIC(5, 2) DEFAULT 5.00,
    tenure_months INT DEFAULT 11,
    start_date DATE,
    end_date DATE,
    custom_clauses JSONB DEFAULT '[]'::jsonb,
    ai_compliance_score NUMERIC(5, 2) DEFAULT 98.50,
    generated_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Parties Table (Lessors, Lessees, Witnesses) with Aadhaar OCR support
CREATE TABLE IF NOT EXISTS agreement.agr_parties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_id UUID REFERENCES agreement.agr_agreements(id) ON DELETE CASCADE,
    party_type VARCHAR(50) NOT NULL, -- 'LESSOR', 'LESSEE', 'WITNESS', 'GUARANTOR'
    full_name VARCHAR(150) NOT NULL,
    relation_type VARCHAR(20), -- 'S/O', 'D/O', 'W/O', 'C/O'
    relation_name VARCHAR(150),
    date_of_birth DATE,
    gender VARCHAR(20),
    email VARCHAR(255),
    phone VARCHAR(20),
    pan_number VARCHAR(20),
    aadhaar_masked VARCHAR(20), -- e.g. 'XXXX-XXXX-1234'
    address_line1 TEXT,
    locality VARCHAR(150),
    city VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(20),
    is_ocr_verified BOOLEAN DEFAULT FALSE,
    ocr_raw_data JSONB,
    signing_status VARCHAR(50) DEFAULT 'PENDING',
    signed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Properties Table
CREATE TABLE IF NOT EXISTS agreement.agr_properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_id UUID REFERENCES agreement.agr_agreements(id) ON DELETE CASCADE,
    property_type VARCHAR(50) DEFAULT 'APARTMENT', -- 'APARTMENT', 'INDEPENDENT_HOUSE', 'COMMERCIAL'
    building_name VARCHAR(255),
    door_number VARCHAR(100),
    street VARCHAR(255),
    locality VARCHAR(150),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    pincode VARCHAR(20),
    super_built_up_area_sqft INT,
    furnishing_status VARCHAR(50) DEFAULT 'SEMI_FURNISHED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Stamp Paper Details
CREATE TABLE IF NOT EXISTS agreement.agr_stamps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_id UUID REFERENCES agreement.agr_agreements(id) ON DELETE CASCADE,
    state_code VARCHAR(10) NOT NULL,
    stamp_certificate_number VARCHAR(100),
    stamp_duty_amount NUMERIC(10, 2) NOT NULL,
    first_party_name VARCHAR(150),
    second_party_name VARCHAR(150),
    stamp_file_url TEXT,
    status VARCHAR(50) DEFAULT 'ATTACHED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Document Uploads Table (Aadhaar cards, PAN, Stamp Paper uploads)
CREATE TABLE IF NOT EXISTS agreement.agr_document_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_id UUID REFERENCES agreement.agr_agreements(id) ON DELETE CASCADE,
    party_id UUID REFERENCES agreement.agr_parties(id) ON DELETE SET NULL,
    document_type VARCHAR(50) NOT NULL, -- 'AADHAAR_FRONT', 'AADHAAR_BACK', 'PAN_CARD', 'STAMP_PAPER'
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INT,
    mime_type VARCHAR(50),
    extracted_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Stamp Duty Master Lookup Rates Table
CREATE TABLE IF NOT EXISTS agreement.agr_stamp_duty_rates (
    id SERIAL PRIMARY KEY,
    state_code VARCHAR(10) NOT NULL,
    state_name VARCHAR(100) NOT NULL,
    min_tenure_months INT DEFAULT 1,
    max_tenure_months INT DEFAULT 11,
    duty_amount NUMERIC(10, 2) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Audit Logs Table
CREATE TABLE IF NOT EXISTS agreement.agr_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agreement_id UUID REFERENCES agreement.agr_agreements(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- 'AGREEMENT_CREATED', 'AADHAAR_OCR_PROCESSED', 'AI_DRAFTED', 'PDF_EXPORTED'
    performed_by VARCHAR(150) DEFAULT 'system',
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. India PIN Code Master Table
CREATE TABLE IF NOT EXISTS agreement.agr_pincodes (
    pincode VARCHAR(6) PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    district VARCHAR(100),
    division VARCHAR(100),
    state VARCHAR(100) NOT NULL,
    office VARCHAR(150),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Indexes for High-Frequency Query Paths
CREATE INDEX IF NOT EXISTS idx_agr_agreements_user_id ON agreement.agr_agreements(user_id);
CREATE INDEX IF NOT EXISTS idx_agr_agreements_status ON agreement.agr_agreements(status);
CREATE INDEX IF NOT EXISTS idx_agr_agreements_created_at ON agreement.agr_agreements(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agr_parties_agreement_id ON agreement.agr_parties(agreement_id);
CREATE INDEX IF NOT EXISTS idx_agr_properties_agreement_id ON agreement.agr_properties(agreement_id);
CREATE INDEX IF NOT EXISTS idx_agr_document_uploads_agreement_id ON agreement.agr_document_uploads(agreement_id);
CREATE INDEX IF NOT EXISTS idx_agr_audit_logs_agreement_id ON agreement.agr_audit_logs(agreement_id);
CREATE INDEX IF NOT EXISTS idx_agr_pincodes_pincode ON agreement.agr_pincodes(pincode);

-- =========================================================
-- Seed Default Data (Stamp Rates & Templates)
-- =========================================================

INSERT INTO agreement.agr_stamp_duty_rates (state_code, state_name, min_tenure_months, max_tenure_months, duty_amount, description)
VALUES 
('KA', 'Karnataka', 1, 11, 200.00, 'Rs. 200 Stamp paper for <11 month tenure'),
('MH', 'Maharashtra', 1, 11, 500.00, 'Rs. 500 Stamp paper for Leave & License'),
('DL', 'Delhi NCR', 1, 11, 100.00, 'Rs. 100 Stamp paper standard'),
('TN', 'Tamil Nadu', 1, 11, 100.00, 'Rs. 100 Stamp paper standard')
ON CONFLICT DO NOTHING;

INSERT INTO agreement.agr_templates (template_code, title, description, category, state_code, template_body)
VALUES 
('RESIDENTIAL_RENTAL_11M', '11-Month Residential Rental Agreement', 'Standard Indian 11-month residential tenancy agreement with 5% annual escalation.', 'Residential', 'KA', 'RENTAL AGREEMENT FOR RESIDENTIAL PREMISES...'),
('COMMERCIAL_LEASE', 'Commercial Property Lease Agreement', 'Comprehensive commercial lease agreement for offices, shops, and warehouses.', 'Commercial', 'KA', 'COMMERCIAL LEASE AGREEMENT...'),
('MAHA_LEAVE_LICENSE', 'Leave and License Agreement (Maharashtra)', 'Maharashtra Rent Control Act compliant leave and license contract.', 'Residential', 'MH', 'LEAVE AND LICENSE AGREEMENT...'),
('AGREEMENT_TO_SELL', 'Agreement to Sell / Sale Deed', 'Legally binding real estate property sale agreement with advance payment terms.', 'Sale', 'KA', 'AGREEMENT TO SELL PROPERTY...')
ON CONFLICT DO NOTHING;
