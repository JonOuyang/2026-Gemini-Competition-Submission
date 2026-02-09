/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Stub: Content converter for code assist server.
 * Code assist functionality removed for CLOVIS integration.
 */

import type { Content } from '@google/genai';

/**
 * Convert contents to a consistent format.
 * In the simplified version, this just ensures we have an array.
 */
export function toContents(
  contents: Content | Content[] | string | undefined,
): Content[] {
  if (!contents) {
    return [];
  }
  if (typeof contents === 'string') {
    return [{ role: 'user', parts: [{ text: contents }] }];
  }
  if (Array.isArray(contents)) {
    return contents;
  }
  return [contents];
}

/**
 * Convert parts to a consistent format.
 */
export function toParts(parts: unknown): unknown[] {
  if (!parts) {
    return [];
  }
  if (Array.isArray(parts)) {
    return parts;
  }
  return [parts];
}
