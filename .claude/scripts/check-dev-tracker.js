#!/usr/bin/env node
/**
 * Hook script to enforce dev-tracker invocation for implementation tasks.
 * Called by UserPromptSubmit hook - reads JSON from stdin.
 */

let inputData = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  inputData += chunk;
});

process.stdin.on('end', () => {
  try {
    const input = JSON.parse(inputData);
    const prompt = input.prompt || '';
    const lowerPrompt = prompt.toLowerCase();

    // Keywords that indicate implementation work
    const implementationKeywords = [
      // Direct action words
      'fix',
      'implement',
      'refactor',
      'build',
      'develop',
      'create',
      'add',
      'remove',
      'delete',
      'update',
      'modify',
      'change',
      'write',
      // Problem indicators
      'bug',
      'broken',
      'error',
      'issue',
      'problem',
      'failing',
      "doesn't work",
      'not working',
      // Task phrases
      'execute plan',
      'start task',
      'begin work',
      'work on',
      'continue with',
      'finish',
      'complete',
      // UI/styling work (catches "center this div" type prompts)
      'center',
      'align',
      'style',
      'css',
      'styling',
      'layout',
      'margin',
      'padding',
      'flex',
      'grid',
      'responsive',
      'mobile',
      'desktop',
      'breakpoint',
      'color',
      'font',
      'spacing',
      'border',
      'shadow',
      'hover',
      'animation',
      'transition',
      // Component work
      'component',
      'button',
      'form',
      'input',
      'modal',
      'dropdown',
      'menu',
      'navbar',
      'sidebar',
      'footer',
      'header',
      'card',
      'table',
      'list',
      // Screenshot/visual context
      'screenshot',
      'make it look',
      'looks like',
      'should look',
      'adjust',
      'tweak',
      'move',
      'resize',
      'position',
    ];

    // Exclusions - prompts that should NOT trigger dev-tracker
    const exclusionKeywords = [
      'what is',
      'how does',
      'explain',
      'show me',
      'list',
      'find',
      'search',
      'where is',
      'why',
      'can you tell',
      'help me understand',
      '/dev-tracker', // Already invoking it
      'dev-tracker',
      'commit',
      '/commit',
      'status',
      'git status',
      'test the hook',
      'hook works',
    ];

    // Check if prompt is excluded (questions, research, already using dev-tracker)
    const isExcluded = exclusionKeywords.some((keyword) =>
      lowerPrompt.includes(keyword)
    );

    // Check if prompt contains implementation keywords
    const isImplementation = implementationKeywords.some((keyword) =>
      lowerPrompt.includes(keyword)
    );

    // Check if user is invoking a skill (starts with /)
    const skillInvocation = prompt.match(/^\/(\S+)/);

    // Skills that are part of dev-tracker or don't need tracking
    const skipSkills = [
      'dev-tracker', 'task-status', 'tasks', 'backlog', 'backlog-add',
      'help', 'clear', 'config', 'settings', 'memory', 'forget'
    ];

    // Any skill invocation (except skip list) should trigger dev-tracker
    const isSkillCall = skillInvocation && !skipSkills.includes(skillInvocation[1]);

    // Trigger if: ANY skill invoked (except skip list) OR implementation keywords detected (unless excluded)
    const shouldTrigger = isSkillCall || (isImplementation && !isExcluded);

    if (shouldTrigger) {
      console.log('<user-prompt-submit-hook>');

      if (isSkillCall) {
        // User is calling another skill - need to run dev-tracker first
        console.log('⚠️ SKILL INVOCATION DETECTED: /' + skillInvocation[1]);
        console.log('');
        console.log('BLOCKING REQUIREMENT: You MUST invoke dev-tracker FIRST.');
        console.log('');
        console.log('Execute in this order:');
        console.log('1. FIRST: Invoke skill "dev-tracker" (check for existing task or create one)');
        console.log('2. THEN: Proceed with /' + skillInvocation[1]);
        console.log('');
        console.log('Do NOT skip step 1. Run dev-tracker before the requested skill.');
      } else {
        console.log('⚠️ IMPLEMENTATION TASK DETECTED');
        console.log('');
        console.log(
          'MANDATORY: Invoke /dev-tracker skill IMMEDIATELY before any implementation work.'
        );
        console.log('This tracks progress across sessions and prevents conflicts.');
        console.log('');
        console.log(
          'Do this now: Use the Skill tool to invoke "dev-tracker" before proceeding.'
        );
      }

      console.log('</user-prompt-submit-hook>');
    }

    process.exit(0);
  } catch (e) {
    // If JSON parsing fails, try reading from command line for backwards compatibility
    const prompt = process.argv[2] || '';
    const lowerPrompt = prompt.toLowerCase();

    const implementationKeywords = [
      'fix',
      'implement',
      'refactor',
      'build',
      'add',
      'remove',
      'update',
      'modify',
      'change',
      'bug',
      'broken',
      'error',
    ];

    const isImplementation = implementationKeywords.some((keyword) =>
      lowerPrompt.includes(keyword)
    );

    if (isImplementation) {
      console.log('<user-prompt-submit-hook>');
      console.log('⚠️ IMPLEMENTATION TASK DETECTED - Invoke /dev-tracker first');
      console.log('</user-prompt-submit-hook>');
    }

    process.exit(0);
  }
});
