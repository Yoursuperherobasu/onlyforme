import Convert from "ansi-to-html";
import { useEffect, useRef, useState } from "react";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomMarkdownField } from "@/customization/components/custom-markdown-field";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_AGENTCORE } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import Robot from "../../../../../assets/robot.png";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../components/common/genericIconComponent";
import SanitizedHTMLWrapper from "../../../../../components/common/sanitizedHTMLWrapper";
import { EMPTY_INPUT_SEND_MESSAGE } from "../../../../../constants/constants";
import useAlertStore from "../../../../../stores/alertStore";
import type { chatMessagePropsType } from "../../../../../types/components";
import { cn } from "../../../../../utils/utils";
import { ErrorView } from "./components/content-view";
import EditMessageField from "./components/edit-message-field";
import FileCardWrapper from "./components/file-card-wrapper";
import { EditMessageButton } from "./components/message-options";
import { convertFiles } from "./helpers/convert-files";

export default function ChatMessage({
  chat,
  lastMessage,
  updateChat,
  closeChat,
  playgroundPage,
}: chatMessagePropsType): JSX.Element {
  const convert = new Convert({ newline: true });
  const [hidden, setHidden] = useState(true);
  const [streamUrl, setStreamUrl] = useState(chat.stream_url);
  const flow_id = useFlowsManagerStore((state) => state.currentFlowId);
  const fitViewNode = useFlowStore((state) => state.fitViewNode);
  const [chatMessage, setChatMessage] = useState(
    chat.message ? chat.message.toString() : "",
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSource = useRef<EventSource | undefined>(undefined);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const chatMessageRef = useRef(chatMessage);
  const [editMessage, setEditMessage] = useState(false);
  const [showError, setShowError] = useState(false);
  const isBuilding = useFlowStore((state) => state.isBuilding);

  const isAudioMessage = chat.category === "audio";

  useEffect(() => {
    const chatMessageString = chat.message ? chat.message.toString() : "";
    setChatMessage(chatMessageString);
    chatMessageRef.current = chatMessage;
  }, [chat, isBuilding]);

  const streamChunks = (url: string) => {
    setIsStreaming(true);
    return new Promise<boolean>((resolve, reject) => {
      eventSource.current = new EventSource(url);
      eventSource.current.onmessage = (event) => {
        const parsedData = JSON.parse(event.data);
        if (parsedData.chunk) {
          setChatMessage((prev) => prev + parsedData.chunk);
        }
      };
      eventSource.current.onerror = (event: any) => {
        setIsStreaming(false);
        eventSource.current?.close();
        setStreamUrl(undefined);
        if (JSON.parse(event.data)?.error) {
          setErrorData({
            title: "Error on Streaming",
            list: [JSON.parse(event.data)?.error],
          });
        }
        updateChat(chat, chatMessageRef.current);
        reject(new Error("Streaming failed"));
      };
      eventSource.current.addEventListener("close", (event) => {
        setStreamUrl(undefined);
        eventSource.current?.close();
        setIsStreaming(false);
        resolve(true);
      });
    });
  };

  useEffect(() => {
    if (streamUrl && !isStreaming) {
      streamChunks(streamUrl)
        .then(() => {
          if (updateChat) updateChat(chat, chatMessageRef.current);
        })
        .catch((error) => console.error(error));
    }
  }, [streamUrl, chatMessage]);

  useEffect(() => {
    return () => {
      eventSource.current?.close();
    };
  }, []);

  useEffect(() => {
    if (chat.category === "error") {
      const timer = setTimeout(() => setShowError(true), 50);
      return () => clearTimeout(timer);
    }
  }, [chat.category]);

  let decodedMessage = chatMessage ?? "";
  try {
    decodedMessage = decodeURIComponent(chatMessage);
  } catch (_e) {}
  const isEmpty = decodedMessage?.trim() === "";
  const { mutate: updateMessageMutation } = useUpdateMessage();

  const handleEditMessage = (message: string) => {
    updateMessageMutation(
      {
        message: {
          id: chat.id,
          files: convertFiles(chat.files),
          sender_name: chat.sender_name ?? "AI",
          text: message,
          sender: chat.isSend ? "User" : "Machine",
          flow_id,
          session_id: chat.session ?? "",
        },
        refetch: true,
      },
      {
        onSuccess: () => {
          updateChat(chat, message);
          setEditMessage(false);
        },
        onError: () => {
          setErrorData({ title: "Error updating messages." });
        },
      },
    );
  };

  const handleEvaluateAnswer = (evaluation: boolean | null) => {
    updateMessageMutation(
      {
        message: {
          ...chat,
          files: convertFiles(chat.files),
          sender_name: chat.sender_name ?? "AI",
          text: chat.message.toString(),
          sender: chat.isSend ? "User" : "Machine",
          flow_id,
          session_id: chat.session ?? "",
          properties: {
            ...chat.properties,
            positive_feedback: evaluation,
          },
        },
        refetch: true,
      },
      {
        onError: () => {
          setErrorData({ title: "Error updating messages." });
        },
      },
    );
  };

  const editedFlag = chat.edit ? (
    <span className="ml-2 text-xs text-[#9aa0a6]">(Edited)</span>
  ) : null;

  if (chat.category === "error") {
    const blocks = chat.content_blocks ?? [];
    return (
      <ErrorView
        blocks={blocks}
        showError={showError}
        lastMessage={lastMessage}
        closeChat={closeChat}
        fitViewNode={fitViewNode}
        chat={chat}
      />
    );
  }

  return (
    <>
      <div className="w-full py-5 word-break-break-word">
        <div
          className={cn(
            "group relative flex w-full gap-4 px-2",
            editMessage ? "" : "",
          )}
        >
          {/* Avatar — circular, Gemini style */}
          <div
            className={cn(
              "relative flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-full",
              !chat.isSend
                ? "bg-gradient-to-br from-[#4285f4] via-[#9b72cb] to-[#d96570]"
                : "bg-[#e8eaed] dark:bg-[#3c4043]",
            )}
            style={
              chat.properties?.background_color
                ? { backgroundColor: chat.properties.background_color }
                : {}
            }
          >
            {!chat.isSend ? (
              <div className="flex h-5 w-5 items-center justify-center text-white">
                {chat.properties?.icon ? (
                  chat.properties.icon.match(
                    /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
                  ) ? (
                    <span>{chat.properties.icon}</span>
                  ) : (
                    <ForwardedIconComponent
                      name={chat.properties.icon}
                      className="h-4 w-4"
                    />
                  )
                ) : (
                  <img
                    src={Robot}
                    className="absolute bottom-0 left-0 scale-[60%] brightness-0 invert"
                    alt="robot_image"
                  />
                )}
              </div>
            ) : (
              <div className="flex h-5 w-5 items-center justify-center text-[#5f6368] dark:text-[#c4c7c5]">
                {chat.properties?.icon ? (
                  chat.properties.icon.match(
                    /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
                  ) ? (
                    <div>{chat.properties.icon}</div>
                  ) : (
                    <ForwardedIconComponent
                      name={chat.properties.icon}
                      className="h-4 w-4"
                    />
                  )
                ) : !ENABLE_DATASTAX_AGENTCORE && !playgroundPage ? (
                  <CustomProfileIcon />
                ) : playgroundPage ? (
                  <ForwardedIconComponent name="User" className="h-4 w-4" />
                ) : (
                  <CustomProfileIcon />
                )}
              </div>
            )}
          </div>

          {/* Message body */}
          <div className="flex w-full min-w-0 flex-col gap-1">
            {/* Sender name */}
            <div
              className="flex items-center gap-2 text-sm font-medium text-[#1f1f1f] dark:text-[#e3e3e3]"
              style={
                chat.properties?.text_color
                  ? { color: chat.properties.text_color }
                  : {}
              }
              data-testid={
                "sender_name_" + chat.sender_name?.toLocaleLowerCase()
              }
            >
              <span className="flex items-center gap-2">
                {chat.sender_name}
                {isAudioMessage && (
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#f1f3f4] dark:bg-[#3c4043]">
                    <ForwardedIconComponent
                      name="mic"
                      className="h-3 w-3 text-[#70757a] dark:text-[#9aa0a6]"
                    />
                  </div>
                )}
              </span>
              {chat.properties?.source && !playgroundPage && (
                <span className="text-xs font-normal text-[#9aa0a6]">
                  {chat.properties?.source.source}
                </span>
              )}
            </div>

            {/* Content blocks */}
            {chat.content_blocks && chat.content_blocks.length > 0 && (
              <ContentBlockDisplay
                playgroundPage={playgroundPage}
                contentBlocks={chat.content_blocks}
                isLoading={
                  chat.properties?.state === "partial" &&
                  isBuilding &&
                  lastMessage
                }
                state={chat.properties?.state}
                chatId={chat.id}
              />
            )}

            {/* Message content */}
            {!chat.isSend ? (
              <div className="flex-grow">
                <div>
                  {hidden && chat.thought && chat.thought !== "" && (
                    <div
                      onClick={() => setHidden((prev) => !prev)}
                      className="form-modal-chat-icon-div"
                    >
                      <IconComponent
                        name="MessageSquare"
                        className="form-modal-chat-icon"
                      />
                    </div>
                  )}
                  {chat.thought && chat.thought !== "" && !hidden && (
                    <SanitizedHTMLWrapper
                      className="form-modal-chat-thought"
                      content={convert.toHtml(chat.thought ?? "")}
                      onClick={() => setHidden((prev) => !prev)}
                    />
                  )}
                  {chat.thought && chat.thought !== "" && !hidden && <br />}
                  <div className="flex w-full flex-col">
                    <div
                      className="flex w-full flex-col text-[#1f1f1f] dark:text-[#e3e3e3]"
                      data-testid="div-chat-message"
                    >
                      <div
                        data-testid={
                          "chat-message-" + chat.sender_name + "-" + chatMessage
                        }
                        className="flex w-full flex-col"
                      >
                        {chatMessage === "" && isBuilding && lastMessage ? (
                          <div className="flex items-center gap-1 py-2">
                            <span className="h-2 w-2 rounded-full bg-[#4285f4] animate-pulse" />
                            <span className="h-2 w-2 rounded-full bg-[#9b72cb] animate-pulse [animation-delay:150ms]" />
                            <span className="h-2 w-2 rounded-full bg-[#d96570] animate-pulse [animation-delay:300ms]" />
                          </div>
                        ) : (
                          <div className="min-h-6 w-full text-[15px] leading-relaxed">
                            {editMessage ? (
                              <EditMessageField
                                key={`edit-message-${chat.id}`}
                                message={decodedMessage}
                                onEdit={(message) =>
                                  handleEditMessage(message)
                                }
                                onCancel={() => setEditMessage(false)}
                              />
                            ) : (
                              <CustomMarkdownField
                                isAudioMessage={isAudioMessage}
                                chat={chat}
                                isEmpty={isEmpty}
                                chatMessage={chatMessage}
                                editedFlag={editedFlag}
                              />
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-grow">
                <div className="flex w-full flex-col">
                  {editMessage ? (
                    <EditMessageField
                      key={`edit-message-${chat.id}`}
                      message={decodedMessage}
                      onEdit={(message) => handleEditMessage(message)}
                      onCancel={() => setEditMessage(false)}
                    />
                  ) : (
                    <>
                      <div
                        className={cn(
                          "w-full whitespace-pre-wrap break-words text-[15px] leading-relaxed",
                          isEmpty
                            ? "text-[#9aa0a6]"
                            : "text-[#1f1f1f] dark:text-[#e3e3e3]",
                        )}
                        data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                      >
                        {isEmpty ? EMPTY_INPUT_SEND_MESSAGE : decodedMessage}
                        {editedFlag}
                      </div>
                    </>
                  )}
                  {chat.files && (
                    <div className="my-3 flex flex-col gap-3">
                      {chat.files?.map((file, index) => (
                        <FileCardWrapper key={index} index={index} path={file} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Action buttons — appear on hover, inline below message */}
            {!editMessage && (
              <div className="invisible mt-1 group-hover:visible">
                <EditMessageButton
                  onCopy={() => navigator.clipboard.writeText(chatMessage)}
                  onEdit={
                    playgroundPage ? undefined : () => setEditMessage(true)
                  }
                  className="h-fit"
                  isBotMessage={!chat.isSend}
                  onEvaluate={handleEvaluateAnswer}
                  evaluation={chat.properties?.positive_feedback}
                  isAudioMessage={isAudioMessage}
                />
              </div>
            )}
          </div>
        </div>
      </div>
      <div id={lastMessage ? "last-chat-message" : undefined} />
    </>
  );
}