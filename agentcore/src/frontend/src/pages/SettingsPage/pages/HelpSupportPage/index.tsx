import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  HelpCircle,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useAuthStore from "@/stores/authStore";
import useAlertStore from "@/stores/alertStore";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type HelpQuestion = {
  id: string;
  question: string;
  answer: string;
  created_at: string;
  updated_at: string;
};

type HelpQuestionPayload = {
  question: string;
  answer: string;
};

const QUERY_KEY = ["help-support-questions"];

export default function HelpSupportPage() {
  const role = useAuthStore((state) => state.role);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const queryClient = useQueryClient();

  const [searchValue, setSearchValue] = useState("");
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingQuestion, setEditingQuestion] = useState("");
  const [editingAnswer, setEditingAnswer] = useState("");
  const [editOpen, setEditOpen] = useState(false);

  const isAdminEditor = useMemo(
    () =>
      ["root", "super_admin", "department_admin"].includes(
        (role || "").toLowerCase(),
      ),
    [role],
  );

  const { data: questions = [], isLoading } = useQuery<HelpQuestion[]>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const response = await api.get(`${getURL("HELP_SUPPORT")}/questions`);
      return response.data ?? [];
    },
    refetchOnWindowFocus: false,
  });

  const filteredQuestions = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    if (!q) return questions;
    return questions.filter(
      (item) =>
        item.question.toLowerCase().includes(q) ||
        item.answer.toLowerCase().includes(q),
    );
  }, [questions, searchValue]);

  const createMutation = useMutation({
    mutationFn: async (payload: HelpQuestionPayload) => {
      const response = await api.post(
        `${getURL("HELP_SUPPORT")}/questions`,
        payload,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      setSuccessData({ title: "Question created" });
      setNewQuestion("");
      setNewAnswer("");
      setCreateOpen(false);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to create question",
        list: [error?.response?.data?.detail || "Unexpected error"],
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: string; data: HelpQuestionPayload }) => {
      const response = await api.patch(
        `${getURL("HELP_SUPPORT")}/questions/${payload.id}`,
        payload.data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      setSuccessData({ title: "Question updated" });
      setEditingId(null);
      setEditingQuestion("");
      setEditingAnswer("");
      setEditOpen(false);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to update question",
        list: [error?.response?.data?.detail || "Unexpected error"],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(
        `${getURL("HELP_SUPPORT")}/questions/${id}`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      setSuccessData({ title: "Question deleted" });
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to delete question",
        list: [error?.response?.data?.detail || "Unexpected error"],
      });
    },
  });

  const openEditModal = (item: HelpQuestion) => {
    setEditingId(item.id);
    setEditingQuestion(item.question);
    setEditingAnswer(item.answer);
    setEditOpen(true);
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex h-full min-h-0 w-full flex-col gap-4 px-5 py-5 md:px-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex w-full flex-col">
            <h2 className="flex items-center text-lg font-semibold tracking-tight">
              Help & Support
              <HelpCircle className="ml-2 h-5 w-5 text-primary" />
            </h2>
            <p className="text-sm text-muted-foreground">
              Find answers to common questions or reach out to us.
            </p>
          </div>
          {isAdminEditor && (
            <Button
              variant="outline"
              size="sm"
              className="flex shrink-0 items-center gap-1.5 text-xs"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Add FAQ
            </Button>
          )}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
          <Input
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="Search for articles..."
            className="h-9 rounded-lg border bg-background pl-9 text-sm shadow-sm placeholder:text-muted-foreground/50 focus-visible:ring-1 focus-visible:ring-ring"
          />
          {searchValue && (
            <button
              onClick={() => setSearchValue("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* FAQ Section */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Frequently Asked Questions
            </p>
            {searchValue && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                {filteredQuestions.length} result
                {filteredQuestions.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center gap-2 px-4 py-12">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground/20 border-t-primary" />
                <p className="text-xs text-muted-foreground">
                  Loading questions...
                </p>
              </div>
            ) : filteredQuestions.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-1.5 px-4 py-12">
                <Search className="h-5 w-5 text-muted-foreground/40" />
                <p className="text-xs font-medium text-muted-foreground">
                  No questions found
                </p>
                <p className="text-[11px] text-muted-foreground/60">
                  {searchValue
                    ? "Try a different search term."
                    : "No FAQ entries have been added yet."}
                </p>
              </div>
            ) : (
              <Accordion type="single" collapsible className="w-full">
                {filteredQuestions.map((item) => (
                  <AccordionItem
                    key={item.id}
                    value={item.id}
                    className="border-b last:border-b-0"
                  >
                    <AccordionTrigger className="px-4 py-3 text-left hover:bg-accent/30 hover:no-underline [&[data-state=open]]:bg-accent/20">
                      <p className="min-w-0 pr-2 text-[13px] font-medium leading-5 text-foreground">
                        {item.question}
                      </p>
                    </AccordionTrigger>

                    <AccordionContent className="px-4 pb-3">
                      <div className="flex flex-col gap-3">
                        <p className="whitespace-pre-wrap text-[12.5px] leading-[1.6] text-muted-foreground">
                          {item.answer}
                        </p>

                        {isAdminEditor && (
                          <div className="flex gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 gap-1.5 px-2.5 text-[11px] text-muted-foreground hover:text-foreground"
                              onClick={() => openEditModal(item)}
                            >
                              <Pencil className="h-3 w-3" />
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 gap-1.5 px-2.5 text-[11px] text-destructive hover:bg-destructive/10 hover:text-destructive"
                              onClick={() => deleteMutation.mutate(item.id)}
                              disabled={deleteMutation.isPending}
                            >
                              <Trash2 className="h-3 w-3" />
                              Delete
                            </Button>
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </div>
        </div>
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-base">Add Question</DialogTitle>
            <DialogDescription className="text-xs">
              Create a new FAQ entry visible to all users.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-1">
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Question
              </label>
              <Input
                value={newQuestion}
                onChange={(e) => setNewQuestion(e.target.value)}
                placeholder="e.g. How do I reset my password?"
                className="h-9 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Answer
              </label>
              <textarea
                value={newAnswer}
                onChange={(e) => setNewAnswer(e.target.value)}
                placeholder="Write a clear, concise answer..."
                className="primary-input min-h-28 w-full resize-y text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
              onClick={() => {
                setCreateOpen(false);
                setNewQuestion("");
                setNewAnswer("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="gap-1.5 text-xs"
              onClick={() =>
                createMutation.mutate({
                  question: newQuestion.trim(),
                  answer: newAnswer.trim(),
                })
              }
              disabled={
                !newQuestion.trim() ||
                !newAnswer.trim() ||
                createMutation.isPending
              }
            >
              <Save className="h-3.5 w-3.5" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-base">Edit Question</DialogTitle>
            <DialogDescription className="text-xs">
              Update this FAQ entry.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-1">
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Question
              </label>
              <Input
                value={editingQuestion}
                onChange={(e) => setEditingQuestion(e.target.value)}
                placeholder="Question"
                className="h-9 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Answer
              </label>
              <textarea
                value={editingAnswer}
                onChange={(e) => setEditingAnswer(e.target.value)}
                placeholder="Answer"
                className="primary-input min-h-28 w-full resize-y text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
              onClick={() => {
                setEditOpen(false);
                setEditingId(null);
                setEditingQuestion("");
                setEditingAnswer("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="gap-1.5 text-xs"
              onClick={() =>
                editingId &&
                updateMutation.mutate({
                  id: editingId,
                  data: {
                    question: editingQuestion.trim(),
                    answer: editingAnswer.trim(),
                  },
                })
              }
              disabled={
                !editingId ||
                !editingQuestion.trim() ||
                !editingAnswer.trim() ||
                updateMutation.isPending
              }
            >
              <Save className="h-3.5 w-3.5" />
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
