/** SPEC "Moderation and community rules": shown in the composer and on /guidelines. */
export const COMMUNITY_RULES = [
  "Talk about the course and the teaching, not anyone's private life.",
  "No names of other students.",
  "No claims of misconduct. Report those to the University instead.",
  "No slurs or harassment.",
] as const;

/** Reasons offered in the report dialog. */
export const REPORT_REASONS = [
  "Personal attack or harassment",
  "Names or identifies a student",
  "Claim of misconduct",
  "Spam or off topic",
  "Something else",
] as const;

export const GRADE_BUCKETS = ["A-range", "B-range", "C or lower", "P/F", "prefer not to say"] as const;

export const RATING_FIELDS = [
  { key: "overall", label: "Overall", low: "Poor", high: "Excellent" },
  { key: "difficulty", label: "Difficulty", low: "Easy", high: "Very hard" },
  { key: "intellectual_intensity", label: "Intellectual intensity", low: "Light", high: "Intense" },
] as const;
