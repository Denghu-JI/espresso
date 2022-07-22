import numpy as np
import pygimli
from pygimli.physics import ert
from cofi import BaseProblem, InversionOptions, Inversion
from cofi.solvers import BaseSolver

from pygimli_ert_lib import (
    survey_scheme,
    model_true,
    ert_simulate,
    ert_manager,
    inversion_mesh,
    ert_forward_operator,
    reg_matrix,
    starting_model,
    get_response,
    get_residual,
    get_jacobian,
    get_data_misfit,
    get_regularisation,
    get_gradient,
    get_hessian,
)


############# ERT Modelling with PyGIMLi ##############################################

# measuring scheme
scheme = survey_scheme()

# create simulation mesh and true model
mesh, rhomap = model_true(scheme)
ax = pygimli.show(mesh, data=rhomap, label="$\Omega m$", showMesh=True)
ax[0].set_title("True model")
ax[0].figure.savefig("figs/scipy_opt_model_true")

# generate data
data, log_data, data_cov_inv = ert_simulate(mesh, scheme, rhomap)
ax = ert.show(data)
ax[0].set_title("Provided data")
ax[0].figure.savefig("figs/scipy_opt_data")

# create PyGIMLi's ERT manager
ert_manager = ert_manager(data)

# create inversion mesh
inv_mesh = inversion_mesh(ert_manager)
ax = pygimli.show(inv_mesh, showMesh=True, markers=True)
ax[0].set_title("Mesh used for inversion")
ax[0].figure.savefig("figs/scipy_opt_inv_mesh")

# PyGIMLi's forward operator (ERTModelling)
forward_oprt = ert_forward_operator(ert_manager, scheme, inv_mesh)

# extract regularisation matrix
Wm = reg_matrix(forward_oprt)

# initialise a starting model for inversion
start_model = starting_model(ert_manager)
ax = pygimli.show(ert_manager.paraDomain, data=start_model, label="$\Omega m$", showMesh=True)
ax[0].set_title("Starting model")
ax[0].figure.savefig("figs/scipy_opt_model_start")


############# Inverted by SciPy optimiser through CoFI ################################

# hyperparameters
lamda = 0.0005

# CoFI - define BaseProblem
ert_problem = BaseProblem()
ert_problem.name = "Electrical Resistivity Tomography defined through PyGIMLi"
ert_problem.set_forward(get_response, args=[forward_oprt])
ert_problem.set_jacobian(get_jacobian, args=[forward_oprt])
ert_problem.set_residual(get_residual, args=[log_data, forward_oprt])
ert_problem.set_data_misfit(get_data_misfit, args=[log_data, forward_oprt])
ert_problem.set_regularisation(get_regularisation, args=[Wm, lamda])
ert_problem.set_gradient(get_gradient, args=[log_data, forward_oprt, Wm, lamda])
ert_problem.set_hessian(get_hessian, args=[log_data, forward_oprt, Wm, lamda])
ert_problem.set_initial_model(start_model)

# CoFI - define InversionOptions
inv_options_scipy = InversionOptions()
inv_options_scipy.set_tool("scipy.optimize.minimize")
inv_options_scipy.set_params(method="Newton-CG")

# CoFI - define Inversion, run it
inv = Inversion(ert_problem, inv_options_scipy)
inv_result = inv.run()

# plot inferred model
inv_result.summary()
ax = pygimli.show(ert_manager.paraDomain, data=inv_result.model, label=r"$\Omega m$")
ax[0].set_title("Inferred model")
ax[0].figure.savefig("figs/scipy_opt_inferred_model")

# plot synthetic data
d = forward_oprt.response(inv_result.model)
ax = ert.showERTData(scheme, vals=d)
ax[0].set_title("Synthetic data from inferred model")
ax[0].figure.savefig("figs/scipy_opt_inferred_data")
