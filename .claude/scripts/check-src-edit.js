#!/usr/bin/env node
/**
 * PreToolUse hook to remind about dev-tracker when editing src/ files.
 * Triggers on Edit/Write operations targeting ./src folder.
 */

let inputData = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  inputData += chunk;
});

process.stdin.on('end', () => {
  try {
    const input = JSON.parse(inputData);
    const toolName = input.tool_name || '';
    const toolInput = input.tool_input || {};

    // Get the file path from the tool input
    const filePath = toolInput.file_path || toolInput.path || '';

    // Check if editing/writing to src/ folder
    const isSrcFile = filePath.includes('/src/') ||
                      filePath.includes('\\src\\') ||
                      filePath.startsWith('src/') ||
                      filePath.startsWith('src\\');

    // Skip if not a src file
    if (!isSrcFile) {
      process.exit(0);
    }

    // Check if dev-tracker was already invoked in this session
    // We can't easily track this, so we just remind every time
    // The reminder is helpful as a safety net

    console.log('<pre-tool-use-hook>');
    console.log('⚠️ EDITING SOURCE FILE');
    console.log('');
    console.log('If you haven\'t already, invoke /dev-tracker to track this work.');
    console.log('File: ' + filePath);
    console.log('</pre-tool-use-hook>');

    process.exit(0);
  } catch (e) {
    // Silent fail - don't block edits
    process.exit(0);
  }
});
