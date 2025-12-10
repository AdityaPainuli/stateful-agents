
export interface AgentState<Payload = any> {
    agentId: string;
    step: string;
    payload: Payload;
    messages: any[];
    updatedAt: number;
  }