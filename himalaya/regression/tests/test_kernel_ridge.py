import pytest

import sklearn.linear_model
import scipy.linalg

from himalaya.backend import change_backend
from himalaya.backend import ALL_BACKENDS
from himalaya.regression.kernel_ridge import multi_kernel_ridge_gradient
from himalaya.regression.kernel_ridge import solve_multi_kernel_ridge_gradient_descent  # noqa


def _create_dataset(backend):
    n_samples, n_targets = 100, 3

    Xs = [backend.randn(n_samples, 100), backend.randn(n_samples, 200)]
    Ks = backend.stack([backend.matmul(X, X.T) for X in Xs])
    Y = backend.randn(n_samples, n_targets)
    dual_weights = backend.randn(n_samples, n_targets)
    gammas = backend.rand(Ks.shape[0], n_targets)

    return Xs, Ks, Y, gammas, dual_weights


@pytest.mark.parametrize("double_K", [False, True])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_multi_kernel_ridge_gradient(backend, double_K):
    backend = change_backend(backend)

    _, Ks, Y, gammas, dual_weights = _create_dataset(backend)
    alpha = 1.

    n_targets = Y.shape[1]
    grad = backend.zeros_like(dual_weights)
    func = backend.zeros(n_targets)
    for tt in range(n_targets):
        K = backend.sum(
            backend.stack([K * g for K, g in zip(Ks, gammas[:, tt])]), 0)
        grad[:, tt] = (backend.matmul(K, dual_weights[:, tt]) - Y[:, tt] +
                       alpha * dual_weights[:, tt])

        pred = backend.matmul(K, dual_weights[:, tt])
        func[tt] = backend.sum((pred - Y[:, tt]) ** 2, 0)
        func[tt] += alpha * (dual_weights[:, tt] @ K @ dual_weights[:, tt])

        if double_K:
            grad[:, tt] = backend.matmul(K.T, grad[:, tt])

    ########################
    grad2, func2 = multi_kernel_ridge_gradient(Ks, Y, dual_weights, gammas,
                                               alpha, double_K=double_K,
                                               return_objective=True)
    backend.assert_allclose(grad, grad2, rtol=1e-4, atol=1e-4)
    backend.assert_allclose(func, func2, rtol=1e-4, atol=1e-4)


@pytest.mark.parametrize('solver', ["gradient_descent"])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_solve_ridge_kernel_gamma_per_target(solver, backend):
    backend = change_backend(backend)

    if solver == "gradient_descent":
        solver = solve_multi_kernel_ridge_gradient_descent

    Xs, Ks, Y, gammas, dual_weights = _create_dataset(backend)
    alpha = 1.

    for alpha in backend.logspace(-3, 3, 7):
        c2 = solver(Ks, Y, gammas, alpha=alpha, max_iter=100)

        n_targets = Y.shape[1]
        for ii in range(n_targets):
            # compare dual coefficients with scipy.linalg.solve
            K = backend.matmul(Ks.T, gammas[:, ii]).T
            K_reg = K + backend.eye(K.shape[0]) * alpha
            c1 = scipy.linalg.solve(K_reg, Y[:, ii])
            backend.assert_allclose(c1, c2[:, ii], rtol=1e-4, atol=1e-2)

            # compare predictions with sklearn.linear_model.Ridge
            X_scaled = backend.concatenate(
                [t * backend.sqrt(g) for t, g in zip(Xs, gammas[:, ii])], 1)
            prediction = backend.matmul(K, c2[:, ii])
            model = sklearn.linear_model.Ridge(alpha=alpha,
                                               fit_intercept=False).fit(
                                                   X_scaled, Y[:, ii])
            prediction_sklearn = model.predict(X_scaled)
            backend.assert_allclose(prediction, prediction_sklearn, rtol=1e-4,
                                    atol=1e-1)