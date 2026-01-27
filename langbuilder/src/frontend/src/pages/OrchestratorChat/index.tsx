import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";

interface Agent {
  id: string;
  name: string;
  description: string;
  online: boolean;
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
  {
    id: "1",
    name: "General Assistant",
    description: "General purpose AI assistant",
    online: true,
  },
  {
    id: "2",
    name: "Code Expert",
    description: "Specialized in coding",
    online: true,
  },
  {
    id: "3",
    name: "Data Analyst",
    description: "Data analysis and insights",
    online: true,
  },
  {
    id: "4",
    name: "Content Writer",
    description: "Creative writing",
    online: true,
  },
  {
    id: "5",
    name: "Business Analyst",
    description: "Business strategy",
    online: true,
  },
  {
    id: "6",
    name: "Research Agent",
    description: "Deep research & synthesis",
    online: true,
  },
];

/* ------------------ INITIAL CHAT ------------------ */

const initialMessages: Message[] = [
  {
    id: "1",
    sender: "agent",
    agentName: "General Assistant",
    content:
      "Hello! You can chat with agents by selecting them or typing @ followed by their name.",
    timestamp: "12:39 PM",
  },
  {
    id: "2",
    sender: "user",
    content: "Hi @Research Agent",
    timestamp: "12:40 PM",
  },
];

/* ------------------ COMPONENT ------------------ */

export default function AgentOrchestrator() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>(agents);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* ------------------ HELPERS ------------------ */

  const timeNow = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const highlightMentions = (text: string) => {
    return text.split(/(@[\w\s]+)/g).map((part, i) =>
      part.startsWith("@") ? (
        <span
          key={i}
          className="rounded bg-blue-600/20 px-1 text-blue-400"
        >
          {part}
        </span>
      ) : (
        part
      ),
    );
  };

  /* ------------------ INPUT HANDLING ------------------ */

  const handleInputChange = (value: string) => {
    setInput(value);

    const match = value.match(/@([\w\s]*)$/);
    if (match) {
      const query = match[1].toLowerCase();
      setFilteredAgents(
        agents.filter((a) =>
          a.name.toLowerCase().includes(query),
        ),
      );
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
      agents.find((a) => input.includes(`@${a.name}`)) || agents[0];

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

  /* ------------------ UI ------------------ */

  return (
    <div className="flex h-screen w-full bg-background">
      {/* ---------------- SIDEBAR ---------------- */}
      <div className="w-64 border-r bg-card p-4">
        <h2 className="mb-3 font-semibold">Available Agents</h2>
        <div className="space-y-1">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="rounded-md p-2 hover:bg-accent"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{agent.name}</span>
                {agent.online && (
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {agent.description}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ---------------- CHAT ---------------- */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => {
            const isUser = msg.sender === "user";

            return (
              <div
                key={msg.id}
                className={`flex ${isUser ? "justify-start" : "justify-end"}`}
              >
                <div className="max-w-[70%]">
                  <div className="mb-1 text-xs text-muted-foreground">
                    {isUser ? "You" : msg.agentName} · {msg.timestamp}
                  </div>
                  <div
                    className={`inline-block rounded-lg px-4 py-3 text-sm ${
                      isUser
                        ? "bg-muted text-foreground"
                        : "bg-blue-600 text-white"
                    }`}
                  >
                    {highlightMentions(msg.content)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Input */}
        <div className="relative border-t bg-card p-4">
          {/* Mention dropdown */}
          {showMentions && (
            <div className="absolute bottom-16 left-4 z-50 w-64 rounded-md border bg-popover shadow">
              {filteredAgents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => handleSelectAgent(agent)}
                  className="block w-full px-3 py-2 text-left hover:bg-accent"
                >
                  @{agent.name}
                </button>
              ))}
            </div>
          )}

          <div className="relative">
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
              placeholder="Type your message or use @ to mention an agent..."
              className="w-full resize-none rounded-lg border bg-background px-4 py-3 pr-12 text-sm"
              rows={1}
            />
            <button
              onClick={handleSend}
              className="absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
