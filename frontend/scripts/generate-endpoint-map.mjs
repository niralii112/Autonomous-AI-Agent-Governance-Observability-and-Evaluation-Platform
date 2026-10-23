import fs from "node:fs";

const source = fs.readFileSync(
  "src/types/generated/api.d.ts",
  "utf8"
);

const pathSection = source.split(
  "export interface paths {"
)[1]?.split("export interface webhooks")[0];

if (!pathSection) {
  throw new Error("Could not locate generated paths.");
}

const matches = [
  ...pathSection.matchAll(
    /^\s{4}"([^"]+)":\s*\{/gm
  ),
];

console.log("Generated paths:", matches.length);

const output = matches.map((match) => {
  const start = match.index;
  const next = pathSection.indexOf(
    "\n    };\n",
    start
  );

  const block = pathSection.slice(
    start,
    next === -1 ? undefined : next + 7
  );

  const methods = [
    ...block.matchAll(
      /^\s{8}(get|post|put|patch|delete):\s*operations\["([^"]+)"\]/gm
    ),
  ];

  return {
    path: match[1],
    methods: methods.map((m) => ({
      method: m[1].toUpperCase(),
      operationId: m[2],
    })),
  };
});

fs.writeFileSync(
  "api-endpoint-map.json",
  JSON.stringify(output, null, 2)
);

console.log(
  "Endpoint map saved to api-endpoint-map.json"
);
