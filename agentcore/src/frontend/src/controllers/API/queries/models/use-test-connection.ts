import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import type {
  TestConnectionRequest,
  TestConnectionResponse,
} from "@/types/models/models";

export const useTestModelConnection = () => {
  return useMutation<TestConnectionResponse, Error, TestConnectionRequest>({
    mutationFn: async (data) => {
      const response = await api.post(
        "api/models/registry/test-connection",
        data,
      );
      return response.data;
    },
  });
};