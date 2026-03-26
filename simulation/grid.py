"""
grid.py
-------
2D spatial grid for reaction-diffusion simulations.

Each cell (i, j) holds a vector of state variable densities.
The grid evolves using:
    state[var] += dt * (reaction_term + D * laplacian(state[var]))

Usage
-----
    grid = Grid(width=100, height=100, n_variables=2)
    grid.randomize(means=[10.0, 5.0], noise=1.0)
    grid.step(derivatives_fn, params, dt=0.1, diffusion=[0.1, 0.05])
"""

import numpy as np
from typing import Callable


class Grid:
    """
    2D spatial grid holding densities for n_variables per cell.

    Attributes
    ----------
    width, height : grid dimensions
    n_variables   : number of state variables (e.g. 2 for prey/predator)
    state         : np.ndarray shape (n_variables, height, width)
    """

    def __init__(self, width: int, height: int, n_variables: int) -> None:
        self.width = width
        self.height = height
        self.n_variables = n_variables
        self.state = np.zeros((n_variables, height, width), dtype=np.float64)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def fill(self, values: list[float]) -> None:
        """Fill every cell with the given values (one per variable)."""
        for v, val in enumerate(values):
            self.state[v] = val

    def randomize(self, means: list[float], noise: float = 0.5) -> None:
        """Fill each variable with mean + uniform noise in [-noise, +noise]."""
        for v, mean in enumerate(means):
            self.state[v] = mean + noise * (
                2.0 * np.random.rand(self.height, self.width) - 1.0
            )
        np.clip(self.state, 0, None, out=self.state)

    def seed_patch(
        self,
        variable: int,
        center: tuple[int, int],
        radius: int,
        value: float,
    ) -> None:
        """Set a circular patch of cells to a given value."""
        cy, cx = center
        y, x = np.ogrid[: self.height, : self.width]
        mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
        self.state[variable][mask] = value

    # ------------------------------------------------------------------
    # Laplacian (finite differences, periodic boundary)
    # ------------------------------------------------------------------

    @staticmethod
    def laplacian(field: np.ndarray) -> np.ndarray:
        """
        2D discrete Laplacian with periodic boundary conditions.
        Uses a 5-point stencil (up/down/left/right neighbours).
        """
        return (
            np.roll(field, 1, axis=0)
            + np.roll(field, -1, axis=0)
            + np.roll(field, 1, axis=1)
            + np.roll(field, -1, axis=1)
            - 4.0 * field
        )

    # ------------------------------------------------------------------
    # Time stepping
    # ------------------------------------------------------------------

    def step(
        self,
        derivatives: Callable,
        params: dict,
        dt: float,
        diffusion: list[float],
    ) -> None:
        """
        Advance the grid by one time step using forward Euler.

        Parameters
        ----------
        derivatives : model function (state_list, t, params) -> list[float]
                      called per cell; t is set to 0 (spatial mode is memoryless)
        params      : model parameter dict
        dt          : time step
        diffusion   : diffusion coefficient per variable
        """
        new_state = self.state.copy()

        for i in range(self.height):
            for j in range(self.width):
                cell_state = [float(self.state[v, i, j]) for v in range(self.n_variables)]
                derivs = derivatives(cell_state, 0.0, params)
                for v in range(self.n_variables):
                    new_state[v, i, j] += dt * derivs[v]

        # Add diffusion term after reaction
        for v in range(self.n_variables):
            if diffusion[v] > 0:
                new_state[v] += dt * diffusion[v] * self.laplacian(self.state[v])

        np.clip(new_state, 0, None, out=new_state)
        self.state = new_state

    def step_vectorized(
        self,
        alpha: float,
        beta: float,
        delta: float,
        gamma: float,
        dt: float,
        diffusion: list[float],
    ) -> None:
        """
        Fast vectorized step for Lotka-Volterra only.
        Used when the grid is too large for the cell-by-cell loop.
        Replace hardcoded variable names if you add more models.
        """
        X = self.state[0]
        Y = self.state[1]

        dX = alpha * X - beta * X * Y
        dY = delta * X * Y - gamma * Y

        new_X = X + dt * dX + dt * diffusion[0] * self.laplacian(X)
        new_Y = Y + dt * dY + dt * diffusion[1] * self.laplacian(Y)

        self.state[0] = np.clip(new_X, 0, None)
        self.state[1] = np.clip(new_Y, 0, None)
