import { useEffect, useMemo, useState } from "react";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useGetFilesV2 } from "@/controllers/API/queries/file-management";
import { useGetKnowledgeBases } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { ENABLE_FILE_MANAGEMENT } from "@/customization/feature-flags";
import { createFileUpload } from "@/helpers/create-file-upload";
import BaseModal from "@/modals/baseModal";
import FilesRendererComponent from "@/modals/fileManagerModal/components/filesRendererComponent";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import { cn } from "@/utils/utils";
import {
  CONSOLE_ERROR_MSG,
  INVALID_FILE_ALERT,
} from "../../../../../constants/alerts_constants";
import useAlertStore from "../../../../../stores/alertStore";
import useAgentsManagerStore from "../../../../../stores/agentsManagerStore";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import type { FileComponentType, InputProps } from "../../types";

export default function InputFileComponent({
  value,
  file_path,
  handleOnNewValue,
  disabled,
  fileTypes,
  isList,
  tempFile = true,
  editNode = false,
  id,
}: InputProps<string, FileComponentType>): JSX.Element {
  const currentAgentId = useAgentsManagerStore((state) => state.currentAgentId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      handleOnNewValue({ value: "", file_path: "" }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  function checkFileType(fileName: string): boolean {
    if (fileTypes === undefined) return true;

    // Extract the file extension
    const fileExtension = fileName.split(".").pop();

    // Check if the extracted extension is in the list of accepted file types
    return fileTypes.includes(fileExtension || "");
  }

  const { mutateAsync, isPending } = usePostUploadFile();
  const [isKnowledgeBaseModalOpen, setIsKnowledgeBaseModalOpen] =
    useState(false);
  const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useState<
    string[]
  >([]);

  const handleButtonClick = (): void => {
    createFileUpload({ multiple: isList, accept: fileTypes?.join(",") }).then(
      (files) => {
        if (files.length === 0) return;

        // For single file mode, only process the first file
        const filesToProcess = isList ? files : [files[0]];

        // Validate all files
        for (const file of filesToProcess) {
          try {
            validateFileSize(file);
          } catch (e) {
            if (e instanceof Error) {
              setErrorData({
                title: e.message,
              });
            }
            return;
          }
          if (!checkFileType(file.name)) {
            setErrorData({
              title: INVALID_FILE_ALERT,
              list: [fileTypes?.join(", ") || ""],
            });
            return;
          }
        }

        // Upload all files
        Promise.all(
          filesToProcess.map(
            (file) =>
              new Promise<{ file_name: string; file_path: string } | null>(
                async (resolve) => {
                  const data = await mutateAsync(
                    { file, id: currentAgentId },
                    {
                      onError: (error) => {
                        console.error(CONSOLE_ERROR_MSG);
                        setErrorData({
                          title: "Error uploading file",
                          list: [error.response?.data?.detail],
                        });
                        resolve(null);
                      },
                    },
                  );
                  resolve({
                    file_name: file.name,
                    file_path: data.file_path,
                  });
                },
              ),
          ),
        )
          .then((results) => {
            console.warn(results);
            // Filter out any failed uploads
            const successfulUploads = results.filter(
              (r): r is { file_name: string; file_path: string } => r !== null,
            );

            if (successfulUploads.length > 0) {
              const fileNames = successfulUploads.map(
                (result) => result.file_name,
              );
              const filePaths = successfulUploads.map(
                (result) => result.file_path,
              );

              // For single file mode, just use the first result
              // For list mode, join with commas
              handleOnNewValue({
                value: isList ? fileNames : fileNames[0],
                file_path: isList ? filePaths : filePaths[0],
              });
            }
          })
          .catch((e) => {
            console.error(e);
            // Error handling is done in the onError callback above
          });
      },
    );
  };

  const isDisabled = disabled || isPending;

  const { data: files } = useGetFilesV2({
    enabled: !!ENABLE_FILE_MANAGEMENT,
  });
  const { data: knowledgeBases } = useGetKnowledgeBases({
    enabled: !!ENABLE_FILE_MANAGEMENT,
  });

  const selectedFiles = (
    isList
      ? Array.isArray(file_path)
        ? file_path.filter((value) => value !== "")
        : typeof file_path === "string"
          ? [file_path]
          : []
      : Array.isArray(file_path)
        ? (file_path ?? [])
        : [file_path ?? ""]
  ).filter((value) => value !== "");

  const selectedKnowledgeBaseNames = useMemo(() => {
    if (!files || !knowledgeBases) return [];
    const kbIds = new Set(
      files
        .filter((file) => selectedFiles.includes(file.path))
        .map((file) => file.knowledge_base_id)
        .filter((kbId): kbId is string => typeof kbId === "string"),
    );
    return knowledgeBases
      .filter((kb) => kbIds.has(kb.id))
      .map((kb) => kb.name);
  }, [files, knowledgeBases, selectedFiles]);

  const applyKnowledgeBaseSelection = (kbIds: string[]) => {
    if (!files || !knowledgeBases) return;
    const scopedFiles = files.filter(
      (file) => file.knowledge_base_id && kbIds.includes(file.knowledge_base_id),
    );
    const filePaths = scopedFiles.map((file) => file.path);
    const kbNames = knowledgeBases
      .filter((kb) => kbIds.includes(kb.id))
      .map((kb) => kb.name);

    handleOnNewValue({
      value: isList ? kbNames : (kbNames[0] ?? ""),
      file_path: isList ? filePaths : (filePaths[0] ?? ""),
    });
  };

  useEffect(() => {
    if (files !== undefined && !tempFile) {
      const validSelectedFiles = files.filter((f) => selectedFiles.includes(f.path));
      if (validSelectedFiles.length === selectedFiles.length) return;

      handleOnNewValue({
        value: isList ? selectedKnowledgeBaseNames : (selectedKnowledgeBaseNames[0] ?? ""),
        file_path: isList ? validSelectedFiles.map((f) => f.path) : (validSelectedFiles[0]?.path ?? ""),
      });
    }
  }, [files, file_path, selectedFiles, selectedKnowledgeBaseNames, isList]);

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5">
          {ENABLE_FILE_MANAGEMENT && !tempFile ? (
            files && (
              <div className="relative flex w-full flex-col gap-2">
                <div className="nopan nowheel flex max-h-44 flex-col overflow-y-auto">
                  <FilesRendererComponent
                    files={files.filter((file) =>
                      selectedFiles.includes(file.path),
                    )}
                    handleRemove={(path) => {
                      const newSelectedFiles = selectedFiles.filter(
                        (file) => file !== path,
                      );
                      handleOnNewValue({
                        value: isList
                          ? newSelectedFiles.map(
                              (file) =>
                                files.find((f) => f.path === file)?.name,
                            )
                          : (files.find((f) => f.path == newSelectedFiles[0]) ??
                            ""),
                        file_path: isList
                          ? newSelectedFiles
                          : (newSelectedFiles[0] ?? ""),
                      });
                    }}
                  />
                </div>
                <BaseModal
                  size="small"
                  open={isKnowledgeBaseModalOpen}
                  setOpen={setIsKnowledgeBaseModalOpen}
                  onSubmit={() => {
                    applyKnowledgeBaseSelection(selectedKnowledgeBaseIds);
                    setIsKnowledgeBaseModalOpen(false);
                  }}
                >
                  <BaseModal.Header description="Select one or more knowledge bases.">
                    Select Knowledge Base
                  </BaseModal.Header>
                  <BaseModal.Content className="gap-2 overflow-auto">
                    {(knowledgeBases ?? []).map((kb) => {
                      const isSelected = selectedKnowledgeBaseIds.includes(kb.id);
                      return (
                        <button
                          key={kb.id}
                          type="button"
                          className={cn(
                            "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left",
                            isSelected && "border-primary bg-muted/40",
                          )}
                          onClick={() => {
                            if (isList) {
                              setSelectedKnowledgeBaseIds((prev) =>
                                isSelected
                                  ? prev.filter((id) => id !== kb.id)
                                  : [...prev, kb.id],
                              );
                            } else {
                              setSelectedKnowledgeBaseIds(
                                isSelected ? [] : [kb.id],
                              );
                            }
                          }}
                        >
                          <span className="font-medium">{kb.name}</span>
                          {isSelected && (
                            <ForwardedIconComponent name="Check" className="h-4 w-4" />
                          )}
                        </button>
                      );
                    })}
                    {(knowledgeBases ?? []).length === 0 && (
                      <div className="text-sm text-muted-foreground">
                        No knowledge bases available.
                      </div>
                    )}
                  </BaseModal.Content>
                  <BaseModal.Footer
                    submit={{
                      label: "Select",
                      disabled: selectedKnowledgeBaseIds.length === 0,
                      dataTestId: "select-knowledge-base-modal-button",
                    }}
                  />
                </BaseModal>
                {(selectedFiles.length === 0 || isList) && (
                  <div data-testid="input-file-component" className="w-full">
                    <Button
                      disabled={isDisabled}
                      onClick={() => {
                        const existingKbIds =
                          files
                            ?.filter((f) => selectedFiles.includes(f.path))
                            .map((f) => f.knowledge_base_id)
                            .filter((kbId): kbId is string => !!kbId) ?? [];
                        setSelectedKnowledgeBaseIds(Array.from(new Set(existingKbIds)));
                        setIsKnowledgeBaseModalOpen(true);
                      }}
                      variant={selectedFiles.length !== 0 ? "ghost" : "default"}
                      size={selectedFiles.length !== 0 ? "iconMd" : "default"}
                      className={cn(
                        selectedFiles.length !== 0
                          ? "hit-area-icon absolute -top-8 right-0"
                          : "w-full",
                        "font-semibold",
                      )}
                      data-testid="button_open_file_management"
                    >
                      {selectedFiles.length !== 0 ? (
                        <ForwardedIconComponent
                          name="Plus"
                          className="icon-size"
                          strokeWidth={ICON_STROKE_WIDTH}
                        />
                      ) : (
                        <div>Select knowledge base{isList ? "s" : ""}</div>
                      )}
                    </Button>
                  </div>
                )}
              </div>
            )
          ) : (
            <div className="relative flex w-full">
              <div className="w-full">
                <input
                  data-testid="input-file-component"
                  type="text"
                  className={cn(
                    "primary-input h-9 w-full cursor-pointer rounded-r-none text-sm focus:border-border focus:outline-none focus:ring-0",
                    !value && "text-placeholder-foreground",
                    editNode && "h-6",
                  )}
                  value={value || "Upload a file..."}
                  readOnly
                  disabled={isDisabled}
                  onClick={handleButtonClick}
                />
              </div>
              <div>
                <Button
                  className={cn(
                    "h-9 w-9 rounded-l-none",
                    value &&
                      "bg-accent-emerald-foreground ring-accent-emerald-foreground hover:bg-accent-emerald-foreground",
                    isDisabled &&
                      "relative top-[1px] h-9 ring-1 ring-border ring-offset-0 hover:ring-border",
                    editNode && "h-6",
                  )}
                  onClick={handleButtonClick}
                  disabled={isDisabled}
                  size="icon"
                  data-testid="button_upload_file"
                >
                  <IconComponent
                    name={value ? "CircleCheckBig" : "Upload"}
                    className={cn(
                      value && "text-background",
                      isDisabled && "text-muted-foreground",
                      "h-4 w-4",
                    )}
                    strokeWidth={2}
                  />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
