/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: Google credential provider for MCP servers.
 * Google OAuth functionality removed for CLOVIS integration.
 */

import type { MCPServerConfig } from '../config/config.js';
import type { McpAuthProvider } from './auth-provider.js';

export class GoogleCredentialProvider implements McpAuthProvider {
  constructor(_config: MCPServerConfig) {}

  async getRequestHeaders(): Promise<Record<string, string>> {
    return {};
  }
}
