import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useContext } from "react";
import { useLocation, useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { AuthContext } from "@/contexts/authContext";
import { SidebarRail, SidebarTrigger } from "@/components/ui/sidebar";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { DEFAULT_FOLDER } from "@/constants/constants";
import { useUpdateUser } from "@/controllers/API/queries/auth";
import {
  usePatchFolders,
  usePostFolders,
  usePostUploadFolders,
} from "@/controllers/API/queries/folders";
import { useGetDownloadFolders } from "@/controllers/API/queries/folders/use-get-download-folders";
import { CustomStoreButton } from "@/customization/components/custom-store-button";
import {
  ENABLE_CUSTOM_PARAM,
  ENABLE_DATASTAX_LANGBUILDER,
  ENABLE_FILE_MANAGEMENT,
  ENABLE_KNOWLEDGE_BASES,
  ENABLE_MCP_NOTICE,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import { customGetDownloadFolderBlob } from "@/customization/utils/custom-get-download-folders";
import { createFileUpload } from "@/helpers/create-file-upload";
import { getObjectsFromFilelist } from "@/helpers/get-objects-from-filelist";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { useIsMobile } from "@/hooks/use-mobile";
import useAuthStore from "@/stores/authStore";
import type { FolderType } from "../../../../../pages/MainPage/entities";
import useAlertStore from "../../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../../stores/foldersStore";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import { cn } from "../../../../../utils/utils";
import useFileDrop from "../../hooks/use-on-file-drop";
import { SidebarFolderSkeleton } from "../sidebarFolderSkeleton";
import { HeaderButtons } from "./components/header-buttons";
import { InputEditFolderName } from "./components/input-edit-folder-name";
import { MCPServerNotice } from "./components/mcp-server-notice";
import { SelectOptions } from "./components/select-options";

type SideBarFoldersButtonsComponentProps = {
  handleChangeFolder?: (id: string) => void;
  handleDeleteFolder?: (item: FolderType) => void;
  handleFilesClick?: () => void;
};
const SideBarFoldersButtonsComponent = ({
  handleChangeFolder,
  handleDeleteFolder,
  handleFilesClick,
}: SideBarFoldersButtonsComponentProps) => {
  const location = useLocation();
  const pathname = location.pathname;
  const folders = useFolderStore((state) => state.folders);
  const loading = !folders;
  const refInput = useRef<HTMLInputElement>(null);

  const _navigate = useCustomNavigate();

  const currentFolder = pathname.split("/");
  const urlWithoutPath =
    pathname.split("/").length < (ENABLE_CUSTOM_PARAM ? 5 : 4);
  const checkPathFiles = pathname.includes("assets");

  const checkPathName = (itemId: string) => {
    if (urlWithoutPath && itemId === myCollectionId && !checkPathFiles) {
      return true;
    }
    return currentFolder.includes(itemId);
  };

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const isMobile = useIsMobile({ maxWidth: 1024 });
  const folderIdDragging = useFolderStore((state) => state.folderIdDragging);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const { permissions, role } = useContext(AuthContext);

  const folderId = useParams().folderId ?? myCollectionId ?? "";

  const { dragOver, dragEnter, dragLeave, onDrop } = useFileDrop(folderId);
  const uploadFlow = useUploadFlow();
  const [foldersNames, setFoldersNames] = useState({});
  const [editFolders, setEditFolderName] = useState(
    folders.map((obj) => ({ name: obj.name, edit: false })) ?? [],
  );

  const isFetchingFolders = !!useIsFetching({
    queryKey: ["useGetFolders"],
    exact: false,
  });

  const { mutate: mutateDownloadFolder } = useGetDownloadFolders({});
  const { mutate: mutateAddFolder, isPending } = usePostFolders();
  const { mutate: mutateUpdateFolder } = usePatchFolders();
  const { mutate } = usePostUploadFolders();

  const checkHoveringFolder = (folderId: string) => {
    if (folderId === folderIdDragging) {
      return "bg-accent text-accent-foreground";
    }
  };

  const isFetchingFolder = !!useIsFetching({
    queryKey: ["useGetFolder"],
    exact: false,
  });

  const isDeletingFolder = !!useIsMutating({
    mutationKey: ["useDeleteFolders"],
  });

  const isUpdatingFolder =
    isFetchingFolders ||
    isFetchingFolder ||
    isPending ||
    loading ||
    isDeletingFolder;

  const handleUploadFlowsToFolder = () => {
    createFileUpload().then((files: File[]) => {
      if (files?.length === 0) {
        return;
      }

      getObjectsFromFilelist<any>(files).then((objects) => {
        if (objects.every((flow) => flow.data?.nodes)) {
          uploadFlow({ files }).then(() => {
            setSuccessData({
              title: "Uploaded successfully",
            });
          });
        } else {
          files.forEach((folder) => {
            const formData = new FormData();
            formData.append("file", folder);
            mutate(
              { formData },
              {
                onSuccess: () => {
                  setSuccessData({
                    title: "Project uploaded successfully.",
                  });
                },
                onError: (err) => {
                  console.error(err);
                  setErrorData({
                    title: `Error on uploading your project, try dragging it into an existing project.`,
                    list: [err["response"]["data"]["message"]],
                  });
                },
              },
            );
          });
        }
      });
    });
  };

  const handleDownloadFolder = (id: string, folderName: string) => {
    mutateDownloadFolder(
      {
        folderId: id,
      },
      {
        onSuccess: (response) => {
          customGetDownloadFolderBlob(response, id, folderName, setSuccessData);
        },
        onError: (e) => {
          setErrorData({
            title: `An error occurred while downloading your project.`,
          });
        },
      },
    );
  };

  function addNewFolder() {
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
          handleChangeFolder!(folder.id);
        },
      },
    );
  }

  function handleEditFolderName(e, name): void {
    const {
      target: { value },
    } = e;
    setFoldersNames((old) => ({
      ...old,
      [name]: value,
    }));
  }

  useEffect(() => {
    if (folders && folders.length > 0) {
      setEditFolderName(
        folders.map((obj) => ({ name: obj.name, edit: false })),
      );
    }
  }, [folders]);

  const handleEditNameFolder = async (item) => {
    const newEditFolders = editFolders.map((obj) => {
      if (obj.name === item.name) {
        return { name: item.name, edit: false };
      }
      return { name: obj.name, edit: false };
    });
    setEditFolderName(newEditFolders);
    if (foldersNames[item.name].trim() !== "") {
      setFoldersNames((old) => ({
        ...old,
        [item.name]: foldersNames[item.name],
      }));
      const body = {
        ...item,
        name: foldersNames[item.name],
        flows: item.flows?.length > 0 ? item.flows : [],
        components: item.components?.length > 0 ? item.components : [],
      };

      mutateUpdateFolder(
        {
          data: body,
          folderId: item.id!,
        },
        {
          onSuccess: (updatedFolder) => {
            const updatedFolderIndex = folders.findIndex(
              (f) => f.id === updatedFolder.id,
            );

            const updateFolders = [...folders];
            updateFolders[updatedFolderIndex] = updatedFolder;

            setFoldersNames({});
            setEditFolderName(
              folders.map((obj) => ({
                name: obj.name,
                edit: false,
              })),
            );
          },
        },
      );
    } else {
      setFoldersNames((old) => ({
        ...old,
        [item.name]: item.name,
      }));
    }
  };

  const handleDoubleClick = (event, item) => {
    if (item.name === DEFAULT_FOLDER) {
      return;
    }

    event.stopPropagation();
    event.preventDefault();

    handleSelectFolderToRename(item);
  };

  const handleSelectFolderToRename = (item) => {
    if (!foldersNames[item.name]) {
      setFoldersNames({ [item.name]: item.name });
    }

    if (editFolders.find((obj) => obj.name === item.name)?.name) {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.name === item.name) {
          return { name: item.name, edit: true };
        }
        return { name: obj.name, edit: false };
      });
      setEditFolderName(newEditFolders);
      takeSnapshot();
      return;
    }

    setEditFolderName((old) => [...old, { name: item.name, edit: true }]);
    setFoldersNames((oldFolder) => ({
      ...oldFolder,
      [item.name]: item.name,
    }));
    takeSnapshot();
  };

  const handleKeyDownFn = (e, item) => {
    if (e.key === "Escape") {
      const newEditFolders = editFolders.map((obj) => {
        if (obj.name === item.name) {
          return { name: item.name, edit: false };
        }
        return { name: obj.name, edit: false };
      });
      setEditFolderName(newEditFolders);
      setFoldersNames({});
      setEditFolderName(
        folders.map((obj) => ({
          name: obj.name,
          edit: false,
        })),
      );
    }
    if (e.key === "Enter") {
      refInput.current?.blur();
    }
  };

  const [hoveredFolderId, setHoveredFolderId] = useState<string | null>(null);

  const userData = useAuthStore((state) => state.userData);
  const { mutate: updateUser } = useUpdateUser();
  const userDismissedMcpDialog = userData?.optins?.mcp_dialog_dismissed;

  const [isDismissedMcpDialog, setIsDismissedMcpDialog] = useState(
    userDismissedMcpDialog,
  );

  const handleDismissMcpDialog = () => {
    setIsDismissedMcpDialog(true);
    updateUser({
      user_id: userData?.id!,
      user: {
        optins: {
          ...userData?.optins,
          mcp_dialog_dismissed: true,
        },
      },
    });
  };

  const handleFilesNavigation = () => {
    _navigate("/assets/files");
  };

  const handleKnowledgeNavigation = () => {
    _navigate("/assets/knowledge-bases");
  };

  return (
    <Sidebar
      collapsible={isMobile ? "offcanvas" : "icon"}
      data-testid="project-sidebar"
      className="bg-[var(--sidebar-background)] text-[var(--sidebar-foreground)]"
    >
      {/* ================= HEADER ================= */}
      <div
        className="absolute top-[56px] right-[-12px] z-50 -translate-y-1/2"
      >
        <SidebarTrigger
          className="h-6 w-6 rounded-full bg-background border shadow-md hover:bg-accent"
        />
      </div>
      <SidebarHeader className="flex h-12 items-center px-3">
        {/* Left side (title or spacer) */}
        <div className="flex flex-1 items-center"></div>
      </SidebarHeader>

      {/* ================= CONTENT ================= */}
      <SidebarContent className="text-[var(--sidebar-foreground)]">
        <SidebarGroup className="p-4 py-2">
          <SidebarGroupContent>
            <SidebarMenu className="text-[var(--sidebar-foreground)]">
              {/* Dashboard */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/dashboard")}
                  onClick={() => _navigate("/dashboard")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="LayoutDashboard"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Dashboard
                </SidebarMenuButton>
              </SidebarMenuItem>

              {/* Projects */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="FolderKanban"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Projects
                </SidebarMenuButton>
              </SidebarMenuItem>

              {/* Review & Approval */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="ClipboardCheck"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Review & Approval
                </SidebarMenuButton>
              </SidebarMenuItem>
              {/* Agent Registry */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="BrainCog"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Agent Registry
                </SidebarMenuButton>
              </SidebarMenuItem>
              {/* Model Registry */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="Workflow"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Model Registry
                </SidebarMenuButton>
              </SidebarMenuItem>
              {/* Orchestrator */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="Cog"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Orchestrator 
                </SidebarMenuButton>
              </SidebarMenuItem>

              {/* Observability */}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="md"
                  isActive={pathname.startsWith("/approval")}
                  onClick={() => _navigate("/approval")}
                  className="text-[var(--sidebar-foreground)]"
                >
                  <ForwardedIconComponent
                    name="BarChart3"
                    className="h-4 w-4 text-[var(--sidebar-foreground)]"
                  />
                  Observability
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* ================= FOOTER ================= */}
      <SidebarFooter className="border-t">
        <div className="grid w-full items-center gap-2 p-2">
          <SidebarMenuButton
            onClick={() => _navigate("/settings")}
            size="md"
            className="text-sm text-[var(--sidebar-foreground)]"
          >
            <ForwardedIconComponent
              name="Settings"
              className="h-4 w-4 text-[var(--sidebar-foreground)]"
            />
            Settings
          </SidebarMenuButton>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
};
export default SideBarFoldersButtonsComponent;