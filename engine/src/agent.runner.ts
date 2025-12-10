import { loadState, saveState } from "./stores/state.store";
import { AgentState } from "./types/agent.types";



export class AgentEngine<
  Steps extends string,
  Payload extends Record<string, any>
> {
  private handlers: Partial<
  Record<Steps, (s: AgentState<Payload>) => Promise<AgentState<Payload>>>
> = {};


  /**
   * Register step handler with type safety
   */
  registerStep(
    step: Steps,
    handler: (s: AgentState<Payload>) => Promise<AgentState<Payload>>
  ) {
    this.handlers[step] = handler;
  }

  /**
   * Fully type-safe run() function
   */
  async run(
    agentId: string,
    initialStep: Steps,
    initialPayload: Payload
  ): Promise<void> {
    let state = await loadState(agentId);

    if (!state) {
      state = {
        agentId,
        step: initialStep,
        payload: initialPayload,
        messages: [],
        updatedAt: Date.now(),
      };
      await saveState(state);
    }

    let currentState: AgentState<any> = state;


    while (currentState.step !== "DONE") {
      const handler = this.handlers[currentState.step as Steps];

      if (!handler) {
        throw new Error(`No handler registered for step: ${state.step}`);
      }

      console.log(`➡ Running step: ${state.step}`);

      state = await handler(currentState);
      state.updatedAt = Date.now();

      await saveState(state);
    }

    console.log("🎉 Workflow complete");
  }
}
