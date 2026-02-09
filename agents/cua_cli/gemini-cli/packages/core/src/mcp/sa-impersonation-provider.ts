/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: Service account impersonation provider for MCP servers.
 * Service account auth functionality removed for CLOVIS integration.
 */

import type { MCPServerConfig } from '../config/config.js';
import type { McpAuthProvider } from './auth-provider.js';

export class ServiceAccountImpersonationProvider implements McpAuthProvider {
  constructor(_config: MCPServerConfig) {}

  async getRequestHeaders(): Promise<Record<string, string>> {
    return {};
  }
}
