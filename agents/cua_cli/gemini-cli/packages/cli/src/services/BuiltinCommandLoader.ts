/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { ICommandLoader } from './types.js';
import type { SlashCommand } from '../ui/commands/types.js';
import { initCommand } from '../ui/commands/initCommand.js';
import type { Config } from '@google/gemini-cli-core';

/**
 * Loads a minimal set of built-in slash commands for headless mode.
 */
export class BuiltinCommandLoader implements ICommandLoader {
  constructor(_config: Config | null) {}

  async loadCommands(_signal: AbortSignal): Promise<SlashCommand[]> {
    return [initCommand];
  }
}
