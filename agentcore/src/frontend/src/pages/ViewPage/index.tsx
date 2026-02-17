import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAgentsManagerStore from "../../stores/agentsManagerStore";
import Page from "../AgentBuilderPage/components/PageComponent";

export default function ViewPage() {
  const setCurrentAgent = useAgentsManagerStore((state) => state.setCurrentAgent);

  const { id } = useParams();
  const navigate = useCustomNavigate();

  const agents = useAgentsManagerStore((state) => state.agents);
  const currentAgentId = useAgentsManagerStore((state) => state.currentAgentId);

  // Set agent tab id
  useEffect(() => {
    const awaitgetTypes = async () => {
      if (agents && currentAgentId === "") {
        const isAnExistingAgent = agents.find((agent) => agent.id === id);

        if (!isAnExistingAgent) {
          navigate("/all");
          return;
        }

        setCurrentAgent(isAnExistingAgent);
      }
    };
    awaitgetTypes();
  }, [id, agents]);

  return (
    <div className="agent-page-positioning">
      <Page view />
    </div>
  );
}
