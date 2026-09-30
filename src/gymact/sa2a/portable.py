"""Language-neutral wire projection."""
def encode(e):
    c=e.candidate; return {"subject":c.subject,"effect_id":c.effect_id,"generation":c.generation,"provider":c.provider,"replay_key":c.replay_key,"authority":c.authority,"attempt":e.attempt,"max_attempts":e.max_attempts,"outcome":e.outcome}
