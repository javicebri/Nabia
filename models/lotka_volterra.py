"""
lotka_volterra.py
-----------------
Classic Lotka-Volterra predator-prey model.

Equations
---------
    dX/dt =  alpha * X  -  beta  * X * Y     (prey)
    dY/dt =  delta * X * Y  -  gamma * Y     (predator)

Variables
---------
    X : prey population density
    Y : predator population density

Parameters
----------
    alpha  : prey intrinsic growth rate
    beta   : predation rate (prey loss per predator encounter)
    delta  : predator growth efficiency from predation
    gamma  : predator natural death rate

Spatial extension (reaction-diffusion)
---------------------------------------
When run on a 2D grid, each cell evolves with the equations above plus
Fickian diffusion:
    dX/dt += D_prey     * laplacian(X)
    dY/dt += D_predator * laplacian(Y)

    D_prey     : diffusion coefficient for prey
    D_predator : diffusion coefficient for predator

Edit any value below to change model behaviour.
"""

NAME = "Lotka-Volterra"
VARIABLES = ["prey", "predator"]

DEFAULT_PARAMS = {
    "alpha": 1.0,       # prey growth rate
    "beta": 0.1,        # predation rate
    "delta": 0.075,     # predator efficiency
    "gamma": 1.5,       # predator death rate
    "D_prey": 0.1,      # prey diffusion (spatial mode)
    "D_predator": 0.05, # predator diffusion (spatial mode)
}

# Initial conditions used when no CSV is loaded
DEFAULT_INITIAL_STATE = [10.0, 5.0]  # [prey, predator]


def derivatives(state: list[float], t: float, params: dict) -> list[float]:
    """
    Returns [dX/dt, dY/dt] for a single well-mixed population (ODE mode).

    Parameters
    ----------
    state  : [X, Y]  current population densities
    t      : current time (unused here, kept for solver compatibility)
    params : dict with keys matching DEFAULT_PARAMS
    """
    X, Y = state

    alpha = params["alpha"]
    beta  = params["beta"]
    delta = params["delta"]
    gamma = params["gamma"]

    dX = alpha * X - beta * X * Y
    dY = delta * X * Y - gamma * Y

    return [dX, dY]
