export type ResearchSteps =
  | "GENERATE_QUESTIONS"
  | "GENERATE_PLAN"
  | "FETCH_DATA"
  | "GENERATE_REPORT"
  | "DONE";

export interface ResearchPayload {
  topic: string;

  questions?: string;
  plan?: string;

  data?: Array<{
    planSection: string;
    research: string;
  }>;

  fetchIndex?: number;
}