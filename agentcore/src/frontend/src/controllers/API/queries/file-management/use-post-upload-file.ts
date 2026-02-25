import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FileType } from "@/types/file_management";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
  knowledgeBaseName?: string;
  visibility?: string;
}

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.knowledgeBaseName) {
      formData.append("knowledge_base_name", payload.knowledgeBaseName);
    }
    if (payload.visibility) {
      formData.append("visibility", payload.visibility);
    }
    const data = new Date().toISOString().split("Z")[0];

    const newFile = {
      id: "temp",
      name: payload.file.name.split(".").slice(0, -1).join("."),
      path: payload.file.name,
      size: payload.file.size,
      file: payload.file,
      updated_at: data,
      created_at: data,
      progress: 0,
    };
    queryClient.setQueryData(["useGetFilesV2"], (old: FileType[]) => {
      return [...old.filter((file) => file.id !== "temp"), newFile];
    });

    try {
      const response = await api.post<any>(
        `${getURL("FILE_MANAGEMENT", {}, true)}`,
        formData,
        {
          onUploadProgress: (progressEvent) => {
            if (progressEvent.progress) {
              queryClient.setQueryData(["useGetFilesV2"], (old: any) => {
                return old.map((file: any) => {
                  if (file?.id === "temp") {
                    return { ...file, progress: progressEvent.progress };
                  }
                  return file;
                });
              });
            }
          },
        }
      );
      console.log(response, "<<< response");
      return response.data;
    } catch (error: any) {
      const status = error?.response?.status;
      console.log(status, error);
      // Permission denied → REMOVE temp file
      if (status === 403) {
        queryClient.setQueryData(["useGetFilesV2"], (old: FileType[] = []) => {
          return old.filter((file) => file.id !== "temp");
        });
      } else {
        // Other errors → mark failed
        queryClient.setQueryData(["useGetFilesV2"], (old: FileType[] = []) => {
          return old.map((file: any) => {
            if (file?.id === "temp") {
              return { ...file, progress: -1 };
            }
            return file;
          });
        });
      }

      // Always throw a SAFE error shape
      throw {
        status,
        message:
          error?.response?.data?.detail ??
          error?.response?.data?.message ??
          "Upload failed",
      };
    }
  };

  const mutation: UseMutationResult<IPostUploadFile, any, IPostUploadFile> =
    mutate(
      ["usePostUploadFileV2"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
      {
        onSettled: (data, error, variables, context) => {
          if (!error) {
            queryClient.invalidateQueries({
              queryKey: ["useGetFilesV2"],
            });
            queryClient.invalidateQueries({
              queryKey: ["useGetKnowledgeBases"],
            });
          }
          options?.onSettled?.(data, error, variables, context);
        },
        retry: 0,
        ...options,
      }
    );

  return mutation;
};
