import { useState } from "react";
import { Plus, Folder, MoreVertical, Edit2, Trash2, Download, FileText, X, Grid3x3, List } from "lucide-react";
import { useFolderStore } from "@/stores/foldersStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { usePostFolders } from "@/controllers/API/queries/folders";
import { useGetDownloadFolders } from "@/controllers/API/queries/folders/use-get-download-folders";
import useAlertStore from "@/stores/alertStore";
import { track } from "@/customization/utils/analytics";
import { customGetDownloadFolderBlob } from "@/customization/utils/custom-get-download-folders";
import type { FolderType } from "@/pages/MainPage/entities";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface FolderCardsViewProps {
  setOpenModal: (open: boolean) => void;
  onFolderClick: (folderId: string) => void;
  onRenameFolder?: (folder: FolderType) => void;
  onDeleteFolder?: (folder: FolderType) => void;
  onFilesClick?: () => void;
}

export default function FolderCardsView({
  setOpenModal,
  onFolderClick,
  onRenameFolder,
  onDeleteFolder,
  onFilesClick,
}: FolderCardsViewProps): JSX.Element {
  const folders = useFolderStore((state) => state.folders);
  const flows = useFlowsManagerStore((state) => state.flows);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  
  const { mutate: mutateAddFolder, isPending } = usePostFolders();
  const { mutate: mutateDownloadFolder } = useGetDownloadFolders({});

  const displayFolders = folders || [];
  
  // Split folders into recent (top 5) and older
  const recentFolders = displayFolders.slice(0, 5);
  const olderFolders = displayFolders.slice(5);

  // Count flows per folder
  const getFlowCount = (folderId: string) => {
    if (!flows || flows.length === 0) return 0;
    const count = flows.filter((flow) => flow.folder_id === folderId).length;
    console.log(`Folder ${folderId} has ${count} flows`); // Debug log
    return count;
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  // Open create modal
  const handleOpenCreateModal = () => {
    setProjectName("");
    setProjectDescription("");
    setCreateModalOpen(true);
  };

  // Handle creating new folder
  const handleCreateNewFolder = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!projectName.trim()) {
      setErrorData({ title: "Project name is required" });
      return;
    }

    mutateAddFolder(
      {
        data: {
          name: projectName.trim(),
          parent_id: null,
          description: projectDescription.trim(),
        },
      },
      {
        onSuccess: (folder) => {
          track("Create New Project");
          setSuccessData({
            title: "Project created successfully.",
          });
          setCreateModalOpen(false);
          setProjectName("");
          setProjectDescription("");
          onFolderClick(folder.id);
        },
        onError: (err) => {
          console.error(err);
          setErrorData({ title: "Failed to create project" });
        },
      },
    );
  };

  const handleDownloadFolder = (folder: FolderType) => {
    mutateDownloadFolder(
      {
        folderId: folder.id!,
      },
      {
        onSuccess: (response) => {
          customGetDownloadFolderBlob(response, folder.id!, folder.name, setSuccessData);
        },
        onError: (e) => {
          setErrorData({
            title: `An error occurred while downloading your project.`,
          });
        },
      },
    );
  };

  return (
    <>
      <div className="flex h-full w-full flex-col overflow-auto bg-background">
        {/* Header */}
        <div className="flex items-center justify-between border-b bg-background px-6 py-4 sticky top-0 z-10">
          <div>
            <h1 className="text-2xl font-semibold">Projects</h1>
            <p className="text-sm text-muted-foreground">
              Start a new project or select an existing one
            </p>
          </div>
          {onFilesClick && (
            <Button
              onClick={onFilesClick}
              variant="outline"
              className="gap-2"
            >
              <FileText className="h-4 w-4" />
              My Files
            </Button>
          )}
        </div>

        {/* Cards Section - Recent Projects */}
        <div className="border-b bg-muted/30 px-6 py-6">
          <h2 className="mb-4 text-sm font-semibold text-muted-foreground">Recents</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {/* Create New Project Card */}
            <button
              onClick={handleOpenCreateModal}
              disabled={isPending}
              className="group flex aspect-square flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 bg-background p-4 transition-all hover:border-primary hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
                <Plus className="h-6 w-6 text-primary" />
              </div>
              <span className="text-center text-xs font-medium">Blank project</span>
            </button>

            {/* Recent Folder Cards */}
            {recentFolders.map((folder) => {
              const flowCount = getFlowCount(folder.id);
              return (
                <div
                  key={folder.id}
                  className="group relative flex min-h-[180px] flex-col items-start justify-between rounded-lg border bg-card p-5 transition-all hover:border-primary hover:shadow-md"
                >
                  {/* Three dots menu */}
                  <div className="absolute right-2 top-2 z-10">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          onClick={(e) => e.stopPropagation()}
                          className="flex h-6 w-6 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                        >
                          <MoreVertical className="h-3.5 w-3.5" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            onRenameFolder?.(folder);
                          }}
                        >
                          <Edit2 className="mr-2 h-4 w-4" />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadFolder(folder);
                          }}
                        >
                          <Download className="mr-2 h-4 w-4" />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteFolder?.(folder);
                          }}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  {/* Clickable card content */}
                  <button
                    onClick={() => onFolderClick(folder.id)}
                    className="flex w-full flex-1 flex-col items-center justify-center gap-3 text-center py-2"
                  >
                    <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
                      <Folder className="h-7 w-7 text-primary" />
                    </div>
                    <div className="w-full space-y-2">
                      <span className="block text-sm font-semibold line-clamp-2 leading-snug">
                        {folder.name}
                      </span>
                      {folder.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed px-1">
                          {folder.description}
                        </p>
                      )}
                      <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground pt-1">
                        <span>{flowCount} {flowCount === 1 ? "flow" : "flows"}</span>
                        {folder.updated_at && (
                          <>
                            <span>•</span>
                            <span>{formatDate(folder.updated_at)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Table/List Section - Older Projects */}
        {olderFolders.length > 0 && (
          <div className="flex-1 overflow-auto px-6 py-4">
            <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Earlier</h2>
            
            <div className="rounded-lg border bg-card">
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 border-b bg-muted/50 px-4 py-3 text-xs font-medium text-muted-foreground">
                <div className="col-span-6 flex items-center gap-2">
                  <Folder className="h-4 w-4" />
                  Name
                </div>
                <div className="col-span-2">Owner</div>
                <div className="col-span-3">Last opened</div>
                <div className="col-span-1"></div>
              </div>

              {/* Table Body */}
              <div className="divide-y">
                {olderFolders.map((folder) => {
                  const flowCount = getFlowCount(folder.id);
                  return (
                    <div
                      key={folder.id}
                      className="grid grid-cols-12 gap-4 px-4 py-3 transition-colors hover:bg-muted/50 cursor-pointer group"
                      onClick={() => onFolderClick(folder.id)}
                    >
                      {/* Name Column */}
                      <div className="col-span-6 flex items-center gap-3">
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-primary/10">
                          <Folder className="h-4 w-4 text-primary" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-medium text-sm">
                              {folder.name}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            {folder.description && (
                              <>
                                <p className="text-xs text-muted-foreground truncate">
                                  {folder.description}
                                </p>
                                <span className="text-xs text-muted-foreground">•</span>
                              </>
                            )}
                            <span className="text-xs text-muted-foreground whitespace-nowrap">
                              {flowCount} {flowCount === 1 ? "flow" : "flows"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Owner Column */}
                      <div className="col-span-2 flex items-center text-sm text-muted-foreground">
                        me
                      </div>

                      {/* Last Opened Column */}
                      <div className="col-span-3 flex items-center text-sm text-muted-foreground">
                        {folder.updated_at ? formatDate(folder.updated_at) : '--'}
                      </div>

                      {/* Actions Column */}
                      <div className="col-span-1 flex items-center justify-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              onClick={(e) => e.stopPropagation()}
                              className="flex h-8 w-8 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                            >
                              <MoreVertical className="h-4 w-4" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                onRenameFolder?.(folder);
                              }}
                            >
                              <Edit2 className="mr-2 h-4 w-4" />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDownloadFolder(folder);
                              }}
                            >
                              <Download className="mr-2 h-4 w-4" />
                              Download
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteFolder?.(folder);
                              }}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {displayFolders.length === 0 && (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <Folder className="mx-auto mb-4 h-16 w-16 text-muted-foreground/50" />
              <h3 className="mb-2 text-lg font-semibold">No projects yet</h3>
              <p className="mb-4 text-sm text-muted-foreground">
                Create your first project to get started
              </p>
              <button
                onClick={handleOpenCreateModal}
                disabled={isPending}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                Create Project
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {createModalOpen && (
        <>
          <div
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            onClick={() => setCreateModalOpen(false)}
          />

          <div className="fixed left-[50%] top-[50%] z-50 w-full max-w-lg translate-x-[-50%] translate-y-[-50%] rounded-lg border border-border bg-card p-6 shadow-lg">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold text-card-foreground">
                  Create New Project
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Enter a name and description for your project
                </p>
              </div>
              <button
                onClick={() => setCreateModalOpen(false)}
                className="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100"
              >
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </button>
            </div>

            <form onSubmit={handleCreateNewFolder} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="projectName" className="text-sm font-medium">
                  Project Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="projectName"
                  required
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="e.g., Customer Support Workflow"
                  className="bg-background"
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="projectDescription" className="text-sm font-medium">
                  Description (Optional)
                </Label>
                <Textarea
                  id="projectDescription"
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Brief description of your project..."
                  rows={3}
                  className="resize-none bg-background"
                />
              </div>

              <div className="flex items-center gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCreateModalOpen(false)}
                  className="flex-1"
                  disabled={isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="default"
                  className="flex-1"
                  disabled={isPending}
                >
                  {isPending ? "Creating..." : "Create Project"}
                </Button>
              </div>
            </form>
          </div>
        </>
      )}
    </>
  );
}