import numbers

from ..backend import get_backend


def solve_ridge_svd(X, Y, alpha=1., method="svd",
                    negative_eigenvalues="zeros"):
    """Solve kernel ridge regression using eigenvalues decomposition.

    Solve the kernel ridge regression::

        b* = argmin_B ||X @ b - Y||^2 + alpha ||b||^2

    Parameters
    ----------
    X : array of shape (n_samples, n_features)
        Input features.
    Y : array of shape (n_samples, n_targets)
        Target data.
    alpha : float, or array of shape (n_targets, )
        Regularization parameter.
    method : str in {"svd"}
        Method used to diagonalize the input feature matrix.
    negative_eigenvalues : str in {"nan", "error", "zeros"}
        If the decomposition leads to negative eigenvalues (wrongly emerging
        from float32 errors):
        - "error" raises an error.
        - "zeros" remplaces them with zeros.
        - "nan" returns nans if the regularization does not compensate
        twice the smallest negative value, else it ignores the problem.

    Returns
    -------
    weights : array of shape (n_features, n_targets)
        Ridge coefficients.
    """
    backend = get_backend()
    if isinstance(alpha, numbers.Number) or alpha.ndim == 0:
        alpha = backend.ones_like(Y, shape=(1, )) * alpha

    X, Y, alpha = backend.check_arrays(X, Y, alpha)

    if method == "svd":
        # SVD: X = U @ np.diag(eigenvalues) @ Vt
        U, eigenvalues, Vt = backend.svd(X, full_matrices=False)
    else:
        raise ValueError("Unknown method=%r." % (method, ))

    inverse = eigenvalues[:, None] / (alpha[None] + eigenvalues[:, None] ** 2)

    # negative eigenvalues can emerge from incorrect kernels, or from float32
    if eigenvalues[0] < 0:
        if negative_eigenvalues == "nan":
            if alpha < -eigenvalues[0] * 2:
                return backend.ones_like(Y) * backend.asarray(
                    backend.nan, dtype=Y.dtype)
            else:
                pass

        elif negative_eigenvalues == "zeros":
            eigenvalues[eigenvalues < 0] = 0

        elif negative_eigenvalues == "error":
            raise RuntimeError(
                "Negative eigenvalues. Make sure the kernel is positive "
                "semi-definite, increase the regularization alpha, or use"
                "another solver.")
        else:
            raise ValueError("Unknown negative_eigenvalues=%r." %
                             (negative_eigenvalues, ))

    iUT = inverse[:, None, :] * U.T[:, :, None]
    if Y.shape[0] < Y.shape[1]:
        weights = (backend.transpose(Vt.T @ iUT,
                                     (2, 0, 1)) @ Y.T[:, :, None])[:, :, 0].T
    else:
        weights = Vt.T @ (
            backend.transpose(iUT, (2, 0, 1)) @ Y.T[:, :, None])[:, :, 0].T

    return weights


#: Dictionary with all ridge solvers
RIDGE_SOLVERS = {"svd": solve_ridge_svd}
