/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { loadCliConfig, parseArguments } from './config/config.js';
import { loadSettings } from './config/settings.js';
import { runNonInteractive } from './nonInteractiveCli.js';
import { runExitCleanup } from './utils/cleanup.js';
import {
  ExitCodes,
  UserPromptEvent,
  debugLogger,
  logUserPrompt,
  sessionId,
} from '@google/gemini-cli-core';
import { validateNonInteractiveAuth } from './validateNonInteractiveAuth.js';

export async function main() {
  const settings = loadSettings();
  const argv = await parseArguments(settings.merged);

  const input = argv.prompt ?? (argv.query?.length ? argv.query.join(' ') : '');
  if (!input) {
    debugLogger.error(
      'No input provided. Use --prompt or pass a query argument.',
    );
    await runExitCleanup();
    process.exit(ExitCodes.FATAL_INPUT_ERROR);
  }

  const currentSessionId =
    typeof sessionId === 'function' ? sessionId() : sessionId;
  const config = await loadCliConfig(settings.merged, currentSessionId, argv, {
    cwd: process.cwd(),
  });

  const prompt_id = Math.random().toString(16).slice(2);
  logUserPrompt(
    config,
    new UserPromptEvent(
      input.length,
      prompt_id,
      config.getContentGeneratorConfig()?.authType,
      input,
    ),
  );

  const authType = await validateNonInteractiveAuth(
    settings.merged.security.auth.selectedType,
    settings.merged.security.auth.useExternal,
  );
  await config.refreshAuth(authType);
  await config.initialize();

  await runNonInteractive({
    config,
    settings,
    input,
    prompt_id,
  });

  await runExitCleanup();
  process.exit(ExitCodes.SUCCESS);
}
