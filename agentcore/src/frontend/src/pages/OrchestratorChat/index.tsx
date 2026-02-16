import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, ChevronDown, Plus, MessageSquare, PanelLeftClose, PanelLeft, User } from "lucide-react";

/* ------------------ TYPES ------------------ */

interface Agent {
  id: string;
  name: string;
  description: string;
  online: boolean;
  color: string;
}

interface Message {
  id: string;
  sender: "user" | "agent";
  agentName?: string;
  content: string;
  timestamp: string;
}

/* ------------------ AGENTS ------------------ */

const agents: Agent[] = [
  { id: "1", name: "General Assistant", description: "General purpose AI assistant", online: true, color: "#10a37f" },
  { id: "2", name: "Code Expert", description: "Specialized in coding", online: true, color: "#ab68ff" },
  { id: "3", name: "Data Analyst", description: "Data analysis and insights", online: true, color: "#19c37d" },
  { id: "4", name: "Content Writer", description: "Creative writing", online: true, color: "#ef4146" },
  { id: "5", name: "Business Analyst", description: "Business strategy", online: true, color: "#f5a623" },
  { id: "6", name: "Research Agent", description: "Deep research & synthesis", online: true, color: "#0ea5e9" },
];

/* ------------------ INITIAL CHAT ------------------ */

const initialMessages: Message[] = [
  {
    id: "1",
    sender: "agent",
    agentName: "General Assistant",
    content: "Hello! You can chat with agents by selecting them or typing @ followed by their name.",
    timestamp: "12:39 PM",
  },
  {
    id: "2",
    sender: "user",
    content: "Hi @Research Agent",
    timestamp: "12:40 PM",
  },
];

const chatHistory = [
  { id: "c1", title: "Research on AI trends", date: "Today" },
  { id: "c2", title: "Code review for API", date: "Today" },
  { id: "c3", title: "Q3 Data Analysis", date: "Yesterday" },
  { id: "c4", title: "Blog post draft", date: "Yesterday" },
  { id: "c5", title: "Business strategy meeting", date: "Previous 7 Days" },
];

/* ------------------ COMPONENT ------------------ */

export default function AgentOrchestrator() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>(agents);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedModel, setSelectedModel] = useState("General Assistant");
  const [showModelPicker, setShowModelPicker] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const modelPickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelPickerRef.current && !modelPickerRef.current.contains(e.target as Node)) {
        setShowModelPicker(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /* ------------------ HELPERS ------------------ */

  const timeNow = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const highlightMentions = (text: string) => {
    return text.split(/(@[\w\s]+)/g).map((part, i) =>
      part.startsWith("@") ? (
        <span key={i} className="font-semibold text-primary">
          {part}
        </span>
      ) : (
        part
      )
    );
  };

  const getAgentColor = (name?: string) => {
    const agent = agents.find((a) => a.name === name);
    return agent?.color || "#10a37f";
  };

  /* ------------------ INPUT HANDLING ------------------ */

  const handleInputChange = (value: string) => {
    setInput(value);
    const match = value.match(/@([\w\s]*)$/);
    if (match) {
      const query = match[1].toLowerCase();
      setFilteredAgents(agents.filter((a) => a.name.toLowerCase().includes(query)));
      setShowMentions(true);
    } else {
      setShowMentions(false);
    }
  };

  const handleSelectAgent = (agent: Agent) => {
    const updated = input.replace(/@[\w\s]*$/, `@${agent.name} `);
    setInput(updated);
    setShowMentions(false);
    textareaRef.current?.focus();
  };

  /* ------------------ SEND MESSAGE ------------------ */

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      sender: "user",
      content: input,
      timestamp: timeNow(),
    };

    const mentionedAgent =
      agents.find((a) => input.includes(`@${a.name}`)) ||
      agents.find((a) => a.name === selectedModel) ||
      agents[0];

    const agentReply: Message = {
      id: crypto.randomUUID(),
      sender: "agent",
      agentName: mentionedAgent.name,
      content: `Got it! ${mentionedAgent.name} will handle this.`,
      timestamp: timeNow(),
    };

    setMessages((prev) => [...prev, userMessage, agentReply]);
    setInput("");
    setShowMentions(false);
  };

  /* ---- group chat history by date ---- */
  const grouped = chatHistory.reduce<Record<string, typeof chatHistory>>(
    (acc, c) => {
      if (!acc[c.date]) acc[c.date] = [];
      acc[c.date].push(c);
      return acc;
    },
    {},
  );

  /* ------------------ RENDER ------------------ */

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {/* ================ SIDEBAR ================ */}
      <div
        className={`flex flex-col overflow-hidden border-r border-border bg-muted transition-all duration-200 ${
          sidebarOpen ? "w-64 min-w-[16rem]" : "w-0 min-w-0"
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-3">
          <button
            onClick={() => setSidebarOpen(false)}
            className="flex items-center rounded-md p-1.5 text-muted-foreground hover:bg-accent"
          >
            <PanelLeftClose size={18} />
          </button>
          <button className="flex items-center rounded-md p-1.5 text-muted-foreground hover:bg-accent">
            <Plus size={18} />
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto px-2">
          {Object.entries(grouped).map(([date, chats]) => (
            <div key={date} className="mb-4">
              <div className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {date}
              </div>
              {chats.map((chat) => (
                <button
                  key={chat.id}
                  className="flex w-full items-center gap-2 truncate rounded-lg px-2 py-2.5 text-left text-sm text-foreground hover:bg-accent"
                >
                  <MessageSquare size={14} className="shrink-0 opacity-50" />
                  <span className="truncate">{chat.title}</span>
                </button>
              ))}
            </div>
          ))}
        </div>

        {/* Agents Panel */}
        <div className="border-t border-border px-2 py-3">
          <div className="px-2 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Agents
          </div>
          <div className="flex flex-col gap-0.5">
            {agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => {
                  setSelectedModel(agent.name);
                  setShowModelPicker(false);
                }}
                className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-foreground hover:bg-accent ${
                  selectedModel === agent.name ? "bg-accent" : ""
                }`}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: agent.online ? agent.color : undefined }}
                />
                <span className="truncate">{agent.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ================ MAIN AREA ================ */}
      <div className="relative flex flex-1 flex-col">
        {/* Top Bar */}
        <div className="flex h-[52px] shrink-0 items-center gap-2 border-b border-border px-4">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="flex items-center rounded-md p-1.5 text-muted-foreground hover:bg-accent"
            >
              <PanelLeft size={18} />
            </button>
          )}

          {/* Model selector */}
          <div ref={modelPickerRef} className="relative">
            <button
              onClick={() => setShowModelPicker(!showModelPicker)}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[15px] font-semibold text-foreground hover:bg-accent"
            >
              <Sparkles size={16} style={{ color: getAgentColor(selectedModel) }} />
              {selectedModel}
              <ChevronDown size={14} className="opacity-50" />
            </button>

            {showModelPicker && (
              <div className="absolute left-0 top-full z-50 mt-1 min-w-[240px] rounded-xl border border-border bg-popover p-1 shadow-lg">
                {agents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => {
                      setSelectedModel(agent.name);
                      setShowModelPicker(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm text-foreground hover:bg-accent ${
                      selectedModel === agent.name ? "bg-accent" : ""
                    }`}
                  >
                    <span
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                      style={{ background: agent.color }}
                    >
                      <Sparkles size={14} color="white" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {agent.description}
                      </div>
                    </div>
                    {selectedModel === agent.name && (
                      <span className="ml-auto text-primary">✓</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ================ MESSAGES ================ */}
        <div className="flex flex-1 flex-col items-center overflow-y-auto">
          <div className="w-full max-w-3xl px-6 pb-28 pt-6">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              return (
                <div key={msg.id} className="flex items-start gap-4 py-5">
                  {/* Avatar */}
                  <div
                    className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center ${
                      isUser ? "rounded-full bg-muted" : "rounded-lg"
                    }`}
                    style={!isUser ? { background: getAgentColor(msg.agentName) } : undefined}
                  >
                    {isUser ? (
                      <User size={16} className="text-muted-foreground" />
                    ) : (
                      <Sparkles size={16} color="white" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                      {isUser ? "You" : msg.agentName}
                      <span className="text-xs font-normal text-muted-foreground">
                        {msg.timestamp}
                      </span>
                    </div>
                    <div className="text-[15px] leading-relaxed text-foreground/80">
                      {highlightMentions(msg.content)}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ================ INPUT AREA ================ */}
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex justify-center bg-gradient-to-t from-background from-40% to-transparent px-6 pb-6">
          <div className="pointer-events-auto relative w-full max-w-3xl">
            {/* Mention dropdown */}
            {showMentions && (
              <div className="absolute bottom-full left-0 z-50 mb-2 max-h-64 min-w-[240px] overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg">
                {filteredAgents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => handleSelectAgent(agent)}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm text-foreground hover:bg-accent"
                  >
                    <span
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md"
                      style={{ background: agent.color }}
                    >
                      <Sparkles size={12} color="white" />
                    </span>
                    <div className="min-w-0">
                      <div className="font-medium">@{agent.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {agent.description}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Text Input */}
            <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => handleInputChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Message agents or type @ to mention..."
                rows={1}
                className="w-full resize-none border-none bg-transparent px-5 py-4 pr-14 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0"
              />
              <div className="flex items-center justify-end px-3 pb-3">
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                    input.trim()
                      ? "bg-foreground text-background hover:opacity-90"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  <Send size={16} className="-ml-px -mt-px" />
                </button>
              </div>
            </div>

            <div className="mt-2 text-center text-xs text-muted-foreground">
              Agents can make mistakes. Review important info.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}