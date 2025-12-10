// state.store.ts

import { AgentState } from "../types/agent.types";
import { redis } from "../utils/redis";



export async function saveState(state: AgentState) {
  await redis.set(`agent:${state.agentId}`, JSON.stringify(state));
}

export async function loadState<Payload>(agentId: string): Promise<AgentState<Payload> | null> {
    const json = await redis.get(`agent:${agentId}`);
    return json ? JSON.parse(json) : null;
  }
