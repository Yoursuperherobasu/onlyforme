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
  // ─── All state & store hooks (UNCHANGED) ───────────────────────────
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

  const { mutate: deleteSessionFunction } = useDeleteSession();

  const [visibleSession, setvisibleSession] = useState<string | undefined>(
    currentFlowId,
  );
  const PlaygroundTitle = playgroundPage && flowName ? flowName : "Playground";

  // ─── API queries (UNCHANGED) ───────────────────────────────────────
  const {
    data: sessionsFromDb,
    isLoading: sessionsLoading,
    refetch: refetchSessions,
  } = useGetSessionsFromFlowQuery(
    {
      id: currentFlowId,
    },
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
    return () => {
      setIOModalOpen(false);
    };
  }, [open]);

  // ─── Session delete handler (UNCHANGED) ────────────────────────────
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

          if (messageIdsToRemove.length > 0) {
            removeMessages(messageIdsToRemove);
          }

          setSuccessData({
            title: "Session deleted successfully.",
          });
        },
        onError: () => {
          if (visibleSession !== session_id) {
            setvisibleSession(session_id);
          }

          setErrorData({
            title: "Error deleting session.",
          });
        },
      },
    );
  }

  // ─── startView helper (UNCHANGED) ─────────────────────────────────
  function startView() {
    if (!chatInput && !chatOutput) {
      if (filteredInputs.length > 0) {
        return filteredInputs[0];
      } else {
        return filteredOutputs[0];
      }
    } else {
      return undefined;
    }
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
        params: {
          session_id: visibleSession,
        },
      },
      { enabled: open },
    );

  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValue = useUtilityStore((state) => state.setChatValueStore);
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);

  // ─── sendMessage (UNCHANGED) ──────────────────────────────────────
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
          files: files,
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

  // ─── Effects (UNCHANGED) ──────────────────────────────────────────
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
    } else if (visibleSession) {
      setSessionId(visibleSession);
      setCurrentSessionId(visibleSession);
      if (selectedViewField?.type === "Session") {
        setSelectedViewField({
          id: visibleSession,
          type: "Session",
        });
      }
    }
  }, [visibleSession]);

  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves,
  );

  useEffect(() => {
    if (open) {
      setPlaygroundScrollBehaves("instant");
    }
  }, [open]);

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
    setvisibleSession((prev) => {
      if (prev === session) {
        return undefined;
      }
      return session;
    });
  };

  const [hasInitialized, setHasInitialized] = useState(false);
  const prevVisibleSessionRef = useRef<string | undefined>(visibleSession);

  useEffect(() => {
    if (!hasInitialized) {
      setHasInitialized(true);
      prevVisibleSessionRef.current = visibleSession;
      return;
    }
    if (
      open &&
      visibleSession &&
      prevVisibleSessionRef.current !== visibleSession
    ) {
      refetchMessages();
    }

    prevVisibleSessionRef.current = visibleSession;
  }, [visibleSession]);

  // ═══════════════════════════════════════════════════════════════════
  // ═══  REDESIGNED SIDEBAR (visual-only changes)  ═══════════════════
  // ═══════════════════════════════════════════════════════════════════

  const sidebarContent = (
    <div
      className={cn(
        "relative flex h-full w-full flex-col overflow-y-auto custom-scroll",
        "px-3.5 pb-4",
        playgroundPage ? "pt-5" : "pt-4",
      )}
    >
      {/* ── Decorative top accent line ──────────────────────────────── */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      {/* ── Header / Flow Identity Card ─────────────────────────────── */}
      <div className="group relative mb-5 overflow-hidden rounded-2xl border border-border/40 bg-background/80 p-4 shadow-sm backdrop-blur-sm transition-all duration-200 hover:border-border/60 hover:shadow-md dark:bg-background/50">
        {/* Subtle inner glow */}
        <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/[0.04] via-transparent to-primary/[0.02] dark:from-primary/[0.06]" />

        <div className="relative flex items-center gap-3.5">
          {/* Icon container with layered depth */}
          <div className="relative">
            <div
              className={cn(
                "relative z-10 flex shrink-0 items-center justify-center rounded-xl p-2.5",
                "shadow-sm ring-1 ring-black/[0.06] transition-transform duration-200 group-hover:scale-[1.03]",
                "dark:ring-white/[0.08]",
                swatchColors[swatchIndex],
              )}
            >
              <IconComponent
                name={flowIcon ?? "Workflow"}
                className="h-5 w-5"
              />
            </div>
            {/* Soft glow behind icon */}
            <div
              className={cn(
                "absolute -inset-1 -z-0 rounded-xl opacity-20 blur-md",
                swatchColors[swatchIndex],
              )}
            />
          </div>

          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold leading-snug tracking-[-0.01em] text-foreground">
              {PlaygroundTitle}
            </h2>
            <div className="mt-1 flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500/80 shadow-[0_0_4px] shadow-emerald-500/30" />
              <span className="text-[11px] font-medium text-muted-foreground/70">
                Chat Playground
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Sessions Section ─────────────────────────────────────────── */}
      <div className="min-h-0 flex-1">
        {/* Section header with decorative line */}
        <div className="mb-3 flex items-center gap-2.5 px-1">
          <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground/50">
            Sessions
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-border/50 to-transparent" />
          {sessions.length > 0 && (
            <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-muted/80 px-1 text-[10px] font-semibold tabular-nums text-muted-foreground/60">
              {sessions.length}
            </span>
          )}
        </div>

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

      {/* ── Footer / Publish Options ────────────────────────────────── */}
      {showPublishOptions && (
        <div className="relative mt-5 space-y-3.5 pt-4">
          {/* Gradient divider instead of plain border */}
          <div className="absolute inset-x-2 top-0 h-px bg-gradient-to-r from-transparent via-border/60 to-transparent" />

          <div className="flex items-center justify-between px-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground/50">
              Theme
            </span>
            <ThemeButtons />
          </div>

          <Button
            onClick={AgentCoreButtonClick}
            variant="primary"
            className={cn(
              "group/btn relative w-full overflow-hidden !rounded-xl py-2.5",
              "shadow-md transition-all duration-200",
              "hover:shadow-lg hover:brightness-105",
            )}
          >
            {/* Shimmer effect on hover */}
            <div className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-500 group-hover/btn:translate-x-full" />
            <AgentCoreLogoColor />
            <span className="relative ml-1.5 text-[13px] font-medium tracking-[-0.01em]">
              Built with AgentCore
            </span>
          </Button>
        </div>
      )}
    </div>
  );

  // ═══════════════════════════════════════════════════════════════════
  // ═══  RETURN (sidebar container restyled, rest UNCHANGED)  ════════
  // ═══════════════════════════════════════════════════════════════════

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disable}
      type={isPlayground ? "full-screen" : undefined}
      onSubmit={async () => await sendMessage({ repeat: 1 })}
      size="x-large"
      className="!rounded-[12px] p-0"
    >
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
      <BaseModal.Content overflowHidden className="h-full">
        {open && (
          <div className="relative flex h-full w-full bg-background">
            {/* ── Sidebar Container ─────────────────────────────────── */}
            <div
              className={cn(
                "relative flex h-full w-[284px] shrink-0 flex-col",
                "border-r border-border/50",
                // Layered gradient background for depth
                "bg-gradient-to-b from-muted/40 via-muted/20 to-muted/30",
                "dark:from-card/50 dark:via-card/30 dark:to-card/40",
              )}
            >
              {/* Subtle noise texture overlay for richness */}
              <div
                className="pointer-events-none absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
                }}
              />
              {sidebarContent}
            </div>

            {/* ── Main Content (UNCHANGED) ──────────────────────────── */}
            <div className="relative flex h-full min-w-0 flex-1 flex-col bg-background">
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
                sidebarOpen={true}
                currentFlowId={currentFlowId}
                setSidebarOpen={() => {}}
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
        )}
      </BaseModal.Content>
    </BaseModal>
  );
}