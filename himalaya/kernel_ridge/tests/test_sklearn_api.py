import warnings

import pytest
import sklearn.kernel_ridge
import sklearn.utils.estimator_checks

from himalaya.backend import set_backend
from himalaya.backend import get_backend
from himalaya.backend import ALL_BACKENDS
from himalaya.utils import assert_array_almost_equal

from himalaya.kernel_ridge import KernelRidge
from himalaya.kernel_ridge import MultipleKernelRidgeCV
from himalaya.kernel_ridge import WeightedKernelRidge


def _create_dataset(backend):
    n_samples, n_targets = 30, 3

    Xs = [
        backend.asarray(backend.randn(n_samples, n_features), backend.float64)
        for n_features in [100, 200]
    ]
    Ks = backend.stack([backend.matmul(X, X.T) for X in Xs])
    Y = backend.asarray(backend.randn(n_samples, n_targets), backend.float64)

    return Xs, Ks, Y


@pytest.mark.parametrize('kernel', [
    'linear', 'polynomial', 'poly', 'rbf', 'sigmoid', 'cosine', 'precomputed'
])
@pytest.mark.parametrize('multitarget', [True, False])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_kernel_ridge_vs_scikit_learn(backend, multitarget, kernel):
    backend = set_backend(backend)
    Xs, Ks, Y = _create_dataset(backend)

    if not multitarget:
        Y = Y[:, 0]

    if kernel == "precomputed":
        X = Ks[0]
    else:
        X = Xs[0]

    for alpha in backend.asarray_like(backend.logspace(0, 3, 7), Ks):
        model = KernelRidge(alpha=alpha, kernel=kernel)
        model.fit(X, Y)

        reference = sklearn.kernel_ridge.KernelRidge(
            alpha=backend.to_numpy(alpha), kernel=kernel)
        reference.fit(backend.to_numpy(X), backend.to_numpy(Y))

        assert model.dual_coef_.shape == Y.shape
        assert_array_almost_equal(model.dual_coef_, reference.dual_coef_)
        assert_array_almost_equal(model.predict(X),
                                  reference.predict(backend.to_numpy(X)))
        assert_array_almost_equal(
            model.score(X, Y).mean(),
            reference.score(backend.to_numpy(X), backend.to_numpy(Y)))


@pytest.mark.parametrize(
    'kernel', ['linear', 'polynomial', 'poly', 'rbf', 'sigmoid', 'cosine'])
@pytest.mark.parametrize('format', ['coo', 'csr', 'csc'])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_kernel_ridge_vs_scikit_learn_sparse(backend, kernel, format):
    backend = set_backend(backend)
    Xs, _, Y = _create_dataset(backend)

    try:
        import scipy.sparse
    except ImportError:
        pytest.skip("Scipy is not installed.")

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', scipy.sparse.SparseEfficiencyWarning)
        X = scipy.sparse.rand(*Xs[0].shape, density=0.1, format=format)

    for alpha in backend.asarray_like(backend.logspace(0, 3, 7), Y):
        model = KernelRidge(alpha=alpha, kernel=kernel)
        model.fit(X, Y)

        reference = sklearn.kernel_ridge.KernelRidge(
            alpha=backend.to_numpy(alpha), kernel=kernel)
        reference.fit(X, backend.to_numpy(Y))

        assert model.dual_coef_.shape == Y.shape
        assert_array_almost_equal(model.dual_coef_, reference.dual_coef_)
        assert_array_almost_equal(model.predict(X), reference.predict(X))
        assert_array_almost_equal(
            model.score(X, Y).mean(), reference.score(X, backend.to_numpy(Y)))


@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_kernel_ridge_precomputed(backend):
    backend = set_backend(backend)
    Xs, Ks, Y = _create_dataset(backend)

    for alpha in backend.asarray_like(backend.logspace(-2, 3, 7), Ks):
        model_1 = KernelRidge(alpha=alpha, kernel="linear")
        model_1.fit(Xs[0], Y)
        model_2 = KernelRidge(alpha=alpha, kernel="precomputed")
        model_2.fit(Ks[0], Y)

        assert_array_almost_equal(model_1.dual_coef_, model_2.dual_coef_)
        assert_array_almost_equal(model_1.predict(Xs[0]),
                                  model_2.predict(Ks[0]))


@pytest.mark.parametrize(
    'solver', ['eigenvalues', 'conjugate_gradient', 'gradient_descent'])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_kernel_ridge_solvers(solver, backend):
    backend = set_backend(backend)
    Xs, _, Y = _create_dataset(backend)

    kernel = "linear"
    X = Xs[0]

    if solver == "eigenvalues":
        solver_params = dict()
    elif solver == "conjugate_gradient":
        solver_params = dict(max_iter=300, tol=1e-6)
    elif solver == "gradient_descent":
        solver_params = dict(max_iter=300, tol=1e-6)

    for alpha in backend.asarray_like(backend.logspace(0, 3, 7), Y):
        model = KernelRidge(alpha=alpha, kernel=kernel, solver=solver,
                            solver_params=solver_params)
        model.fit(X, Y)

        reference = sklearn.kernel_ridge.KernelRidge(
            alpha=backend.to_numpy(alpha), kernel=kernel)
        reference.fit(backend.to_numpy(X), backend.to_numpy(Y))

        assert model.dual_coef_.shape == Y.shape
        assert_array_almost_equal(model.dual_coef_, reference.dual_coef_)
        assert_array_almost_equal(model.predict(X),
                                  reference.predict(backend.to_numpy(X)))


@pytest.mark.parametrize('solver', ['random_search', 'hyper_gradient'])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_multiple_kernel_ridge_cv_precomputed(backend, solver):
    backend = set_backend(backend)
    Xs, Ks, Y = _create_dataset(backend)

    if solver == "random_search":
        kwargs = dict(
            solver="random_search",
            solver_params=dict(n_iter=2, random_state=0, progress_bar=False))
    elif solver == "hyper_gradient":
        kwargs = dict(solver="hyper_gradient",
                      solver_params=dict(max_iter=2, progress_bar=False))

    model_1 = MultipleKernelRidgeCV(kernels=["linear"], **kwargs)
    model_1.fit(Xs[0], Y)
    model_2 = MultipleKernelRidgeCV(kernels="precomputed", **kwargs)
    model_2.fit(Ks[0][None], Y)

    assert_array_almost_equal(model_1.dual_coef_, model_2.dual_coef_)
    assert_array_almost_equal(model_1.predict(Xs[0]),
                              model_2.predict(Ks[0][None]))


@pytest.mark.parametrize('solver', ['conjugate_gradient', 'gradient_descent'])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_weighted_kernel_ridge_precomputed(backend, solver):
    backend = set_backend(backend)
    Xs, Ks, Y = _create_dataset(backend)

    model_1 = WeightedKernelRidge(kernels=["linear"])
    model_1.fit(Xs[0], Y)
    model_2 = WeightedKernelRidge(kernels="precomputed")
    model_2.fit(Ks[0][None], Y)

    assert_array_almost_equal(model_1.dual_coef_, model_2.dual_coef_)
    assert_array_almost_equal(model_1.predict(Xs[0]),
                              model_2.predict(Ks[0][None]))


###############################################################################
# scikit-learn.utils.estimator_checks


class KernelRidge_(KernelRidge):
    """Cast predictions to numpy arrays, to be used in scikit-learn tests.

    Used for testing only.
    """

    def predict(self, *args, **kwargs):
        backend = get_backend()
        return backend.to_numpy(super().predict(*args, **kwargs))


class MultipleKernelRidgeCV_(MultipleKernelRidgeCV):
    """Cast predictions to numpy arrays, to be used in scikit-learn tests.

    Used for testing only.
    """

    def __init__(self, kernels=["linear", "polynomial"], kernels_params=None,
                 solver="hyper_gradient",
                 solver_params=dict(progress_bar=False, max_iter=2), cv=5):
        super().__init__(kernels=kernels, kernels_params=kernels_params,
                         solver=solver, solver_params=solver_params, cv=cv)

    def predict(self, *args, **kwargs):
        backend = get_backend()
        return backend.to_numpy(super().predict(*args, **kwargs))


class WeightedKernelRidge_(WeightedKernelRidge):
    """Cast predictions to numpy arrays, to be used in scikit-learn tests.

    Used for testing only.
    """

    def predict(self, *args, **kwargs):
        backend = get_backend()
        return backend.to_numpy(super().predict(*args, **kwargs))


@sklearn.utils.estimator_checks.parametrize_with_checks([
    KernelRidge_(),
    MultipleKernelRidgeCV_(),
    WeightedKernelRidge_(),
])
@pytest.mark.parametrize('backend', ALL_BACKENDS)
def test_check_estimator(estimator, check, backend):
    backend = set_backend(backend)
    check(estimator)