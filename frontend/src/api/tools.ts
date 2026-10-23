import { listTools, getTool, createTool, updateTool } from "./generated-services";
import type { components } from "../types/generated/api";

export type ToolCreateParams = components["schemas"]["ToolCreateRequest"];
export type ToolUpdateParams = components["schemas"]["ToolUpdateRequest"];

export async function fetchTools(page = 1, pageSize = 25) {
  const { data, error } = await listTools({
    params: {
      query: {
        page,
        page_size: pageSize,
      },
    },
  });

  if (error) {
    throw new Error("Unable to fetch tools list.");
  }
  return data;
}

export async function fetchToolById(toolId: string) {
  const { data, error } = await getTool({
    params: {
      path: { tool_id: toolId },
    },
  });

  if (error) {
    throw new Error("Unable to fetch tool details.");
  }
  return data;
}

export async function postCreateTool(body: ToolCreateParams) {
  const { data, error } = await createTool({
    body,
  });

  if (error) {
    throw new Error("Failed to create tool.");
  }
  return data;
}

export async function patchUpdateTool(toolId: string, body: ToolUpdateParams) {
  const { data, error } = await updateTool({
    params: {
      path: { tool_id: toolId },
    },
    body,
  });

  if (error) {
    throw new Error("Failed to update tool.");
  }
  return data;
}
