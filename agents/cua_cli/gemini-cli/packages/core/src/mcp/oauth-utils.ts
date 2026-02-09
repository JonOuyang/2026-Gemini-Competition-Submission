/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: OAuth utilities for MCP servers.
 * OAuth functionality removed for CLOVIS integration.
 */

export interface OAuthAuthorizationServerMetadata {
  authorization_endpoint?: string;
  token_endpoint?: string;
}

export interface OAuthProtectedResourceMetadata {
  authorization_servers?: string[];
}

export interface DiscoveredOAuthConfig {
  authorizationUrl: string;
  tokenUrl: string;
  scopes?: string[];
}

export class OAuthUtils {
  static parseWWWAuthenticateHeader(_header: string): string | null {
    return null;
  }

  static async discoverOAuthConfig(
    _baseUrl: string,
  ): Promise<DiscoveredOAuthConfig | null> {
    return null;
  }
}
