import { cn } from "@/utils/utils";
import type { ChatViewWrapperProps } from "../types/chat-view-wrapper";
import ChatView from "./chatView/components/chat-view";

export const ChatViewWrapper = ({
  selectedViewField,
  visibleSession,
  sessions,
  sidebarOpen,
  currentFlowId,
  setSidebarOpen,
  isPlayground,
  setvisibleSession,
  setSelectedViewField,
  messagesFetched,
  sessionId,
  sendMessage,
  canvasOpen,
  setOpen,
  playgroundTitle,
  playgroundPage,
}: ChatViewWrapperProps) => {
  return (
    <div
      className={cn(
        "flex h-full w-full flex-col",
        selectedViewField ? "hidden" : "",
      )}
    >
      {/* Session indicator — subtle centered pill */}
      {visibleSession && sessions.length > 0 && (
        <div className="flex justify-center py-2">
          <span className="inline-flex items-center rounded-full bg-[#f1f3f4] dark:bg-[#2c2d2e] px-4 py-1.5 text-xs font-medium text-[#5f6368] dark:text-[#9aa0a6]">
            {visibleSession === currentFlowId
              ? "New Conversation"
              : visibleSession}
          </span>
        </div>
      )}

      {/* Chat area — takes remaining space */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {messagesFetched && (
          <ChatView
            focusChat={sessionId}
            sendMessage={sendMessage}
            visibleSession={visibleSession}
            closeChat={
              !canvasOpen
                ? undefined
                : () => {
                    setOpen(false);
                  }
            }
            playgroundPage={playgroundPage}
            sidebarOpen={sidebarOpen}
          />
        )}
      </div>
    </div>
  );
};