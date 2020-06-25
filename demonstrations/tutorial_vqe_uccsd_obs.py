r"""
VQE in different spin sectors with the Unitary Coupled Cluster ansatz
=====================================================================

.. meta::
    :property="og:description": Find the lowest-energy states of a Hamiltonian in different
        sector of the spin quantum number using the variational quantum eigensolver
        algorithm in PennyLane.
    :property="og:image": https://pennylane.ai/qml/_images/pes_h2.png

Quantum computers offer a promising avenue to perform first-principles simulations of the
electronic structure of molecules and materials that are currently intractable using classical
high-performance computers. In particular, the Variational Quantum Eigensolver (VQE) algorithm
:ref:`[1, 2]<vqe_uccsd_references>` has proven to be a valuable quantum-classical computational
approach to find the lowest-energy eigenstate of the electronic Hamiltonian by using Noisy
Intermediate-Scale Quantum (NISQ) devices :ref:`[3]<vqe_uccsd_references>`.

In the absence of `spin-orbit coupling <https://en.wikipedia.org/wiki/Spin-orbit_interaction>`_ the
electronic Hamiltonian matrix is block diagonal in the total spin quantum numbers. In other words,
one can expand the many-electron wave function of the molecule as a linear
combination of `Slater determinants <https://en.wikipedia.org/wiki/Slater_determinant>`_
with the same total-spin projection :math:`S_z`, and diagonalize the Hamiltonian in this basis
to obtain the energy spectrum in this particular subspace. For example, the figure below
shows the energy spectra of the Hydrogen molecule calculated in different sectors of the total-
spin projection. Notice, that the ground state with energy :math:`E_\mathrm{gs}=-1.136189` Ha has
spin quantum number :math:`S=0` and :math:`S_z=0` while the lowest-lying excited states,
with energy :math:`E^*=-0.478453` Ha and total spin :math:`S=1`, show a three-fold spin
degeneracy related to the values of :math:`S_z=-1, 0, 1`.

.. figure:: /demonstrations/vqe_uccsd/energy_spectra_h2_sto3g.png
    :width: 50%
    :align: center

Similarly, in the framework of VQE, if the quantum computer can be programmed to prepare many-body
states in a specific sector of the total-spin projection :math:`S_z`, the variational optimization
algorithm will allow us to estimate the energy of the lowest-lying state in this spin sector.
More specifically, if we run a VQE simulation for the :math:`\mathrm{H}_2` molecule in the
subspace of states with :math:`S_z=0` we will find the ground-state energy of the molecule. On the
other hand, if the VQE simulation is carried out in the subspace with :math:`S_z=1` the
optimized state will be in practice an excited state of the molecule as it is shown in the Figure
above.

At the core of the VQE algorithm is the variational quantum circuit that is optimized to prepare
the desired quantum states. The choice of circuit is crucial for the success of the algorithm. The
unitary coupled cluster ansatz :ref:`[4]<vqe_uccsd_references>` is a powerful quantum circuit that
is believed to outperform the classical coupled cluster method :ref:`[5]<vqe_uccsd_references>`,
traditionally referred to as the gold standard of quantum chemistry.

In this tutorial we will demonstrate how different functionalities implemented in PennyLane-QChem
can be put together to run VQE simulations in different sectors of the spin quantum numbers. We
also specify how to use the unitary coupled cluster ansatz, restricted to single and double
excitations, as the variational circuit for the algorithm. These functionalities can be
combined to estimate the energies of the ground and the lowest-lying excited states of the 
hydrogen molecule.

Let's get started! ⚛️

Building the Hamiltonian and the total spin observable :math:`\hat{S}^2`
------------------------------------------------------------------------

The first step is to import the required libraries and packages:
"""

import pennylane as qml
from pennylane import numpy as np
from pennylane import qchem
from pennylane.templates.subroutines import UCCSD

##################################################################################
# The second step is to specify the molecule whose properties we aim to calculate.
# This is done by providing the name, geometry and charge of the molecule.

name = 'h2'

##################################################################################
# The geometry of the molecule can be given in any format recognized by Open Babel.
# Here, we used a locally saved file in
# `xyz format <https://en.wikipedia.org/wiki/XYZ_file_format>`_ specifying the
# three-dimensional coordinates and symbols of the atomic species.

geometry = 'h2.xyz'

##############################################################################
# The charge determines the number of electrons that have been added or removed compared to the
# neutral molecule. In this example, we will consider a neutral molecule:

charge = 0

##############################################################################
# Now, we need to define two input parameters required to compute the mean field
# electronic structure of the molecule. First, the
# `multiplicity <https://en.wikipedia.org/wiki/Multiplicity_(chemistry)>`_ of the 
# `Hartree-Fock (HF) state <https://en.wikipedia.org/wiki/Hartree-Fock_method>`_, and
# the second one is the `atomic basis set <https://en.wikipedia.org/wiki/Basis_set_(chemistry)>`_
# used to represent the HF molecular orbitals. In this example, we will use the minimal
# basis STO-3g.

multiplicity = 1
basis_set = 'sto-3g'

##############################################################################
# PennyLane-QChem allows to define an `active space
# <https://en.wikipedia.org/wiki/Complete_active_space>`_ to expand the second-quantized
# Hamiltonian or any other observable relevant to compute different molecular properties.
# The active space is built by specifying the number of active electrons and active orbitals.
# For the hydrogen molecule described with a minimal basis set we will include all HF orbitals
# in our basis of single-particle states.

n_electrons = 2
n_orbitals = 2

##############################################################################
# Finally, to build the electronic Hamiltonian we have to define the fermionic-to-qubit
# mapping, which can be either Jordan-Wigner (``jordan_wigner``) or Bravyi-Kitaev
# (``bravyi_kitaev``). The outputs of the function :func:`~.generate_hamiltonian` are
# the qubit Hamiltonian of the molecule and the number of qubits needed to represent it:

h, n_qubits = qchem.generate_hamiltonian(
    name,
    geometry,
    charge,
    multiplicity,
    basis_set,
    n_active_electrons=n_electrons,
    n_active_orbitals=n_orbitals,
    mapping='jordan_wigner'
)

print('Number of qubits = ', n_qubits)
print('Hamiltonian is ', h)

##############################################################################
# Now, we also want to build the total spin operator :math:`\hat{S}^2`,
#
# .. math::
#
#     \hat{S}^2 = \frac{3}{4} N_e + \sum_{\alpha, \beta, \gamma, \delta}
#     \langle \alpha, \beta \vert \hat{s}_1 \cdot \hat{s}_2
#     \vert \gamma, \delta \rangle ~ \hat{c}_\alpha^\dagger \hat{c}_\beta^\dagger
#     \hat{c}_\gamma \hat{c}_\delta.
#
# In the equation above :math:`N_e` is the number of active electrons,
# :math:`\hat{c}_\alpha^\dagger` (:math:`\hat{c}_\alpha`) is the creation (annihilation)
# electron operator acting on the :math:`\alpha`-th active (spin) orbital and 
# :math:`\langle \alpha, \beta \vert \hat{s}_1 \cdot \hat{s}_2 \vert \gamma, \delta \rangle`
# are the matrix elements of the two-particle spin operator :ref:`[6]<vqe_uccsd_references>`.
#
# First, we need to load the matrix elements of the two-particle spin operator
# :math:`\hat{s}_1 \cdot \hat{s}_2`. This is achieved by calling the
# :function:`~.get_spin2_matrix_elements` which reads the Hartree-Fock electronic
# structure, defines the active space and outputs the first term :math:`\frac{3}{4} N_e`
# and the table of matrix elements.

s2_matrix_elements, first_term = qchem.get_spin2_matrix_elements(
    name,
    'pyscf/sto-3g',
    n_active_electrons=n_electrons,
    n_active_orbitals=n_orbitals
)
print(first_term)
print(s2_matrix_elements)

##############################################################################
# Here, we have input explicitly the path ``'pyscf/sto-3g'`` to the locally
# saved file ``'pyscf/sto-3g/h2.hdf5'`` storing the HF electronic structure
# of the :math:`\mathrm{H}_2` olecule. However, the :func:`~.meanfield_data` function
# can also be used to generate this information. See the tutorial
# :doc:`tutorial_quantum_chemistry`.
#
# Now that we have the two-particle spin matrix elements we call the
# :func:`~.observable` function to build the Fermionic operator and represent it in
# the basis of Pauli matrices.

s2_obs = qchem.observable(s2_matrix_elements, init_term=first_term, mapping='jordan_wigner')
print(s2_obs)

###############################################################################
# .. note::
#
#     The :func:`~.observable` function can be used to build any second-quantized many-body
#     observables as long as we have access to the matrix elements of the single- and/or 
#     two-particle operators. The keyword argument ``init_term`` contains the contribution
#     of core orbitals, if any, or other quantity required to initialize the observable.


##############################################################################
# Implementing VQE with the UCCSD ansatz
# --------------------------------------
#
# PennyLane contains the :class:`~.VQECost` class to implement the VQE algorithm.
# We begin by defining the device, in this case a qubit simulator:

dev = qml.device('default.qubit', wires=n_qubits)

##############################################################################
# The next step is to define the variational quantum circuit used to prepare
# the state that minimizes the expectation value of the electronic Hamiltonian.
# ansatz. In this example, we will use the Unitary Coupled-Cluster ansatz truncated at
# the level of single and double excitations (UCCSD) :ref:`[4]<vqe_uccsd_references>`.
# But, how does UCCSD work in practice?.
# 
# The UCCSD method is a generalization of the traditional CCSD formalism used in quantum chemistry
# to perform post-Hartree-Fock (HF) electron correlation calculations. Within the first-order
# Trotter approximation, the UCCSD ground-state of the molecule is built via the exponential ansatz
# :ref:`[7]<vqe_uccsd_references>`,
#
# .. math::
#
#     && \vert \Psi \rangle = \hat{U}(\vec{\theta}) \vert \mathrm{HF} \rangle \\ 
#     && \vert \Psi \rangle = \prod_{p > r} \mathrm{exp}
#     \Big\{\theta_{pr}(\hat{c}_p^\dagger \hat{c}_r-\mathrm{H.c.}) \Big\}
#     \prod_{p > q > r > s} \mathrm{exp} \Big\{\theta_{pqrs}
#     (\hat{c}_p^\dagger \hat{c}_q^\dagger \hat{c}_r \hat{c}_s-\mathrm{H.c.}) \Big\}.
#
# In the latter equation, the indices :math:`r, s` and :math:`p, q` run, respectively, over the
# occupied and unoccupied (virtual) molecular orbitals. Thus, the operator
# :math:`\hat{c}_p^\dagger \hat{c}_r` acting on the HF state creates one particle-hole (ph)
# excitation :ref:`[8]<vqe_uccsd_references>` since it annihilates a particle in the
# occupied HF orbital :math:`r` (creates a hole) and create the particle in the virtual orbital
# :math:`p`. Similarly, the the operator
# :math:`\hat{c}_p^\dagger \hat{c}_q^\dagger \hat{c}_r \hat{c}_s` creates two particle-hole (pphh)
# excitations when acting on the HF state. The quantum circuits to exponentiate the
# Jordan-Wigner representation of the ph and pphh excitation operators
# :ref:`[7]<vqe_uccsd_references>` are implemented by the
# :func:`~.SingleExcitationUnitary` and :func:`~.DoubleExcitationUnitary` and are part of
# the PennyLane templates library. Finally, the amplitudes :math:`\theta_{pr}` and
# :math:`\theta_{pqrs}` are precisely the parameters to be optimized to minimize the expectation
# value,
#
# .. math::
#
#     E(\vec{\theta}) = \langle \mathrm{HF} \vert \hat{U}^\dagger(\vec{\theta})
#     \hat{H} \hat{U}(\vec{\theta}) \vert \mathrm{HF} \rangle.
#
################################################################################
# .. note::
#
#     The total number of particle-hole excitations depends on the number of electrons
#     and orbitals included in the active space and determines the number of parameters
#     :math:`\theta` to be optimized by the VQE algorithm.
#
################################################################################ 
#In the circuit, we apply single-qubit rotations, followed by CNOT gates:
#
# The cost function for optimizing the circuit can be created using the :class:`~.VQECost`
# class, which is tailored for VQE optimization. It requires specifying the
# circuit, target Hamiltonian, and the device, and returns a cost function that can
# be evaluated with the circuit parameters:


cost_fn = qml.VQECost(circuit, h, dev)


##############################################################################
# Wrapping up, we fix an optimizer and randomly initialize circuit parameters. For reliable
# results, we fix the seed of the random number generator, since in practice it may be necessary
# to re-initialize the circuit several times before convergence occurs.

opt = qml.GradientDescentOptimizer(stepsize=0.4)
np.random.seed(0)
params = np.random.normal(0, np.pi, (n_qubits, 3))

print(params)

##############################################################################
# We carry out the optimization over a maximum of 200 steps, aiming to reach a convergence
# tolerance (difference in cost function for subsequent optimization steps) of :math:`\sim 10^{
# -6}`.

max_iterations = 100
max_iterations = 1
conv_tol = 1e-06

prev_energy = cost_fn(params)
for n in range(max_iterations):
    params = opt.step(cost_fn, params)
    energy = cost_fn(params)
    conv = np.abs(energy - prev_energy)

    if n % 20 == 0:
        print('Iteration = {:},  Ground-state energy = {:.8f} Ha,  Convergence parameter = {'
              ':.8f} Ha'.format(n, energy, conv))

    if conv <= conv_tol:
        break

    prev_energy = energy

print()
print('Final convergence parameter = {:.8f} Ha'.format(conv))
print('Final value of the ground-state energy = {:.8f} Ha'.format(energy))
print('Accuracy with respect to the FCI energy: {:.8f} Ha ({:.8f} kcal/mol)'.
        format(np.abs(energy - (-1.136189454088)), np.abs(energy - (-1.136189454088))*627.503))
print()
print('Final circuit parameters = \n', params)

##############################################################################
# Success! 🎉🎉🎉 The ground-state energy of the hydrogen molecule has been estimated with chemical
# accuracy (< 1 kcal/mol) with respect to the exact value of -1.136189454088 Hartree (Ha) obtained
# from a full configuration-interaction (FCI) calculation. This is because, for the optimized
# values of the single-qubit rotation angles, the state prepared by the VQE ansatz is precisely
# the FCI ground-state of the :math:`H_2` molecule :math:`|H_2\rangle_{gs} = 0.99 |1100\rangle - 0.10
# |0011\rangle`.
#
# What other molecules would you like to study using PennyLane?
#
# .. _vqe_uccsd_references:
#
# References
# ----------
#
# 1. Alberto Peruzzo, Jarrod McClean *et al.*, "A variational eigenvalue solver on a photonic
#    quantum processor". `Nature Communications 5, 4213 (2014).
#    <https://www.nature.com/articles/ncomms5213?origin=ppub>`__
#
# 2. Yudong Cao, Jonathan Romero, *et al.*, "Quantum Chemistry in the Age of Quantum Computing".
#    `Chem. Rev. 2019, 119, 19, 10856-10915.
#    <https://pubs.acs.org/doi/10.1021/acs.chemrev.8b00803>`__
#
# 3. Abhinav Kandala, Antonio Mezzacapo *et al.*, "Hardware-efficient Variational Quantum
#    Eigensolver for Small Molecules and Quantum Magnets". `arXiv:1704.05018 
#    <https://arxiv.org/abs/1704.05018>`_
#
# 4. Jonathan Romero, Ryan Babbush, *et al.*,"Strategies for quantum computing molecular 
#    energies using the unitary coupled cluster ansatz". `arXiv:1701.02691
#    <https://arxiv.org/abs/1701.02691>`_
#
# 5. Frank Jensen. "Introduction to Computational Chemistry". (John Wiley & Sons, 2016).
#
# 6. A. Fetter, J.D. Walecka, "Quantum Theory of many-particle systems". Courier Corporation, 2012.
#
# 7. P.Kl. Barkoutsos, J.F. Gonthier, *et al.*, "Quantum algorithms for electronic structure
#    calculations: particle/hole Hamiltonian and optimized wavefunction expansions".
#    `arXiv:1805.04340. <https://arxiv.org/abs/1805.04340>`_
#
# 8. P. Ring, P. Schuck. "The Nuclear Many-Body Problem". (Springer Science & Business Media, 2004).
#
