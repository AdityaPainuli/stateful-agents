// index.ts

import { ResearchAgent } from "./workflows/research";



ResearchAgent.run("agent_research_001", "GENERATE_QUESTIONS", {
  topic: "How LLM agents can automate scientific research",
});
