"""
solver.py
---------
Numerical ODE solvers.  Each solver takes:

    derivatives    : callable  (state, t, params) -> list[float]
    state0         : list[float]  initial conditions
    t_span         : (t_start, t_end)
    dt             : float  time step
    params         : dict   model parameters
    stop_condition : callable (state, t) -> bool | None
                     If provided, integration stops when it returns True.

And returns:
    times  : np.ndarray  shape (n_steps,)
    states : np.ndarray  shape (n_steps, n_variables)

Add new solvers here following the same signature.

Stop condition examples
-----------------------
    # Stop when prey exceeds 30
    stop_condition = lambda state, t: state[0] > 30

    # Stop at equilibrium (all derivatives < threshold)
    stop_condition = lambda state, t: all(abs(d) < 1e-4 for d in derivatives(state, t, params))

    # Stop when predator goes extinct
    stop_condition = lambda state, t: state[1] < 0.01
"""

import numpy as np
from typing import Callable


def euler(
    derivatives: Callable,
    state0: list[float],
    t_span: tuple[float, float],
    dt: float,
    params: dict,
    stop_condition: Callable | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Forward Euler method.  Simple, fast, first-order accurate."""
    t_start, t_end = t_span
    times = np.arange(t_start, t_end + dt, dt)
    states = np.empty((len(times), len(state0)))
    states[0] = state0
    last = 0

    for i in range(1, len(times)):
        t = times[i - 1]
        s = states[i - 1]
        derivs = derivatives(s.tolist(), t, params)
        states[i] = s + dt * np.array(derivs)
        last = i
        if stop_condition is not None and stop_condition(states[i].tolist(), times[i]):
            break

    return times[: last + 1], states[: last + 1]


def rk4(
    derivatives: Callable,
    state0: list[float],
    t_span: tuple[float, float],
    dt: float,
    params: dict,
    stop_condition: Callable | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Classical 4th-order Runge-Kutta method.
    More accurate than Euler; recommended for most simulations.
    """
    t_start, t_end = t_span
    times = np.arange(t_start, t_end + dt, dt)
    states = np.empty((len(times), len(state0)))
    states[0] = state0
    last = 0

    for i in range(1, len(times)):
        t = times[i - 1]
        s = states[i - 1]

        k1 = np.array(derivatives(s.tolist(), t, params))
        k2 = np.array(derivatives((s + 0.5 * dt * k1).tolist(), t + 0.5 * dt, params))
        k3 = np.array(derivatives((s + 0.5 * dt * k2).tolist(), t + 0.5 * dt, params))
        k4 = np.array(derivatives((s + dt * k3).tolist(), t + dt, params))

        states[i] = s + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        last = i
        if stop_condition is not None and stop_condition(states[i].tolist(), times[i]):
            break

    return times[: last + 1], states[: last + 1]


# Registry: name -> solver function
SOLVERS = {
    "Euler": euler,
    "RK4": rk4,
}
