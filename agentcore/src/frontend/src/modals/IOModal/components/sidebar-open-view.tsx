import ShadTooltip from "@/components/common/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { useVoiceStore } from "@/stores/voiceStore";
import IconComponent from "../../../components/common/genericIconComponent";
import type { SidebarOpenViewProps } from "../types/sidebar-open-view";
import SessionSelector from "./IOFieldView/components/session-selector";

export const SidebarOpenView = ({
  sessions,
  setSelectedViewField,
  setvisibleSession,
  handleDeleteSession,
  visibleSession,
  selectedViewField,
  playgroundPage,
  setActiveSession,
}: SidebarOpenViewProps) => {
  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );

  const setNewChatOnPlayground = useFlowStore(
    (state) => state.setNewChatOnPlayground,
  );

  return (
    <div className="flex flex-col gap-1">
      {/* New chat button — Gemini style rounded pill */}
      <button
        data-testid="new-chat"
        onClick={() => {
          setvisibleSession(undefined);
          setSelectedViewField(undefined);
          setNewSessionCloseVoiceAssistant(true);
          setNewChatOnPlayground(true);
        }}
        className="mb-3 flex items-center gap-3 rounded-full border border-[#dadce0] dark:border-[#3c4043] px-5 py-3 text-sm font-medium text-[#1f1f1f] dark:text-[#e3e3e3] hover:bg-[#e8eaed] dark:hover:bg-[#2c2d2e] transition-colors w-fit shadow-sm"
      >
        <IconComponent name="Plus" className="h-5 w-5" />
        New chat
      </button>

      {/* Section label */}
      <div className="px-3 py-2 text-xs font-medium text-[#70757a] dark:text-[#9aa0a6]">
        Recent
      </div>

      {/* Session list */}
      <div className="flex flex-col">
        {sessions.map((session, index) => (
          <SessionSelector
            setSelectedView={setSelectedViewField}
            selectedView={selectedViewField}
            key={index}
            session={session}
            playgroundPage={playgroundPage}
            deleteSession={(session) => {
              handleDeleteSession(session);
              if (selectedViewField?.id === session) {
                setSelectedViewField(undefined);
              }
            }}
            updateVisibleSession={(session) => {
              setvisibleSession(session);
            }}
            toggleVisibility={() => {
              setvisibleSession(session);
            }}
            isVisible={visibleSession === session}
            inspectSession={(session) => {
              setSelectedViewField({
                id: session,
                type: "Session",
              });
            }}
            setActiveSession={(session) => {
              setActiveSession(session);
            }}
          />
        ))}
      </div>
    </div>
  );
};