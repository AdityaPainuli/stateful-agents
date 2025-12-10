export const log = {
    step: (msg: string) => console.log(`🔹 [STEP] ${msg}`),
    llmPrompt: (msg: string) => console.log(`🟦 [LLM Prompt] ${msg}`),
    llmResponse: (msg: string) => console.log(`🟩 [LLM Response] ${msg}`),
    state: (msg: string, state: any) =>
      console.log(`📦 [STATE] ${msg}:`, JSON.stringify(state, null, 2)),
    save: () => console.log(`💾 State saved to Redis`),
    resume: (step: string) =>
      console.log(`🔁 Resuming workflow at step: ${step}`),
    error: (msg: string) => console.log(`❌ [ERROR] ${msg}`),
  };
  
  