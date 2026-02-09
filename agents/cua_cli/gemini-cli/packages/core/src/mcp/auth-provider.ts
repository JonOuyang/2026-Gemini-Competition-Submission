/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: Minimal auth provider interface for MCP servers.
 * OAuth functionality removed for CLOVIS integration - API key only.
 */
export interface McpAuthProvider {
  getRequestHeaders?(): Promise<Record<string, string>>;
}
