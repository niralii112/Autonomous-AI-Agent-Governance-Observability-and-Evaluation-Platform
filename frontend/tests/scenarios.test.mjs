import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { after, before, test } from "node:test";
import { setupServer } from "msw/node";
import { createServer } from "vite";

const api = "http://localhost:8000/api/v1";
const catalog = JSON.parse(await readFile(
  new URL("../../contracts/examples/scenarios/scenario-catalog.json", import.meta.url), "utf8"
));
let server;
let vite;

before(async () => {
  vite = await createServer({ server: { middlewareMode: true, ws: false } });
  const { handlers } = await vite.ssrLoadModule("/src/mocks/handlers.ts");
  const { platformHandlers } = await vite.ssrLoadModule("/src/mocks/platformHandlers.ts");
  const { scenarioHandlers } = await vite.ssrLoadModule("/src/mocks/scenarioHandlers.ts");
  const { extendedHandlers } = await vite.ssrLoadModule("/src/mocks/extendedHandlers.ts");
  server = setupServer(...handlers, ...platformHandlers, ...scenarioHandlers, ...extendedHandlers);
  server.listen({ onUnhandledRequest: "error" });
});

after(async () => {
  server?.close();
  await vite?.close();
});

function request(path, token, body) {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (body !== undefined) headers.set("Content-Type", "application/json");
  return fetch(api + path, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function json(response, status = 200) {
  const body = await response.json();
  assert.equal(response.status, status, JSON.stringify(body));
  return body;
}

async function login(role) {
  const result = await json(await request("/auth/login", undefined, {
    username: `demo_${role}`,
    password: "demo123",
  }));
  assert.equal(result.user.role, role.toUpperCase());
  return result.access_token;
}

test("admin and operator can run the documented fixtures, and both action endpoints show the decision", async () => {
  const { items: agents } = await json(await request("/agents"));
  const cases = [["admin", "FINANCE"], ["operator", "CUSTOMER_SUPPORT"]];
  const outcomes = new Set();
  for (const [role, category] of cases) {
    const token = await login(role);
    const agent = agents.find((item) => item.agent_category === category);
    const path = `/agents/${agent.agent_id}`;
    const expected = catalog.scenarios.filter((item) => item.agent_category === category);
    const list = await json(await request(path + "/scenarios", token));
    assert.equal(list.agent_id, agent.agent_id);
    assert.deepEqual(list.scenarios.map((item) => item.scenario_key), expected.map((item) => item.scenario_key));

    for (const [index, scenario] of expected.entries()) {
      assert.equal(list.scenarios[index].expected_decision, scenario.expected_decision_ml_model);
      const response = await json(await request(path + "/runs", token, { scenario_key: scenario.scenario_key }));
      assert.equal(response.scenario_key, scenario.scenario_key);
      assert.equal(response.agent_id, agent.agent_id);
      const { action, governance_decision: decision, approval, execution } = response.submission;
      assert.equal(decision.final_decision, scenario.expected_decision_ml_model);
      outcomes.add(decision.final_decision);
      assert.equal(decision.decision_reason_code, "MOCK_SCENARIO");
      assert.equal(approval, null);
      assert.equal(execution, null);
      const detail = await json(await request(`/actions/${action.action_id}`, token));
      assert.deepEqual(detail.action, action);
      assert.deepEqual(detail.governance_decisions, [decision]);
      const activity = await json(await request(`/actions?agent_id=${agent.agent_id}&page_size=1`, token));
      assert.equal(activity.items[0].action_id, action.action_id);
      assert.equal(activity.items[0].final_decision, decision.final_decision);
      assert.equal(activity.total_items, index + 2, "The existing sample action is still counted");
      assert.equal(activity.total_pages, activity.total_items);
    }
  }
  assert.deepEqual(outcomes, new Set(["ALLOW", "BLOCK", "HUMAN_REVIEW"]));
});

test("both scenario endpoints reject unauthenticated and unauthorized callers", async () => {
  const { items } = await json(await request("/agents"));
  const path = `/agents/${items[0].agent_id}`;
  for (const [token, status, code] of [
    [undefined, 401, "AUTH_MISSING_CREDENTIALS"],
    ["forged", 401, "AUTH_TOKEN_INVALID"],
    [await login("viewer"), 403, "AUTH_INSUFFICIENT_ROLE"],
    [await login("reviewer"), 403, "AUTH_INSUFFICIENT_ROLE"],
  ]) {
    const get = await json(await request(path + "/scenarios", token), status);
    const post = await json(await request(path + "/runs", token, { scenario_key: "finance.report.get" }), status);
    assert.equal(get.error_code, code);
    assert.equal(post.error_code, code);
  }
});

test("invalid requests create no actions and repeated run keys reuse the original action", async () => {
  const token = await login("operator");
  const { items } = await json(await request("/agents"));
  const path = `/agents/${items[0].agent_id}`;
  const before = await json(await request("/actions", token));
  await json(await request("/agents/unknown/scenarios", token), 404);
  await json(await request("/agents/unknown/runs", token, { scenario_key: "finance.report.get" }), 404);
  await json(await request(path + "/runs", token, {}), 422);
  await json(await request(path + "/runs", token, { scenario_key: "support.ticket.get" }), 404);

  const body = { scenario_key: "finance.report.get", idempotency_key: "retry-example" };
  const replies = await Promise.all([request(path + "/runs", token, body), request(path + "/runs", token, body)]);
  const [first, second] = await Promise.all(replies.map((response) => json(response)));
  assert.equal(first.submission.action.action_id, second.submission.action.action_id);
  assert.notEqual(first.submission.duplicate, second.submission.duplicate);
  await json(await request(path + "/runs", token, { ...body, scenario_key: "finance.report.restricted" }), 422);
  const after = await json(await request("/actions", token));
  assert.equal(after.total_items, before.total_items + 1);
});
