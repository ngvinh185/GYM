from deepagents import create_deep_agent

def create_deepagent(model, system_prompt, subagents, backend, checkpointer, middleware):
  return create_deep_agent(
      model=model,
      system_prompt=system_prompt,
      subagents=subagents,
      backend=backend,
      checkpointer=checkpointer,
      middleware=middleware
  )