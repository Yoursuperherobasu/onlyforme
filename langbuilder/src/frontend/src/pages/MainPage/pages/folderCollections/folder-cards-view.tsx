import { Plus, Folder, MoreVertical, Edit2, Trash2, Download, FileText } from "lucide-react";
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
  
  const { mutate: mutateAddFolder, isPending } = usePostFolders();
  const { mutate: mutateDownloadFolder } = useGetDownloadFolders({});

  const displayFolders = folders || [];

  // Count flows per folder
  const getFlowCount = (folderId: string) => {
    return flows?.filter((flow) => flow.folder_id === folderId).length || 0;
  };

  // Handle creating new folder (same as sidebar)
  const handleCreateNewFolder = () => {
    mutateAddFolder(
      {
        data: {
          name: "New Project",
          parent_id: null,
          description: "",
        },
      },
      {
        onSuccess: (folder) => {
          track("Create New Project");
          setSuccessData({
            title: "Project created successfully.",
          });
          // Navigate to the new folder
          onFolderClick(folder.id);
        },
        onError: (err) => {
          console.error(err);
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
    <div className="flex h-full w-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-2xl font-semibold">Projects</h1>
          <p className="text-sm text-muted-foreground">
            Manage your workflow projects
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

      {/* Cards Grid */}
      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {/* Create New Project Card */}
          <button
            onClick={handleCreateNewFolder}
            disabled={isPending}
            className="group flex min-h-[200px] flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 bg-background p-6 transition-all hover:border-primary hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 transition-colors group-hover:bg-primary/20">
              <Plus className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-lg font-semibold">
              {isPending ? "Creating..." : "Create New Project"}
            </h3>
            <p className="mt-2 text-center text-sm text-muted-foreground">
              Start a new workflow project
            </p>
          </button>

          {/* Existing Folder Cards */}
          {displayFolders.map((folder) => {
            const flowCount = getFlowCount(folder.id);
            return (
              <div
                key={folder.id}
                className="group relative flex min-h-[200px] flex-col rounded-lg border bg-card transition-all hover:border-primary hover:shadow-lg"
              >
                {/* Three dots menu */}
                <div className="absolute right-2 top-2 z-10">
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

                {/* Clickable card content */}
                <button
                  onClick={() => onFolderClick(folder.id)}
                  className="flex flex-1 flex-col p-6 text-left"
                >
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
                    <Folder className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-card-foreground">
                    {folder.name}
                  </h3>
                  {folder.description && (
                    <p className="mb-4 flex-1 text-sm text-muted-foreground line-clamp-2">
                      {folder.description}
                    </p>
                  )}
                  <div className="mt-auto flex items-center justify-between pt-4 text-sm text-muted-foreground">
                    <span>
                      {flowCount} {flowCount === 1 ? "flow" : "flows"}
                    </span>
                    <span className="text-xs opacity-0 transition-opacity group-hover:opacity-100">
                      Open →
                    </span>
                  </div>
                </button>
              </div>
            );
          })}
        </div>

        {/* Empty State */}
        {displayFolders.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <Folder className="mx-auto mb-4 h-16 w-16 text-muted-foreground/50" />
              <h3 className="mb-2 text-lg font-semibold">No projects yet</h3>
              <p className="mb-4 text-sm text-muted-foreground">
                Create your first project to get started
              </p>
              <button
                onClick={handleCreateNewFolder}
                disabled={isPending}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                {isPending ? "Creating..." : "Create Project"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}