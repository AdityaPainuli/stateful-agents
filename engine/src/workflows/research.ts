import { AgentEngine } from "../agent.runner";
import { askLLM } from "../llm";
import { ResearchPayload, ResearchSteps } from "../types/research.types";

export const ResearchAgent = new AgentEngine<ResearchSteps, ResearchPayload>();

/**
 * Step 1 → Generate Research Questions
 */
ResearchAgent.registerStep("GENERATE_QUESTIONS", async (state) => {
  const topic = state.payload!.topic;

  const questions = await askLLM(`
    You are a research assistant.
    Generate 5 deep research questions about:
    "${topic}"
  `);

  return {
    ...state,
    payload: { ...state.payload, questions },
    step: "GENERATE_PLAN",
  };
});

/**
 * Step 2 → Create a Research Plan Based on Those Questions
 */
ResearchAgent.registerStep("GENERATE_PLAN", async (state) => {
  const { questions } = state.payload!;

  const plan = await askLLM(`
    Based on these research questions:
    ${questions}

    Create a structured 5-part research plan.
  `);

  return {
    ...state,
    payload: { ...state.payload, plan },
    step: "FETCH_DATA",
  };
});

/**
 * Step 3 → Fetch External Data for Each Part of the Plan
 * We break this step into substeps for crash-safe continuation.
 */
ResearchAgent.registerStep("FETCH_DATA", async (state) => {
  const { plan } = state.payload!;
  const planParts: string[] = plan?.split("\n").filter((p:any) => p.trim() !== "") ?? [];

  let index = state.payload!.fetchIndex ?? 0;

  if (!state.payload!.data) {
    state.payload!.data = [];
  }

  // process one part per execution cycle
  const part = planParts[index];

  const data = await askLLM(`
    Find factual information about:
    "${part}"
    Cite sources and give summaries.
  `);

  state.payload!.data.push({
    planSection: part!,
    research: data,
  });

  index++;
  state.payload!.fetchIndex = index;

  if (index >= planParts.length) {
    return { ...state, step: "GENERATE_REPORT" };
  }

  return state; // continue in FETCH_DATA
});

/**
 * Step 4 → Generate Final Report
 */
ResearchAgent.registerStep("GENERATE_REPORT", async (state) => {
  const { questions, plan, data } = state.payload!;

  const report = await askLLM(`
    Create a full research report combining:
    - Questions
    - Plan
    - Factual data

    Format it professionally with sections.
  `);

  return {
    ...state,
    payload: { ...state.payload, report },
    step: "DONE",
  };
});
