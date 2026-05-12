-- Migration: 002_med_case
-- Creates the MED_CASE table for case metadata extraction from PDFs
-- Compatible with PostgreSQL 16 + pgvector

CREATE TABLE IF NOT EXISTS med_case (
    id                   SERIAL PRIMARY KEY,
    file_uuid            VARCHAR(36)    NOT NULL REFERENCES core_file(file_uuid),
    age                  TEXT,
    bmi                  TEXT,
    menstruation         TEXT,
    infertility          TEXT,
    lifestyle            TEXT,
    present_symptoms     TEXT,
    medical_history      TEXT,
    lab_tests            TEXT,
    ultrasound           TEXT,
    followup             TEXT,
    western_diagnosis    TEXT,
    tcm_diagnosis        TEXT,
    treatment_principle  TEXT,
    prescription         TEXT,
    acupoints            TEXT,
    assisted_reproduction TEXT,
    western_medicine     TEXT,
    efficacy             TEXT,
    adverse_reactions    TEXT,
    commentary           TEXT,
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  med_case                         IS 'Medical case records extracted from PDF by LLM';
COMMENT ON COLUMN med_case.file_uuid               IS 'Foreign key linking to core_file';
COMMENT ON COLUMN med_case.age                     IS '年齡';
COMMENT ON COLUMN med_case.bmi                     IS 'BMI';
COMMENT ON COLUMN med_case.menstruation            IS '月经情况';
COMMENT ON COLUMN med_case.infertility             IS '不孕情况';
COMMENT ON COLUMN med_case.lifestyle               IS '生活习惯';
COMMENT ON COLUMN med_case.present_symptoms         IS '刻下症';
COMMENT ON COLUMN med_case.medical_history         IS '既往病史';
COMMENT ON COLUMN med_case.lab_tests               IS '生化检查';
COMMENT ON COLUMN med_case.ultrasound              IS '超声检查';
COMMENT ON COLUMN med_case.followup                IS '复诊情况';
COMMENT ON COLUMN med_case.western_diagnosis       IS '西医病名诊断';
COMMENT ON COLUMN med_case.tcm_diagnosis           IS '中医证候诊断';
COMMENT ON COLUMN med_case.treatment_principle     IS '治法';
COMMENT ON COLUMN med_case.prescription            IS '方剂';
COMMENT ON COLUMN med_case.acupoints               IS '针刺选穴';
COMMENT ON COLUMN med_case.assisted_reproduction   IS '辅助生殖技术';
COMMENT ON COLUMN med_case.western_medicine        IS '西药';
COMMENT ON COLUMN med_case.efficacy                IS '疔效评价';
COMMENT ON COLUMN med_case.adverse_reactions       IS '不良反应';
COMMENT ON COLUMN med_case.commentary              IS '按语/评价说明';

CREATE INDEX IF NOT EXISTS idx_med_case_file_uuid ON med_case (file_uuid);
CREATE INDEX IF NOT EXISTS idx_med_case_created_at ON med_case (created_at DESC);
