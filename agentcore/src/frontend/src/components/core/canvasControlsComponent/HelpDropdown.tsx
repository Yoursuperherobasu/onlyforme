import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HelpDropdownView } from "@/components/core/canvasControlsComponent/HelpDropdownView";
import {
  BUG_REPORT_URL,
  DATASTAX_DOCS_URL,
  DESKTOP_URL,
  DOCS_URL,
} from "@/constants/constants";
import { ENABLE_DATASTAX_AGENTCORE } from "@/customization/feature-flags";
import useAgentStore from "@/stores/agentStore";

const HelpDropdown = () => {
  const navigate = useNavigate();
  const [isHelpMenuOpen, setIsHelpMenuOpen] = useState(false);
  const helperLineEnabled = useAgentStore((state) => state.helperLineEnabled);
  const setHelperLineEnabled = useAgentStore(
    (state) => state.setHelperLineEnabled,
  );

  const onToggleHelperLines = useCallback(() => {
    setHelperLineEnabled(!helperLineEnabled);
  }, [helperLineEnabled]);

  const docsUrl = ENABLE_DATASTAX_AGENTCORE ? DATASTAX_DOCS_URL : DOCS_URL;

  return (
    <HelpDropdownView
      isOpen={isHelpMenuOpen}
      onOpenChange={setIsHelpMenuOpen}
      helperLineEnabled={helperLineEnabled}
      onToggleHelperLines={onToggleHelperLines}
      navigateTo={(path) => navigate(path)}
      openLink={(url) => window.open(url, "_blank")}
      urls={{ docs: docsUrl, bugReport: BUG_REPORT_URL, desktop: DESKTOP_URL }}
    />
  );
};

export default HelpDropdown;
