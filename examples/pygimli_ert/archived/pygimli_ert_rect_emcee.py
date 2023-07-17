"""Eletrical Resistivity Tomography Inversion with PyGIMLi + CoFI

This script runs:
- ERT problem (rectangular mesh) defined with PyGIMLi, and
- Bayesian sampling using emcee with CoFI


To run this script, refer to the following examples:

- `python pygimli_ert_rect_emcee.py` for a simple run, with all the figures saved to
  current directory by default

- `python pygimli_ert_rect_emcee.py -o figs` for the same run as above, with all the
  figures saved to subfolder `figs`

- `python pygimli_ert_rect_emcee.py -h` to see all available options

"""

############# 0. Import modules #######################################################

import numpy as np
import matplotlib.pyplot as plt
import pygimli
from pygimli.physics import ert
from emcee.moves import GaussianMove

from cofi import BaseProblem, InversionOptions, Inversion

from pygimli_ert_lib import *


############# Configurations ##########################################################

np.random.seed(42)

save_plot = True
show_plot = False
show_summary = True

_problem_name = "pygimli_ert"
_solver_name = "newton_opt"
_file_prefix = f"{_problem_name}_{_solver_name}"
_figs_prefix = f"./{_file_prefix}"


############# Plotting functions ######################################################

def _post_plot(ax, title):
    ax[0].set_title(title)
    if save_plot:
        ax[0].figure.savefig(f"{_figs_prefix}_{title}")
    if show_plot:
        plt.show()

def plot_mesh(mesh, title):
    ax = pygimli.show(mesh)
    _post_plot(ax, title)
    
def plot_model(mesh, model, label, title):
    ax = pygimli.show(mesh, data=model, label=label)
    _post_plot(ax, title)

def plot_data(survey, label, title):
    ax=ert.showERTData(survey,label=label)
    _post_plot(ax, title)


############# Main ####################################################################

def main():

    ######### 1. Define the problem ###################################################
    
    # PyGIMLi - define measuring scheme, geometry, forward mesh and true model
    scheme = scheme_fwd()
    geometry = geometry_true()
    fmesh = mesh_fwd(scheme, geometry)
    rhomap = markers_to_resistivity()
    model_true = model_vec(rhomap, fmesh)
    
    # PyGIMLi - plot the compuational mesh and the true model
    plot_mesh(fmesh, "Computational Mesh")
    plot_model(fmesh, model_true, "$\Omega m$", "Resistivity")

    # PyGIMLi - generate data
    survey = ert.simulate(fmesh, res=rhomap, scheme=scheme)
    plot_data(survey, "$\Omega m$", "Aparent Resistivity")
    y_obs = np.log(survey['rhoa'].array())

    # PyGIMLi - create mesh for inversion
    imesh_rect = mesh_inv_rectangular()
    plot_mesh(imesh_rect, "Inversion Mesh")

    # PyGIMLi - define starting model, forward operator and Wm
    model_0 = starting_model(imesh_rect)
    forward_operator = forward_oprt(scheme, imesh_rect)
    Wm = weighting_matrix(forward_operator, imesh_rect)

    # hyperparameters
    lamda = 2
    nwalkers = 32
    nsteps = 500

    # CoFI - define BaseProblem
    ert_problem = BaseProblem()
    ert_problem.name = "Electrical Resistivity Tomography defined through PyGIMLi"
    ert_problem.set_forward(get_response, args=[forward_operator])
    ert_problem.set_jacobian(get_jacobian, args=[forward_operator])
    ert_problem.set_residual(get_residuals, args=[y_obs, forward_operator])
    ert_problem.set_data_misfit(get_misfit, args=[y_obs, forward_operator, True])
    ert_problem.set_regularization(get_regularization, lamda=lamda, args=[Wm, True])
    ert_problem.set_gradient(get_gradient, args=[y_obs, forward_operator, lamda, Wm])
    ert_problem.set_hessian(get_hessian, args=[y_obs, forward_operator, lamda, Wm])
    ert_problem.set_initial_model(model_0)

    # for emcee - define log_likelihood
    sigma = 1.0                                     # common noise standard deviation
    Cdinv = np.eye(len(y_obs))/(sigma**2)           # inverse data covariance matrix
    def log_likelihood(model):
        residual = ert_problem.residual(model)
        return -0.5 * residual @ (Cdinv @ residual).T

    # for emcee - define log_prior
    m_lower_bound = np.zeros(model_0.shape)         # lower bound for uniform prior
    m_upper_bound = np.ones(model_0.shape) * 250    # upper bound for uniform prior
    def log_prior(model):                           # uniform distribution
        for i in range(len(m_lower_bound)):
            if model[i] < m_lower_bound[i] or model[i] > m_upper_bound[i]: return -np.inf
        return 0.0 # model lies within bounds -> return log(1)

    # for emcee - define walkers' starting positions
    walkers_start = model_0 + 1e-6 * np.random.randn(nwalkers, model_0.shape[0])

    # CoFI - add them into cofi's BaseProblem object
    ert_problem.set_log_likelihood(log_likelihood)
    ert_problem.set_log_prior(log_prior)
    ert_problem.set_walkers_starting_pos(walkers_start)

    if show_summary:
        ert_problem.summary()


    ######### 2. Define the inversion options #########################################
    inv_options = InversionOptions()
    inv_options.set_tool("emcee")
    inv_options.set_params(
        nwalkers=nwalkers, 
        nsteps=nsteps, 
        moves=GaussianMove(1), 
        progress=True
    )

    if show_summary:
        inv_options.summary()


    ######### 3. Run the inversion ####################################################
    inv = Inversion(ert_problem, inv_options)
    inv_result = inv.run()

    if show_summary:
        inv_result.summary()


    ######### 4. Plot the results #####################################################
    plot_model(fmesh, model_true, r"$\Omega m$", "True model")
    plot_model(imesh_rect, model_0, r"$\Omega m$", "Starting model")
    flat_samples = inv_result.sampler.get_chain(discard=100, thin=30, flat=True)
    indices = np.random.randint(len(flat_samples), size=10) # get a random selection from posterior ensemble
    for idx in indices:
        plot_model(imesh_rect, flat_samples[idx], r"$\Omega m$", f"Inferred model - sample {idx}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Polynomial Linear regression solved by linear system solver'
    )
    parser.add_argument("--output-dir", "-o", type=str, help="output folder for figures")
    parser.add_argument("--show-plot", dest="show_plot", action="store_true", default=None)
    parser.add_argument("--no-show-plot", dest="show_plot", action="store_false", default=None)
    parser.add_argument("--save-plot", dest="save_plot", action="store_true", default=None)
    parser.add_argument("--no-save-plot", dest="save_plot", action="store_false", default=None)
    parser.add_argument("--show-summary", dest="show_summary", action="store_true", default=None)
    parser.add_argument("--no-show-summary", dest="show_summary", action="store_false", default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or "."
    if output_dir.endswith("/"):
        output_dir = output_dir[:-1]
    show_plot = show_plot if args.show_plot is None else args.show_plot
    save_plot = save_plot if args.save_plot is None else args.save_plot
    show_summary = show_summary if args.show_summary is None else args.show_summary

    _figs_prefix = f"{output_dir}/{_file_prefix}"
    main()
