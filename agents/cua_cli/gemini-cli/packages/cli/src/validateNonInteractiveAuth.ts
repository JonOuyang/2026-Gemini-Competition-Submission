/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { AuthType } from '@google/gemini-cli-core';

export async function validateNonInteractiveAuth(
  selectedType: string | undefined,
  useExternal: boolean | undefined,
): Promise<AuthType> {
  if (useExternal && selectedType) {
    return selectedType as AuthType;
  }

  if (selectedType) {
    return selectedType as AuthType;
  }

  if (process.env['GEMINI_API_KEY']) {
    return AuthType.USE_GEMINI;
  }

  throw new Error(
    'No auth method configured for non-interactive mode. Set GEMINI_API_KEY or select an auth type in settings.',
  );
}
