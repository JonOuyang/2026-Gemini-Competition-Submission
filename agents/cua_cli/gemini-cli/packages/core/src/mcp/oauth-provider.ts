/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: OAuth provider for MCP servers.
 * OAuth functionality removed for CLOVIS integration - API key only.
 */

export interface MCPOAuthConfig {
  enabled?: boolean;
  authorizationUrl?: string;
  tokenUrl?: string;
  scopes?: string[];
  clientId?: string;
}

export class MCPOAuthProvider {
  constructor(_storage: MCPOAuthTokenStorage) {}

  async authenticate(
    _serverName: string,
    _config: MCPOAuthConfig,
    _serverUrl?: string,
  ): Promise<void> {
    throw new Error('OAuth not supported in CLOVIS CLI integration');
  }

  async getValidToken(
    _serverName: string,
    _config?: MCPOAuthConfig,
  ): Promise<string | null> {
    return null;
  }
}

// Re-export the token storage for import compatibility
export class MCPOAuthTokenStorage {
  async getCredentials(_serverName: string): Promise<null> {
    return null;
  }

  async storeCredentials(
    _serverName: string,
    _credentials: unknown,
  ): Promise<void> {}

  async deleteCredentials(_serverName: string): Promise<void> {}
}
