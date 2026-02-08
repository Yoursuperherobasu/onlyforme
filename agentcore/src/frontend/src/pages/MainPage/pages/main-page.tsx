import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import SideBarFoldersButtonsComponent from "@/components/core/folderSidebarComponent/components/sideBarFolderButtons";
import { SidebarProvider } from "@/components/ui/sidebar";
import CustomEmptyPageCommunity from "@/customization/components/custom-empty-page";
import CustomLoader from "@/customization/components/custom-loader";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";

import ModalsComponent from "../components/modalsComponent";
import FolderCardsView from "./folderCollections/folder-cards-view";
import EditFolderModal from "./folderCollections/edit-folder-modal";

import {
  useDeleteFolders,
  usePatchFolders,
} from "@/controllers/API/queries/folders";

export default function CollectionPage(): JSX.Element {
  /* ================= STATE ================= */

  const [openModal, setOpenModal] = useState(false);
  const [openDeleteFolderModal, setOpenDeleteFolderModal] = useState(false);
  const [openEditFolderModal, setOpenEditFolderModal] = useState(false);

  const navigate = useCustomNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  /* ================= STORES ================= */

  const flows = useFlowsManagerStore((s) => s.flows);
  const examples = useFlowsManagerStore((s) => s.examples);

  const folders = useFolderStore((s) => s.folders);
  const folderToEdit = useFolderStore((s) => s.folderToEdit);
  const setFolderToEdit = useFolderStore((s) => s.setFolderToEdit);

  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  /* ================= ROUTE DETECTION ================= */

  const isFlowsRoute =
    location.pathname === "/flows" || location.pathname === "/flows/";

  const isInFlowsFolder = location.pathname.includes("/flows/folder/");

  /* ================= CLEANUP ================= */

  useEffect(() => {
    return () => {
      queryClient.removeQueries({ queryKey: ["useGetFolder"] });
    };
  }, [queryClient]);

  /* ================= API MUTATIONS ================= */

  const { mutate: deleteFolder } = useDeleteFolders();
  const { mutate: updateFolder } = usePatchFolders();

  const handleDeleteFolder = () => {
    if (!folderToEdit) return;

    deleteFolder(
      { folder_id: folderToEdit.id },
      {
        onSuccess: () => {
          setSuccessData({ title: "Project deleted successfully." });
          navigate("/flows");
        },
        onError: () => {
          setErrorData({ title: "Error deleting project." });
        },
      },
    );
  };

  const handleUpdateFolderName = (newName: string) => {
    if (!folderToEdit || !newName.trim()) return;

    updateFolder(
      {
        folderId: folderToEdit.id,
        data: {
          ...folderToEdit,
          name: newName.trim(),
          flows: folderToEdit.flows ?? [],
          components: folderToEdit.components ?? [],
        },
      },
      {
        onSuccess: () => {
          setSuccessData({ title: "Project renamed successfully." });
          setOpenEditFolderModal(false);
          setFolderToEdit(undefined);
        },
        onError: () => {
          setErrorData({ title: "Error renaming project." });
        },
      },
    );
  };

  /* ================= DERIVED STATE ================= */

  const hasContent = Boolean(flows && examples && folders);

  const showEmptyState =
    hasContent &&
    flows.length === examples.length &&
    folders.length <= 1;

  const showSidebar = Boolean(hasContent && folders.length > 0);

  /* ================= SHARED SIDEBAR ================= */

  const Sidebar = showSidebar ? (
    <SideBarFoldersButtonsComponent
      handleChangeFolder={(id: string) => {
        navigate(`/flows/folder/${id}`);
      }}
      handleDeleteFolder={(folder) => {
        setFolderToEdit(folder);
        setOpenDeleteFolderModal(true);
      }}
      handleFilesClick={() => {
        navigate("/assets/files");
      }}
    />
  ) : null;

  /* ================= LAYOUT ================= */

  return (
    <SidebarProvider width="280px">
      {Sidebar}

      <main className="flex h-full w-full overflow-hidden">
        {!hasContent ? (
          <div className="flex h-full w-full items-center justify-center">
            <CustomLoader remSize={30} />
          </div>
        ) : isFlowsRoute ? (
          <div className="relative mx-auto flex h-full w-full flex-col overflow-hidden">
            {showEmptyState ? (
              <CustomEmptyPageCommunity setOpenModal={setOpenModal} />
            ) : (
              <FolderCardsView
                setOpenModal={setOpenModal}
                onFolderClick={(folderId: string) => {
                  navigate(`/flows/folder/${folderId}`);
                }}
                onRenameFolder={(folder) => {
                  setFolderToEdit(folder);
                  setOpenEditFolderModal(true);
                }}
                onDeleteFolder={(folder) => {
                  setFolderToEdit(folder);
                  setOpenDeleteFolderModal(true);
                }}
                // onFilesClick={() => {
                //   navigate("/assets/files");
                // }}
              />
            )}
          </div>
        ) : (
          <div className="relative mx-auto flex h-full w-full flex-col overflow-hidden">
            <Outlet />
          </div>
        )}
      </main>

      <ModalsComponent
        openModal={openModal}
        setOpenModal={setOpenModal}
        openDeleteFolderModal={openDeleteFolderModal}
        setOpenDeleteFolderModal={setOpenDeleteFolderModal}
        handleDeleteFolder={handleDeleteFolder}
      />

      <EditFolderModal
        open={openEditFolderModal}
        setOpen={setOpenEditFolderModal}
        folder={folderToEdit}
        onSave={handleUpdateFolderName}
      />
    </SidebarProvider>
  );
}