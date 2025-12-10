import OpenAI from "openai";
import "dotenv/config";
import { log } from "./logger";

export const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function askLLM(prompt: string) {
  log.llmPrompt(prompt);

  const res = await client.chat.completions.create({
    model: "gpt-4.1",
    messages: [{ role: "user", content: prompt }],
  });

  const message = res.choices[0]?.message?.content ?? "";

  log.llmResponse(message);

  return message;
}
