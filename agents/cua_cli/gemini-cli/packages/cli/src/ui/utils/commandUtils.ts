/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Checks if a query string potentially represents an '@' command.
 */
export const isAtCommand = (query: string): boolean =>
  query.startsWith('@') || /\s@/.test(query);

/**
 * Checks if a query string potentially represents an '/' command.
 */
export const isSlashCommand = (query: string): boolean => {
  if (!query.startsWith('/')) return false;
  if (query.startsWith('//')) return false;
  if (query.startsWith('/*')) return false;
  return true;
};
