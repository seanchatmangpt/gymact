"""Real gym bridges: GymAct `Environment`/`EnvironmentProvider` implementations
backed by actual, already-installed benchmark packages -- not synthetic stand-ins.

The first bridge target (`gymact.gyms.cube_counter`) drives CUBE's own
no-Docker reference benchmark (`counter-cube`), installed from
~/autofde-lab/vendor/gyms/cube-standard via the optional `cube` extra.
"""
