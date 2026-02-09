/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: Types for code_assist server.
 * Code assist functionality removed for CLOVIS integration.
 */

export type UserTierId = 'free' | 'paid' | 'enterprise';

export interface RetrieveUserQuotaResponse {
  buckets?: Array<{ modelId: string; remaining?: number }>;
}

export interface AdminControlsSettings {
  disabledTools?: string[];
  disabledCommands?: string[];
}
