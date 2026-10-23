import {
  listActions,
  getAction,
  submitAction,
  retryAction,
} from "./generated-services";
import type { components } from "../types/generated/api";

export type ActionFilterParams = {
  agent_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
};

export async function fetchActions(params: ActionFilterParams = {}) {
  const { data, error } = await listActions({
    params: {
      query: {
        agent_id: params.agent_id,
        page: params.page ?? 1,
        page_size: params.page_size ?? 25,
      },
    },
  });

  if (error) {
    throw new Error("Unable to fetch actions list.");
  }
  return data;
}

export async function fetchActionById(actionId: string) {
  const { data, error } = await getAction({
    params: {
      path: { action_id: actionId },
    },
  });

  if (error) {
    throw new Error("Unable to fetch action details.");
  }
  return data;
}

export async function postActionRetry(actionId: string) {
  const { data, error } = await retryAction({
    params: {
      path: { action_id: actionId },
    },
  });

  if (error) {
    throw new Error("Action retry failed.");
  }
  return data;
}

export type ActionSubmission = components["schemas"]["ActionSubmissionRequest"];

export async function postSubmitAction(body: ActionSubmission) {
  const { data, error } = await submitAction({
    body,
  });

  if (error) {
    throw new Error("Action submission failed.");
  }
  return data;
}
