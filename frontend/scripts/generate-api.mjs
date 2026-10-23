
import fs from "node:fs";
import path from "node:path";

const contractPath = path.resolve(
    "../contracts/openapi.yaml"
);

const outputPath = path.resolve(
    "src/api/operations.ts"
);

const source = fs.readFileSync(contractPath, "utf8");

const operationIds = [
    ...source.matchAll(
        /^\s+operationId:\s*["']?([A-Za-z0-9_]+)/gm
    ),
].map((match) => match[1]);

const uniqueIds = [...new Set(operationIds)];

if (operationIds.length !== 55 || uniqueIds.length !== 55) {
    throw new Error(
        `Expected 55 unique operations, found ${operationIds.length} entries and ${uniqueIds.length} unique IDs.`
    );
}

const generated = `/**
 * Auto-generated operation registry.
 * Source: contracts/openapi.yaml
 * Do not edit manually.
 */

export const operationIds = ${JSON.stringify(
    uniqueIds,
    null,
    2
)} as const;

export type OperationId =
  (typeof operationIds)[number];
`;

fs.writeFileSync(outputPath, generated);

console.log(
    `Generated registry for ${uniqueIds.length} API operations.`
);
