import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import type { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the widget code for the API
 * @param {string} agent - The current agent.
 * @returns {string} - The widget code
 */
export default function getWidgetCode({
  agentId,
  agentName,
  isAuth: _isAuth,
  copy = false,
}: GetCodeType): string {
  const { protocol, host } = customGetHostProtocol();

  const source = copy
    ? `<script
  src="${protocol}//${host}/widget/agentcore-chat.js">
</script>`
    : `<script
  src="${protocol}//${host}/widget/agentcore-chat.js">
</script>`;

  return `${source}
  <agentcore-chat
    window_title="${agentName}"
    agent_id="${agentId}"
    host_url="${protocol}//${host}"
    api_key="YOUR_AGENTCORE_API_KEY">
</agentcore-chat>`;
}
