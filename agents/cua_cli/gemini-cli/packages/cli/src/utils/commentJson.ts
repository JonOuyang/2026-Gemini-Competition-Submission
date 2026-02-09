/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { promises as fs } from 'node:fs';

export async function updateSettingsFilePreservingFormat(
  filePath: string,
  data: unknown,
): Promise<void> {
  const json = JSON.stringify(data, null, 2) + '\n';
  await fs.writeFile(filePath, json, 'utf-8');
}
