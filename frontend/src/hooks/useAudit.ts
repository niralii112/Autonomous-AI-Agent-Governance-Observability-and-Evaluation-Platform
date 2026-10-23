import { useQuery } from "@tanstack/react-query";
import { listAuditEvents, getAuditEvent } from "../api/generated-services";

export function useAuditEvents(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: ["audit", "events", page, pageSize],
    queryFn: async () => {
      const { data, error } = await listAuditEvents({
        params: {
          query: { page, page_size: pageSize },
        },
      });
      if (error) throw new Error("Failed to load audit events.");
      return data;
    },
  });
}

export function useAuditEvent(eventId: string) {
  return useQuery({
    queryKey: ["audit", "event", eventId],
    queryFn: async () => {
      const { data, error } = await getAuditEvent({
        params: {
          path: { audit_event_id: eventId },
        },
      });
      if (error) throw new Error("Failed to load audit event details.");
      return data;
    },
    enabled: Boolean(eventId && eventId.trim().length > 0),
  });
}
