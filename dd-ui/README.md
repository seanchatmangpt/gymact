# Deterministic Dynamic UI profile

GymAct contributes bounded world, episode, capability, observation, and authority semantics to the ecosystem DDUI world. It does not own the UI renderer.

The projection law is pinned to `seanchatmangpt/wasm4pm` DDUI v2 exact commit `8d48e784a4215857c8428c09bb09a91c05a8be97`. `world.json` is observation input only; no authority is inferred from rendering.

The verifier projects 5 avatars across 4 contexts and requires exact replay, `irreversibleUiSelections = 0`, `runtimeAiRenderAuthority = false`, and `directActuation = false` for every projection.

DfCM preserves reversible presentation alternatives while GymAct's own consequence law remains intact: request acceptance, world change, verification, and scoring are distinct, and consequential environments remain fail closed.
