import { useCallback, useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import ThemeButtons from "@/components/core/appHeaderComponent/components/ThemeButtons";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { AgentCoreButtonRedirectTarget } from "@/customization/utils/urls";
import { useUtilityStore } from "@/stores/utilityStore";
import { swatchColors } from "@/utils/styleUtils";
import AgentCoreLogoColor from "../../assets/motherson_name.svg";
import IconComponent from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useMessagesStore } from "../../stores/messagesStore";
import type { IOModalPropsType } from "../../types/components";
import { cn, getNumberFromString } from "../../utils/utils";
import BaseModal from "../baseModal";
import { ChatViewWrapper } from "./components/chat-view-wrapper";
import { createNewSessionName } from "./components/chatView/chatInput/components/voice-assistant/helpers/create-new-session-name";
import { SelectedViewField } from "./components/selected-view-field";
import { SidebarOpenView } from "./components/sidebar-open-view";
import { useGetFlowId } from "./hooks/useGetFlowId";

export default function IOModal({
  children,
  open,
  setOpen,
  disable,
  isPlayground,
  canvasOpen,
  playgroundPage,
}: IOModalPropsType): JSX.Element {
  const setIOModalOpen = useFlowsManagerStore((state) => state.setIOModalOpen);
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const nodes = useFlowStore((state) => state.nodes);
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const newChatOnPlayground = useFlowStore(
    (state) => state.newChatOnPlayground,
  );
  const setNewChatOnPlayground = useFlowStore(
    (state) => state.setNewChatOnPlayground,
  );

  const { flowIcon, flowId, flowGradient, flowName } = useFlowStore(
    useShallow((state) => ({
      flowIcon: state.currentFlow?.icon,
      flowId: state.currentFlow?.id,
      flowGradient: state.currentFlow?.gradient,
      flowName: state.currentFlow?.name,
    })),
  );
  const filteredInputs = inputs.filter((input) => input.type !== "ChatInput");
  const chatInput = inputs.find((input) => input.type === "ChatInput");
  const filteredOutputs = outputs.filter(
    (output) => output.type !== "ChatOutput",
  );
  const chatOutput = outputs.find((output) => output.type === "ChatOutput");
  const filteredNodes = nodes.filter(
    (node) =>
      inputs.some((input) => input.id === node.id) ||
      filteredOutputs.some((output) => output.id === node.id),
  );
  const haveChat = chatInput || chatOutput;
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const currentFlowId = useGetFlowId();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { mutate: deleteSessionFunction } = useDeleteSession();

  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const PlaygroundTitle = playgroundPage && flowName ? flowName : "Playground";

  const {
    data: sessionsFromDb,
    isLoading: sessionsLoading,
    refetch: refetchSessions,
  } = useGetSessionsFromFlowQuery(
    { id: currentFlowId },
    { enabled: open },
  );

  useEffect(() => {
    if (sessionsFromDb && !sessionsLoading) {
      const sessions = [...sessionsFromDb.sessions];
      if (!sessions.includes(currentFlowId)) {
        sessions.unshift(currentFlowId);
      }
      setSessions(sessions);
    }
  }, [sessionsFromDb, sessionsLoading, currentFlowId]);

  useEffect(() => {
    setIOModalOpen(open);
    return () => setIOModalOpen(false);
  }, [open]);

  function handleDeleteSession(session_id: string) {
    if (visibleSession === session_id) {
      const remainingSessions = sessions.filter((s) => s !== session_id);
      if (remainingSessions.length > 0) {
        setvisibleSession(remainingSessions[0]);
      } else {
        setvisibleSession(currentFlowId);
      }
    }
    deleteSessionFunction(
      { sessionId: session_id },
      {
        onSuccess: () => {
          deleteSession(session_id);
          const messageIdsToRemove = messages
            .filter((msg) => msg.session_id === session_id)
            .map((msg) => msg.id);
          if (messageIdsToRemove.length > 0) removeMessages(messageIdsToRemove);
          setSuccessData({ title: "Session deleted successfully." });
        },
        onError: () => {
          if (visibleSession !== session_id) setvisibleSession(session_id);
          setErrorData({ title: "Error deleting session." });
        },
      },
    );
  }

  function startView() {
    if (!chatInput && !chatOutput) {
      return filteredInputs.length > 0 ? filteredInputs[0] : filteredOutputs[0];
    }
    return undefined;
  }

  const [selectedViewField, setSelectedViewField] = useState<
    { type: string; id: string } | undefined
  >(startView());

  const messages = useMessagesStore((state) => state.messages);
  const removeMessages = useMessagesStore((state) => state.removeMessages);
  const [sessions, setSessions] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>(currentFlowId);
  const setCurrentSessionId = useUtilityStore(
    (state) => state.setCurrentSessionId,
  );

  const { isFetched: messagesFetched, refetch: refetchMessages } =
    useGetMessagesQuery(
      {
        mode: "union",
        id: currentFlowId,
        params: { session_id: visibleSession },
      },
      { enabled: open },
    );

  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValue = useUtilityStore((state) => state.setChatValueStore);
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);

  const sendMessage = useCallback(
    async ({
      repeat = 1,
      files,
    }: {
      repeat: number;
      files?: string[];
    }): Promise<void> => {
      if (isBuilding) return;
      setChatValue("");
      for (let i = 0; i < repeat; i++) {
        await buildFlow({
          input_value: chatValue,
          startNodeId: chatInput?.id,
          files,
          silent: true,
          session: sessionId,
          eventDelivery: eventDeliveryConfig,
        }).catch((err) => {
          console.error(err);
          throw err;
        });
      }
    },
    [isBuilding, setIsBuilding, chatValue, chatInput?.id, sessionId, buildFlow],
  );

  useEffect(() => {
    if (playgroundPage && messages.length > 0) {
      window.sessionStorage.setItem(currentFlowId, JSON.stringify(messages));
    }
    if (newChatOnPlayground && !sessionsLoading) {
      const handleRefetchAndSetSession = async () => {
        try {
          const result = await refetchSessions();
          if (result.data?.sessions && result.data.sessions.length > 0) {
            setvisibleSession(
              result.data.sessions[result.data.sessions.length - 1],
            );
          }
        } catch (error) {
          console.error("Error refetching sessions:", error);
        }
      };
      handleRefetchAndSetSession();
      setNewChatOnPlayground(false);
    }
  }, [messages, playgroundPage]);

  useEffect(() => {
    if (!visibleSession) {
      setSessionId(createNewSessionName());
      setCurrentSessionId(currentFlowId);
    } else {
      setSessionId(visibleSession);
      setCurrentSessionId(visibleSession);
      if (selectedViewField?.type === "Session") {
        setSelectedViewField({ id: visibleSession, type: "Session" });
      }
    }
  }, [visibleSession]);

  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves,
  );

  useEffect(() => {
    if (open) setPlaygroundScrollBehaves("instant");
  }, [open]);

  useEffect(() => {
    const handleResize = () => setSidebarOpen(window.innerWidth >= 1024);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const showPublishOptions = playgroundPage && ENABLE_PUBLISH;

  const AgentCoreButtonClick = () => {
    track("AgentCoreButtonClick");
    customOpenNewTab(AgentCoreButtonRedirectTarget());
  };

  const swatchIndex =
    (flowGradient && !isNaN(parseInt(flowGradient))
      ? parseInt(flowGradient)
      : getNumberFromString(flowGradient ?? flowId ?? "")) %
    swatchColors.length;

  const setActiveSession = (session: string) => {
    setvisibleSession((prev) => (prev === session ? undefined : session));
  };

  const [hasInitialized, setHasInitialized] = useState(false);
  const prevVisibleSessionRef = useRef<string | undefined>(visibleSession);

  useEffect(() => {
    if (!hasInitialized) {
      setHasInitialized(true);
      prevVisibleSessionRef.current = visibleSession;
      return;
    }
    if (open && visibleSession && prevVisibleSessionRef.current !== visibleSession) {
      refetchMessages();
    }
    prevVisibleSessionRef.current = visibleSession;
  }, [visibleSession]);

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      onSubmit={async () => await sendMessage({ repeat: 1 })}
      size="x-large"
      className="!rounded-none !border-0 p-0 overflow-hidden lg:!rounded-[24px]"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content overflowHidden className="h-full">
        {open && (
          <div className="io-shell relative flex h-full w-full bg-white dark:bg-[#131314]">
            {/* ── Scrim ── */}
            <div
              className={cn(
                "fixed inset-0 z-[60] bg-black/20 backdrop-blur-[1px] transition-opacity duration-200 lg:hidden",
                sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none",
              )}
              onClick={() => setSidebarOpen(false)}
            />

            {/* ── Drawer ── */}
            <aside
              className={cn(
                "fixed inset-y-0 left-0 z-[70] flex w-[300px] flex-col",
                "bg-[#f8f9fa] dark:bg-[#1e1f20]",
                "transition-transform duration-300 ease-[cubic-bezier(.4,0,.2,1)]",
                "lg:static lg:z-auto",
                sidebarOpen ? "translate-x-0" : "-translate-x-full lg:-translate-x-full",
              )}
            >
              {/* Drawer header */}
              <div className="flex h-[60px] items-center justify-between px-4">
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="flex h-10 w-10 items-center justify-center rounded-full text-[#444746] hover:bg-[#e8eaed] dark:text-[#c4c7c5] dark:hover:bg-[#2c2d2e] transition-colors"
                >
                  <IconComponent name="Menu" className="h-5 w-5" />
                </button>
                <ShadTooltip styleClasses="z-[80]" content="New chat">
                  <button
                    onClick={() => {
                      setvisibleSession(undefined);
                      setSelectedViewField(undefined);
                    }}
                    className="flex h-10 w-10 items-center justify-center rounded-full text-[#444746] hover:bg-[#e8eaed] dark:text-[#c4c7c5] dark:hover:bg-[#2c2d2e] transition-colors"
                  >
                    <IconComponent name="SquarePen" className="h-5 w-5" />
                  </button>
                </ShadTooltip>
              </div>

              {/* Sessions */}
              <div className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-1 custom-scroll">
                {!sessionsLoading && (
                  <SidebarOpenView
                    sessions={sessions}
                    setSelectedViewField={setSelectedViewField}
                    setvisibleSession={setvisibleSession}
                    handleDeleteSession={handleDeleteSession}
                    visibleSession={visibleSession}
                    selectedViewField={selectedViewField}
                    playgroundPage={!!playgroundPage}
                    setActiveSession={setActiveSession}
                  />
                )}
              </div>

              {/* Drawer footer */}
              <div className="px-4 py-3">
                {showPublishOptions && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#70757a] dark:text-[#9aa0a6]">Theme</span>
                      <ThemeButtons />
                    </div>
                    <button
                      onClick={AgentCoreButtonClick}
                      className="flex w-full items-center justify-center gap-2 rounded-full border border-[#dadce0] dark:border-[#3c4043] py-2.5 text-sm font-medium text-[#1f1f1f] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#2c2d2e] transition-colors"
                    >
                      <AgentCoreLogoColor className="h-4 w-4" />
                      Built with AgentCore
                    </button>
                  </div>
                )}
              </div>
            </aside>

            {/* ── Main area ── */}
            <div className="flex h-full min-w-0 flex-1 flex-col">
              {/* Top bar */}
              <header className="flex h-[60px] flex-shrink-0 items-center justify-between px-4 lg:px-6">
                <div className="flex items-center gap-2">
                  {!sidebarOpen && (
                    <>
                      <button
                        onClick={() => setSidebarOpen(true)}
                        className="flex h-10 w-10 items-center justify-center rounded-full text-[#444746] hover:bg-[#f1f3f4] dark:text-[#c4c7c5] dark:hover:bg-[#2c2d2e] transition-colors"
                      >
                        <IconComponent name="Menu" className="h-5 w-5" />
                      </button>
                      <ShadTooltip styleClasses="z-50" content="New chat">
                        <button
                          onClick={() => {
                            setvisibleSession(undefined);
                            setSelectedViewField(undefined);
                          }}
                          className="flex h-10 w-10 items-center justify-center rounded-full text-[#444746] hover:bg-[#f1f3f4] dark:text-[#c4c7c5] dark:hover:bg-[#2c2d2e] transition-colors"
                        >
                          <IconComponent name="SquarePen" className="h-5 w-5" />
                        </button>
                      </ShadTooltip>
                    </>
                  )}
                  <div className="flex items-center gap-2 ml-1">
                    <div
                      className={cn(
  "flex h-8 w-8 items-center justify-center rounded-full bg-[#DA2128]"
)}
                    >
                      <IconComponent
                        name={ "MessageCircle"}
                        className="h-4 w-4 text-white"
                      />
                    </div>
                    <span className="text-lg font-normal text-[#1f1f1f] dark:text-[#e3e3e3]">
                      {PlaygroundTitle}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  {!showPublishOptions }
                  {showPublishOptions && !sidebarOpen && (
                    <button
                      onClick={AgentCoreButtonClick}
                      className="flex items-center gap-1.5 rounded-full border border-[#dadce0] dark:border-[#3c4043] px-4 py-2 text-sm font-medium text-[#1f1f1f] dark:text-[#e3e3e3] hover:bg-[#f1f3f4] dark:hover:bg-[#2c2d2e] transition-colors"
                    >
                      <AgentCoreLogoColor className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">AgentCore</span>
                    </button>
                  )}
                </div>
              </header>

              {/* Content */}
              <div className="flex h-full min-h-0 flex-1 overflow-hidden">
                {selectedViewField && !sessionsLoading && (
                  <SelectedViewField
                    selectedViewField={selectedViewField}
                    setSelectedViewField={setSelectedViewField}
                    haveChat={haveChat}
                    inputs={filteredInputs}
                    outputs={filteredOutputs}
                    sessions={sessions}
                    currentFlowId={currentFlowId}
                    nodes={filteredNodes}
                  />
                )}
                <ChatViewWrapper
                  playgroundPage={playgroundPage}
                  selectedViewField={selectedViewField}
                  visibleSession={visibleSession}
                  sessions={sessions}
                  sidebarOpen={sidebarOpen}
                  currentFlowId={currentFlowId}
                  setSidebarOpen={setSidebarOpen}
                  isPlayground={isPlayground}
                  setvisibleSession={setvisibleSession}
                  setSelectedViewField={setSelectedViewField}
                  haveChat={haveChat}
                  messagesFetched={messagesFetched}
                  sessionId={sessionId}
                  sendMessage={sendMessage}
                  canvasOpen={canvasOpen}
                  setOpen={setOpen}
                  playgroundTitle={PlaygroundTitle}
                />
              </div>
            </div>
          </div>
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}