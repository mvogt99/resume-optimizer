Delegate a task to the local RTX 5090 GPU via the FTAL harness. This saves cloud tokens by running the task on the local Qwen3-Coder-30B model.

Use the `mcp__ftal-harness__delegate_task` tool with the user's input as the task.

If the user provided arguments, use them as the task description. If the user also specified a type (e.g., "--type coding", "--type planning", "--type reasoning", "--type analysis", "--type review"), pass it as task_type.

After receiving the result, display:
1. The FTAL score (F/T/A/L breakdown and gap percentage)
2. Whether it passed or failed
3. The generated output
4. If escalated (gap >= 50 after 3 attempts), ask the user whether to use cloud tokens or skip

$ARGUMENTS
