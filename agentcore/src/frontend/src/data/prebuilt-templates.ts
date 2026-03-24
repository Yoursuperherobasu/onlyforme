import type { AgentType } from "@/types/agent";
import customerSupport from "./templates/customer-support-bot.json";
import researchAssistant from "./templates/research-assistant.json";
import codeReview from "./templates/code-review-agent.json";
import emailDrafter from "./templates/email-drafter.json";
import dataAnalyst from "./templates/data-analyst.json";
import taskAutomator from "./templates/task-automator.json";
import contentWriter from "./templates/content-writer.json";
import sqlAgent from "./templates/sql-agent.json";

export const PREBUILT_TEMPLATES: AgentType[] = [
  customerSupport,
  researchAssistant,
  codeReview,
  emailDrafter,
  dataAnalyst,
  taskAutomator,
  contentWriter,
  sqlAgent,
] as unknown as AgentType[];
