import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

function rtkCheck(command) {
  const result = spawnSync('rtk', ['hook', 'check', command], { encoding: 'utf8', timeout: 3000 })
  return result.status === 0 ? result.stdout.trim() : ''
}

export function rewriteHookInput(input, check = rtkCheck) {
  if (input?.tool_name !== 'Bash' && input?.toolName !== 'Bash') return null
  const toolInput = input.tool_input ?? input.toolInput
  const command = toolInput?.command
  if (typeof command !== 'string' || command.trim() === '') return null
  const rewritten = check(command)
  if (!rewritten || rewritten === command) return null
  return {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      updatedInput: { ...toolInput, command: rewritten },
    },
  }
}

async function main() {
  let raw = ''
  for await (const chunk of process.stdin) raw += chunk
  try {
    const output = rewriteHookInput(JSON.parse(raw))
    if (output) process.stdout.write(JSON.stringify(output))
  } catch {
    // Compression is an optimization. Malformed input must never block Codex.
  }
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) await main()
