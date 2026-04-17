/**
 * Canvas editor — port of MiBuddy's canvas UI (Answer.tsx:1344-1406).
 *
 * Renders an assistant message inside a bordered, editable card. The
 * user can click the "Edit" action to modify the content inline
 * (contentEditable div); edits auto-save to the backend with a debounce.
 * A "DRAFT" action opens the user's mail client pre-populated with
 * the content — matches MiBuddy's Outlook-draft hand-off.
 */
import { useEffect, useRef, useState } from "react";
import { Pencil, Check, Mail, Smile, BookOpen, Loader2 } from "lucide-react";

// Reading levels — matches MiBuddy's READING_LEVELS constant.
// The "reading level" entry is the middle "keep current" sentinel: clicking
// it is a no-op, consistent with MiBuddy's NON_CLICKABLE_INDEX behaviour.
const READING_LEVELS = [
  "kindergarten",
  "middle school",
  "high school",
  "reading level",
  "college",
  "graduate",
] as const;
const NON_CLICKABLE_INDEX = READING_LEVELS.indexOf(
  "reading level" as (typeof READING_LEVELS)[number],
);

interface CanvasEditorProps {
  messageId: string;
  /** Full markdown / HTML text of the assistant reply. */
  content: string;
  /** Session id so the backend can scope persisted canvas edits. */
  sessionId?: string;
  /** Whether to show the DRAFT (mailto:) button — MiBuddy shows it
   *  only when Outlook is connected & the content looks email-ish. */
  showDraftButton?: boolean;
  /** Called when content changes and is persisted to the backend. */
  onContentChange?: (newContent: string) => void;
}

/* Minimal markdown → HTML for the initial render (headings, bullets,
   paragraphs, bold/italic, inline code). Keeps the editable div
   friendly for plain-prose drafts like emails/memos which is 90% of
   canvas usage. Heavy markdown is rare in canvas responses. */
function mdToHtml(md: string): string {
  const esc = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  const lines = md.split(/\r?\n/);
  const out: string[] = [];
  let inUl = false;
  let inOl = false;
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (inOl) { out.push("</ol>"); inOl = false; }
      out.push("");
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (inOl) { out.push("</ol>"); inOl = false; }
      const level = h[1].length;
      out.push(`<h${level}>${esc(h[2])}</h${level}>`);
      continue;
    }
    const ul = line.match(/^[-*+]\s+(.*)$/);
    if (ul) {
      if (inOl) { out.push("</ol>"); inOl = false; }
      if (!inUl) { out.push("<ul>"); inUl = true; }
      out.push(`<li>${esc(ul[1])}</li>`);
      continue;
    }
    const ol = line.match(/^\d+\.\s+(.*)$/);
    if (ol) {
      if (inUl) { out.push("</ul>"); inUl = false; }
      if (!inOl) { out.push("<ol>"); inOl = true; }
      out.push(`<li>${esc(ol[1])}</li>`);
      continue;
    }
    if (inUl) { out.push("</ul>"); inUl = false; }
    if (inOl) { out.push("</ol>"); inOl = false; }
    // inline replacements on escaped text
    let body = esc(line)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
    out.push(`<p>${body}</p>`);
  }
  if (inUl) out.push("</ul>");
  if (inOl) out.push("</ol>");
  return out.join("\n");
}

/** Very small HTML → plain text for the DRAFT mailto: body. */
function htmlToPlain(html: string): string {
  return html
    .replace(/<br\s*\/?>(\n)?/gi, "\n")
    .replace(/<\/p>\s*<p[^>]*>/gi, "\n\n")
    .replace(/<\/(h\d|li|p|div)>/gi, "\n")
    .replace(/<li[^>]*>/gi, "• ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Extract "Subject: ...\n\nBody..." — matches MiBuddy's emailDraft
 *  parsing so the DRAFT button pre-fills the mailto subject. */
function extractSubjectBody(text: string): { subject?: string; body: string } {
  const m = text.match(/^Subject:\s*(.+?)\r?\n\r?\n([\s\S]*)$/i);
  if (m) return { subject: m[1].trim(), body: m[2].trim() };
  return { body: text };
}

export default function CanvasEditor({
  messageId,
  content,
  sessionId,
  showDraftButton = false,
  onContentChange,
}: CanvasEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [current, setCurrent] = useState<string>(content);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  // Reading-level + emoji state (MiBuddy parity)
  const [showReadingLevel, setShowReadingLevel] = useState(false);
  const [activeReadingIndex, setActiveReadingIndex] = useState<number>(
    NON_CLICKABLE_INDEX,
  );
  const [emojiAction, setEmojiAction] = useState<"words" | "remove">("remove");
  const [panelLoading, setPanelLoading] = useState<null | "emoji" | "reading">(null);

  const editorRef = useRef<HTMLDivElement>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep `current` in sync when a new message streams in
  useEffect(() => {
    if (!isEditing) setCurrent(content);
  }, [content, isEditing]);

  const _canvasCall = (body: Record<string, unknown>) => {
    const tokenMatch = document.cookie.match(/(?:^|;\s*)access_token_ag=([^;]*)/);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (tokenMatch?.[1]) {
      headers["Authorization"] = `Bearer ${decodeURIComponent(tokenMatch[1])}`;
    }
    return fetch("/api/orchestrator/canvas/edit", {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify({ message_id: messageId, session_id: sessionId, ...body }),
    });
  };

  const persist = (html: string) => {
    setSaveState("saving");
    _canvasCall({ content: html, operation: "manual" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then(() => {
        setSaveState("saved");
        onContentChange?.(html);
        window.setTimeout(() => setSaveState("idle"), 1200);
      })
      .catch(() => setSaveState("idle"));
  };

  /** Reading-level rewrite via backend LLM. */
  const handleReadingLevel = async (index: number) => {
    if (index === NON_CLICKABLE_INDEX) return;
    setActiveReadingIndex(index);
    setShowReadingLevel(false);
    setPanelLoading("reading");
    try {
      const html = editorRef.current?.innerHTML ?? current;
      const res = await _canvasCall({
        content: html,
        operation: "reading_level",
        level: READING_LEVELS[index],
        emoji_action: emojiAction,
      });
      const data = await res.json();
      const newContent = data?.data?.[0]?.content;
      if (newContent) {
        setCurrent(newContent);
        onContentChange?.(newContent);
      }
    } catch (e) {
      console.error("reading_level failed:", e);
    } finally {
      setPanelLoading(null);
    }
  };

  /** Toggle add/remove emojis via backend. */
  const handleEmoji = async () => {
    const next: "words" | "remove" = emojiAction === "remove" ? "words" : "remove";
    setEmojiAction(next);
    setPanelLoading("emoji");
    try {
      const html = editorRef.current?.innerHTML ?? current;
      const res = await _canvasCall({
        content: html,
        operation: "emoji",
        emoji_action: next,
      });
      const data = await res.json();
      const newContent = data?.data?.[0]?.content;
      if (newContent) {
        setCurrent(newContent);
        onContentChange?.(newContent);
      }
    } catch (e) {
      console.error("emoji action failed:", e);
    } finally {
      setPanelLoading(null);
    }
  };

  const handleInput = (e: React.FormEvent<HTMLDivElement>) => {
    const html = e.currentTarget.innerHTML;
    setCurrent(html);
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => persist(html), 800);
  };

  const toggleEdit = () => {
    if (isEditing) {
      // Save immediately on toggle off
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      const html = editorRef.current?.innerHTML ?? current;
      persist(html);
    }
    setIsEditing((v) => !v);
  };

  const handleDraft = () => {
    const plain = htmlToPlain(current || content);
    const { subject, body } = extractSubjectBody(plain);
    try {
      const mailto =
        `mailto:?subject=${encodeURIComponent(subject || "Draft")}` +
        `&body=${encodeURIComponent(body)}`;
      window.open(mailto);
    } catch {
      navigator.clipboard.writeText(body).then(() => {
        alert("Email body copied to clipboard. Paste it into a new email.");
      });
    }
  };

  /* Initial HTML: if content already looks like HTML (starts with <),
     use it directly; otherwise render markdown → HTML once. */
  const initialHtml =
    (current || "").trim().startsWith("<")
      ? current
      : mdToHtml(current || "");

  return (
    <div className="ac_canvas_wrapper">
      <div
        ref={editorRef}
        key={`${messageId}-${isEditing ? "edit" : "view"}`}
        className="ac_canvas_answer"
        contentEditable={isEditing}
        suppressContentEditableWarning
        onInput={handleInput}
        dangerouslySetInnerHTML={{ __html: initialHtml }}
      />
      <div className="ac_canvas_actions">
        {saveState !== "idle" && (
          <span className="ac_canvas_save_indicator">
            {saveState === "saving" ? "saving…" : "saved ✓"}
          </span>
        )}
        {showDraftButton && (
          <button
            type="button"
            className="ac_canvas_draft_btn"
            onClick={handleDraft}
            title="Open in a new email"
          >
            <Mail size={14} />
            DRAFT
          </button>
        )}
        <button
          type="button"
          className={`ac_canvas_btn ${isEditing ? "active" : ""}`}
          onClick={toggleEdit}
          title={isEditing ? "Save" : "Edit"}
        >
          {isEditing ? <Check size={14} /> : <Pencil size={14} />}
          {isEditing ? "Save" : "Edit"}
        </button>
      </div>

      {/* Floating panel with emoji + reading-level buttons (MiBuddy port) */}
      {isEditing && (
        <>
          <div className="ac_canvas_floating_panel">
            <button
              type="button"
              className="ac_canvas_panel_btn"
              disabled={panelLoading === "emoji"}
              onClick={handleEmoji}
              title={
                emojiAction === "remove"
                  ? "Add expressive emojis"
                  : "Remove emojis"
              }
            >
              {panelLoading === "emoji" ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Smile size={18} />
              )}
            </button>
            <button
              type="button"
              className="ac_canvas_panel_btn"
              disabled={panelLoading === "reading"}
              onClick={() => setShowReadingLevel((v) => !v)}
              title="Change reading level"
            >
              {panelLoading === "reading" ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <BookOpen size={18} />
              )}
            </button>
          </div>

          {/* Reading-level vertical slider */}
          {showReadingLevel && (
            <div className="ac_reading_level_wrapper">
              <div className="ac_reading_level_label">
                {READING_LEVELS[activeReadingIndex]}
              </div>
              <div className="ac_reading_track">
                {READING_LEVELS.map((lvl, i) => {
                  const active = i === activeReadingIndex;
                  const disabled = i === NON_CLICKABLE_INDEX;
                  return (
                    <div
                      key={lvl}
                      className={`ac_reading_dot ${active ? "active" : ""} ${disabled ? "disabled" : ""}`}
                      title={lvl}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!disabled) handleReadingLevel(i);
                      }}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
