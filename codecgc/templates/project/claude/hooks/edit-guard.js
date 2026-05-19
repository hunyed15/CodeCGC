#!/usr/bin/env node
// CodeCGC Edit Guard — PreToolUse hook (Edit|Write|MultiEdit)
// Routes file edits through model-routing.yaml policy.
// Zero external dependencies. Never crashes (try/catch -> exit(0)).

'use strict';

try {
  var fs = require('fs');
  var path = require('path');

  // ── Read stdin ──
  var inputData = '';
  if (!process.stdin.isTTY) {
    inputData = fs.readFileSync(0, 'utf-8');
  }
  if (!inputData.trim()) {
    process.exit(0);
  }

  var parsed = JSON.parse(inputData);
  var toolInput = parsed.tool_input || parsed.input || parsed;
  var toolName = (parsed.tool_name || '').trim();
  var filePath = (toolInput.file_path || toolInput.path || '').trim();

  if (!filePath) {
    process.exit(0);
  }

  // ── Find routing file ──
  var cwd = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  var routingPath = path.join(cwd, 'model-routing.yaml');

  if (!fs.existsSync(routingPath)) {
    process.exit(0);
  }

  // ── Parse YAML (simple, handles model-routing.yaml structure) ──
  var routingContent = fs.readFileSync(routingPath, 'utf-8');
  var sections = parseSimpleYaml(routingContent);

  // ── Classify path ──
  var normalizedPath = normalizePath(filePath, cwd);
  var owner = classifyPath(normalizedPath, sections);

  // ── Decide ──
  if (owner === 'orchestration' || owner === 'docs') {
    process.exit(0);
  }

  var ownerLabel = owner || 'unknown';
  var reason = 'CodeCGC: ' + ownerLabel + ' paths should be routed through /cgc (Codex for backend, Gemini for frontend).';
  if (ownerLabel === 'unknown') {
    reason = 'CodeCGC: path is not covered by model-routing.yaml. Add it to the appropriate section or route through /cgc.';
  }
  if (ownerLabel === 'shared') {
    reason = 'CodeCGC: shared paths require split-first routing. Use /cgc to split into backend/frontend steps.';
  }

  console.log(JSON.stringify({
    decision: 'deny',
    reason: reason
  }));
} catch {
  process.exit(0);
}

// ── Helpers ──

function normalizePath(filePath, cwd) {
  var p = filePath.replace(/\\/g, '/');
  if (path.isAbsolute(filePath)) {
    try {
      p = path.relative(cwd, filePath).replace(/\\/g, '/');
    } catch { /* keep original */ }
  }
  while (p.startsWith('./')) {
    p = p.slice(2);
  }
  return p;
}

function parseSimpleYaml(content) {
  var sections = {};
  var currentKey = null;
  var lines = content.split('\n');

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    // Skip empty lines and comments
    if (!line.trim() || line.trim().charAt(0) === '#') continue;

    // Top-level key (no leading whitespace, ends with :)
    if (line.charAt(0) !== ' ' && line.charAt(0) !== '\t' && line.indexOf(':') > 0) {
      currentKey = line.split(':')[0].trim();
      if (!sections[currentKey]) sections[currentKey] = [];
      continue;
    }

    if (!currentKey) continue;

    var trimmed = line.trim();

    // Nested key under current section (e.g. "frontend:" under "test_paths:")
    // Check if line has indentation + is a key (contains : but is not a list item)
    var indent = line.length - line.replace(/^(\s*)/, '').length;
    if (indent > 0 && trimmed.indexOf(':') > 0 && trimmed.charAt(0) !== '-') {
      var subKey = trimmed.split(':')[0].trim();
      var compoundKey = currentKey + '_' + subKey;
      if (!sections[compoundKey]) sections[compoundKey] = [];
      // Point currentKey to compound key so subsequent list items go there
      currentKey = compoundKey;
      continue;
    }

    // List item (indented, starts with -)
    if (trimmed.charAt(0) === '-') {
      var value = trimmed.slice(1).trim();
      // Strip quotes
      if ((value.charAt(0) === '"' && value.charAt(value.length - 1) === '"')
        || (value.charAt(0) === "'" && value.charAt(value.length - 1) === "'")) {
        value = value.slice(1, -1);
      }
      if (value) {
        sections[currentKey].push(value);
      }
    }
  }

  return sections;
}

function classifyPath(normalizedPath, sections) {
  // Order matters: shared first, then orchestration, docs, tests, frontend, backend
  var groups = [
    ['shared', sections['shared_paths'] || []],
    ['orchestration', sections['orchestration_paths'] || []],
    ['docs', sections['docs_paths'] || []],
    ['frontend-test', sections['test_paths_frontend'] || []],
    ['backend-test', sections['test_paths_backend'] || []],
    ['frontend', sections['frontend_paths'] || []],
    ['backend', sections['backend_paths'] || []]
  ];

  for (var i = 0; i < groups.length; i++) {
    var owner = groups[i][0];
    var patterns = groups[i][1];
    if (matchesAny(normalizedPath, patterns)) {
      return owner;
    }
  }
  return 'unknown';
}

function matchesAny(filePath, patterns) {
  for (var i = 0; i < patterns.length; i++) {
    if (globMatch(filePath, patterns[i])) {
      return true;
    }
  }
  return false;
}

function globMatch(filePath, pattern) {
  var regex = globToRegex(pattern);
  return regex.test(filePath);
}

function globToRegex(pattern) {
  var regexStr = '^';
  var i = 0;
  while (i < pattern.length) {
    var ch = pattern.charAt(i);
    if (ch === '*' && i + 1 < pattern.length && pattern.charAt(i + 1) === '*') {
      // ** matches everything
      regexStr += '.*';
      i += 2;
      // skip trailing / if present
      if (i < pattern.length && pattern.charAt(i) === '/') i++;
    } else if (ch === '*') {
      // * matches anything except /
      regexStr += '[^/]*';
      i++;
    } else if (ch === '.') {
      regexStr += '\\.';
      i++;
    } else {
      regexStr += ch;
      i++;
    }
  }
  regexStr += '$';
  return new RegExp(regexStr);
}
