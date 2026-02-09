/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  type PolicyEngineConfig,
  type ApprovalMode,
  type PolicyEngine,
  type MessageBus,
  type PolicySettings,
  type PolicyRule,
  PolicyDecision,
  SHELL_TOOL_NAME,
  createPolicyEngineConfig as createCorePolicyEngineConfig,
  createPolicyUpdater as createCorePolicyUpdater,
} from '@google/gemini-cli-core';
import { type Settings } from './settings.js';

const CLOVIS_PERMISSIVE_POLICY_ENV = 'CLOVIS_CLI_PERMISSIVE_POLICY';

function isTruthyEnv(value: string | undefined): boolean {
  if (!value) {
    return false;
  }

  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes';
}

function getDangerousShellCommandRules(): PolicyRule[] {
  const denyMessage =
    'Blocked dangerous shell command in permissive mode.';

  // These patterns are matched against stringified tool-call args.
  const dangerousCommandPatterns: RegExp[] = [
    /\bsudo\b/i,
    /\brm\s+-[^\n"]*r[^\n"]*f[^\n"]*\s+(?:\/(?:\s|$|")|~(?:\/|$)|\$HOME(?:\/|$)|\/Users\/|\/System\/|\/Library\/|\/Applications\/)/i,
    /\bdd\b[^\n"]*\bof=\/dev\//i,
    /\bmkfs(?:\.[a-z0-9_]+)?\b/i,
    /\b(?:fdisk|sfdisk|parted)\b/i,
    /\bdiskutil\s+erase/i,
    /\b(?:shutdown|reboot|halt|poweroff)\b/i,
    /\bkill\s+-9\s+1\b/i,
    /:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:/,
    /\b(?:curl|wget)\b[^\n"]*\|\s*(?:sh|bash|zsh)\b/i,
    /\bgit\s+reset\s+--hard\b/i,
    /\bgit\s+clean\s+-fdx\b/i,
    /\bgit\s+push\b[^\n"]*--force(?:-with-lease)?\b/i,
    /\bchmod\b[^\n"]*-R[^\n"]*777[^\n"]*\s+\/(?:\s|$|")/i,
    /\bchown\b[^\n"]*-R[^\n"]*\s+\/(?:\s|$|")/i,
  ];

  return dangerousCommandPatterns.map((argsPattern, index) => ({
    name: `clovis-permissive-dangerous-shell-${index + 1}`,
    toolName: SHELL_TOOL_NAME,
    argsPattern,
    decision: PolicyDecision.DENY,
    denyMessage,
    priority: 10000,
    source: 'CLOVIS (Permissive Dangerous Command Blocklist)',
  }));
}

export async function createPolicyEngineConfig(
  settings: Settings,
  approvalMode: ApprovalMode,
): Promise<PolicyEngineConfig> {
  // Explicitly construct PolicySettings from Settings to ensure type safety
  // and avoid accidental leakage of other settings properties.
  const policySettings: PolicySettings = {
    mcp: settings.mcp,
    tools: settings.tools,
    mcpServers: settings.mcpServers,
  };

  const coreConfig = await createCorePolicyEngineConfig(
    policySettings,
    approvalMode,
  );

  if (!isTruthyEnv(process.env[CLOVIS_PERMISSIVE_POLICY_ENV])) {
    return coreConfig;
  }

  return {
    ...coreConfig,
    // Allow all tools by default. We only deny explicitly dangerous shell commands.
    defaultDecision: PolicyDecision.ALLOW,
    rules: getDangerousShellCommandRules(),
    // Remove legacy safety checkers that can still deny in headless mode.
    checkers: [],
  };
}

export function createPolicyUpdater(
  policyEngine: PolicyEngine,
  messageBus: MessageBus,
) {
  return createCorePolicyUpdater(policyEngine, messageBus);
}
