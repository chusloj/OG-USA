'''
------------------------------------------------------------------------
All the functions for the TPI computation for the model with S-period
lived agents, exogenous labor, and two industries and two goods.
    get_pmpath
    get_ppath
    get_cbepath

    get_cvec_lf
    LfEulerSys
    paths_life

    TPI
------------------------------------------------------------------------
'''
# Import Packages
import time
import numpy as np
import scipy.optimize as opt
import ssfuncs as ssf
reload(ssf)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from mpl_toolkits.mplot3d import Axes3D
import sys

'''
------------------------------------------------------------------------
    Functions
------------------------------------------------------------------------
'''

def get_pmpath(params, rpath, wpath):
    '''
    Generates time path of industry prices p_m from rpath and wpath

    Inputs:
        params = length 4 tuple, (A, gamma, epsilon, delta)
        A   = [M,T+S-2] matrix, total factor productivity for each
                 industry
        gamma = [M,T+S-2] matrix, capital share of income for each industry
        epsilon = [M,T+S-2] matrix, elasticity of substitution between capital
                 and labor for each industry
        delta = [M,T+S-2] matrix, capital depreciation rate for each
                 industry
        rpath  = [T+S-2,] matrix, time path of interest rate
        w      = [T+S-2,] matrix, time path of wage

    Functions called: None

    Objects in function:
        pmpath = [M, T+S-2] matrix, time path of industry prices

    Returns: pmpath
    '''
    A, gamma, epsilon, delta = params

    pmpath = (1 / A) * ((gamma * ((rpath + delta) **
                   (1 - epsilon)) + (1 - gamma) * (wpath **
                   (1 - epsilon))) ** (1 / (1 - epsilon)))

    return pmpath

def get_pcpath(pmpath, pi, I):
    '''
    Generates time path of consumption good prices from
    industry output prices and fixed coefficient matrix
    relating output goods to consumption goods.

    Inputs:
        pmpath    = [M,T+S-2] matrix of params = length 4 tuple, (A, gamma, epsilon, delta)
        pi        = [I,M] matrix, element i,j gives the fraction of consumption
        T         = integer > S, number of time periods until steady
                     state

    Functions called: None

    Objects in function:
        pcpath = [I, T+S-2] matrix, time path of consumption good prices

    Returns: pcpath
    '''

    pcpath = np.zeros((I,(pmpath.shape)[1]))
    for t in range(0,(pmpath.shape)[1]): 
        pcpath[:,t] = np.dot(pi,pmpath[:,t])


    return pcpath


def get_ppath(alpha, pcpath):
    '''
    Generates time path of composite price p from pmpath

    Inputs:
        alpha = [I, T+S-2], expenditure share on each good along time path
        pcpath = [I, T+S-2] matrix, time path of industry prices

    Functions called: None

    Objects in function:
        ppath = [T+S-2,] vector, time path of price of composite good

    Returns: ppath
    '''

    ppath = ((pcpath/alpha)**alpha).prod(axis=0)
    return ppath


def get_cbepath(params, Gamma1, rpath_init, wpath_init, pcpath, ppath,
  ci_tilde, I, n):
    '''
    Generates matrices for the time path of the distribution of
    individual savings, individual composite consumption, individual
    consumption of each type of good, and the Euler errors associated
    with the savings decisions.

    Inputs:
        params     = length 6 tuple, (S, T, alpha, beta, sigma, tp_tol)
        S          = integer in [3,80], number of periods an individual
                     lives
        T          = integer > S, number of time periods until steady
                     state
        I          = integer, number unique consumption goods
        alpha      = [I,T+S-1] matrix, expenditure shares on each good along time path
        beta       = scalar in [0,1), discount factor for each model
                     period
        sigma      = scalar > 0, coefficient of relative risk aversion
        tp_tol    = scalar > 0, tolerance level for fsolve's in TPI
        Gamma1     = [S-1,] vector, initial period savings distribution
        rpath_init = [T+S-1,] vector, initial guess for the time path of
                     the interest rate
        wpath_init = [T+S-1,] vector, initial guess for the time path of
                     the wage
        pcpath     = [I, T+S-1] matrix, time path of consumption goods prices
        ppath      = [T+S-1] vector, time path of composite price
        ci_tilde   = [I,T+S-1] matrix, minimum consumption values for all
                     goods along time path
        n          = [S,] vector, exogenous labor supply n_{s}

    Functions called:
        paths_life

    Objects in function:
        bpath      = [S-1, T+S-1] matrix, distribution of savings along time path
        cpath      = [S, T+S-1] matrix, distribution of composite consumption along time path
        cipath     = [S, T+S-1, I] array, distribution of consumption of each cons good along time path
        eulerrpath = [S-1, T+S-1] matrix, Euler equation errors along the time path
        pl_params  = length 4 tuple, parameters to pass into paths_life
                     (S, beta, sigma, TP_tol)
        p          = integer >= 2, represents number of periods
                     remaining in a lifetime, used to solve incomplete
                     lifetimes
        b_guess    = [p-1,] vector, initial guess for remaining lifetime
                     savings, taken from previous cohort's choices
        bveclf     = [p-1,] vector, optimal remaining lifetime savings
                     decisions
        cveclf     = [p,] vector, optimal remaining lifetime consumption
                     decisions
        cimatlf    = [] array, 
        b_err_veclf = [p-1,] vector, Euler errors associated with
                      optimal remaining lifetime savings decisions
        DiagMaskb   = [p-1, p-1] boolean identity matrix
        DiagMaskc   = [p, p] boolean identity matrix

    Returns: bpath, cpath, cipath, eulerrpath
    '''
    S, T, alpha, beta, sigma, tp_tol = params
    bpath = np.append(Gamma1.reshape((S-1,1)), np.zeros((S-1, T+S-2)),
            axis=1)
    cpath = np.zeros((S, T+S-1))
    cipath = np.zeros((S, T+S-1, 2))
    eulerrpath = np.zeros((S-1, T+S-1))
    # Solve the incomplete remaining lifetime decisions of agents alive
    # in period t=1 but not born in period t=1
    cpath[S-1, 0] = (1 / ppath[0]) * ((1 + rpath_init[0]) * Gamma1[S-2]
        + wpath_init[0] * n[S-1] - (pcpath[:, 0] * ci_tilde[:,0]).sum(axis=0))
    cipath[S-1, 0, :] = alpha[:,0] * ((ppath[0] * cpath[S-1, 0]) /
                        pcpath[:, 0]) + ci_tilde[:,0]
    for p in xrange(2, S):
        # b_guess = b_ss[-p+1:]
        b_guess = np.diagonal(bpath[S-p:, :p-1])
        pl_params = (S, alpha[:,:p], beta, sigma, tp_tol)
        bveclf, cveclf, cimatlf, b_err_veclf = paths_life(pl_params,
            S-p+1, Gamma1[S-p-1], ci_tilde[:,:p], n[-p:], rpath_init[:p],
            wpath_init[:p], pcpath[:, :p], ppath[:p], b_guess)
        # Insert the vector lifetime solutions diagonally (twist donut)
        # into the cpath, bpath, and EulErrPath matrices
        DiagMaskb = np.eye(p-1, dtype=bool)
        DiagMaskc = np.eye(p, dtype=bool)
        bpath[S-p:, 1:p] = DiagMaskb * bveclf + bpath[S-p:, 1:p]
        cpath[S-p:, :p] = DiagMaskc * cveclf + cpath[S-p:, :p]
        DiagMaskc_tiled = np.tile(np.expand_dims(np.eye(p, dtype=bool),axis=2),(1,1,I))
        cimatlf = np.tile(np.expand_dims(cimatlf.transpose(),axis=0),((cimatlf.shape)[1],1,1))
        cipath[S-p:, :p, :] = (DiagMaskc_tiled * cimatlf +
                              cipath[S-p:, :p, :])
        eulerrpath[S-p:, 1:p] = (DiagMaskb * b_err_veclf +
                                eulerrpath[S-p:, 1:p])
    # Solve for complete lifetime decisions of agents born in periods
    # 1 to T and insert the vector lifetime solutions diagonally (twist
    # donut) into the cpath, bpath, and EulErrPath matrices
    
    DiagMaskb = np.eye(S-1, dtype=bool)
    DiagMaskc = np.eye(S, dtype=bool)
    DiagMaskc_tiled = np.tile(np.expand_dims(np.eye(S, dtype=bool),axis=2),(1,1,I))

    for t in xrange(1, T+1): # Go from periods 1 to T
        # b_guess = b_ss
        b_guess = np.diagonal(bpath[:, t-1:t+S-2])
        pl_params = (S, alpha[:,t-1:t+S-1], beta, sigma, tp_tol)
        bveclf, cveclf, cimatlf, b_err_veclf = paths_life(pl_params, 1,
            0, ci_tilde[:,t-1:t+S-1], n, rpath_init[t-1:t+S-1],
            wpath_init[t-1:t+S-1], pcpath[:, t-1:t+S-1],
            ppath[t-1:t+S-1], b_guess)
        cimatlf = np.tile(np.expand_dims(cimatlf.transpose(),axis=0),((cimatlf.shape)[1],1,1))
        # Insert the vector lifetime solutions diagonally (twist donut)
        # into the cpath, bpath, and EulErrPath matrices
        bpath[:, t:t+S-1] = DiagMaskb * bveclf + bpath[:, t:t+S-1]
        cpath[:, t-1:t+S-1] = DiagMaskc * cveclf + cpath[:, t-1:t+S-1]
        cipath[:, t-1:t+S-1, :] = (DiagMaskc_tiled * cimatlf +
                                  cipath[:, t-1:t+S-1, :])
        eulerrpath[:, t:t+S-1] = (DiagMaskb * b_err_veclf +
                                 eulerrpath[:, t:t+S-1])
    print 'bpath FIRMS: ', bpath
    quit()
    return bpath, cpath, cipath, eulerrpath


def paths_life(params, beg_age, beg_wealth, ci_tilde, n, rpath,
               wpath, pcpath, ppath, b_init):
    '''
    Solve for the remaining lifetime savings decisions of an individual
    who enters the model at age beg_age, with corresponding initial
    wealth beg_wealth.

    Inputs:
        params     = length 5 tuple, (S, alpha, beta, sigma, tp_tol)
        S          = integer in [3,80], number of periods an individual
                     lives
        alpha      = [I,S-beg_age+1], expenditure share on good for remaing lifetime
        beta       = scalar in [0,1), discount factor for each model
                     period
        sigma      = scalar > 0, coefficient of relative risk aversion
        tp_tol    = scalar > 0, tolerance level for fsolve's in TPI
        beg_age    = integer in [1,S-1], beginning age of remaining life
        beg_wealth = scalar, beginning wealth at beginning age
        n       = [S-beg_age+1,] vector, remaining exogenous labor
                     supplies
        rpath      = [S-beg_age+1,] vector, remaining lifetime interest
                     rates
        wpath      = [S-beg_age+1,] vector, remaining lifetime wages
        pcpath     = [I, S-beg_age+1] matrix, remaining lifetime
                     consumption good prices
        ppath      = [S-beg_age+1,] vector, remaining lifetime composite
                     goods prices
        b_init     = [S-beg_age,] vector, initial guess for remaining
                     lifetime savings

    Functions called:
        LfEulerSys
        get_cvec_lf
        c4ssf.get_b_errors

    Objects in function:
        p            = integer in [2,S], remaining periods in life
        b_guess      = [p-1,] vector, initial guess for lifetime savings
                       decisions
        eullf_objs   = length 9 tuple, objects to be passed in to
                       LfEulerSys: (p, beta, sigma, beg_wealth, n,
                       rpath, wpath, pmpath, ppath)
        bpath        = [p-1,] vector, optimal remaining lifetime savings
                       decisions
        cpath        = [p,] vector, optimal remaining lifetime
                       consumption decisions
        cipath       = [p,I] martrix, remaining lifetime consumption
                        decisions by consumption good
        c_constr     = [p,] boolean vector, =True if c_{p}<=0,
        b_err_params = length 2 tuple, parameters to pass into
                       c4ssf.get_b_errors (beta, sigma)
        b_err_vec    = [p-1,] vector, Euler errors associated with
                       optimal savings decisions

    Returns: bpath, cpath, cipath, b_err_vec
    '''
    S, alpha, beta, sigma, tp_tol = params
    p = int(S - beg_age + 1)
    if beg_age == 1 and beg_wealth != 0:
        sys.exit("Beginning wealth is nonzero for age s=1.")
    if len(rpath) != p:
        #print len(rpath), S-beg_age+1
        sys.exit("Beginning age and length of rpath do not match.")
    if len(wpath) != p:
        sys.exit("Beginning age and length of wpath do not match.")
    if len(n) != p:
        sys.exit("Beginning age and length of n do not match.")
    b_guess = 1.01 * b_init
    eullf_objs = (p, beta, sigma, beg_wealth, ci_tilde, n, rpath,
                  wpath, pcpath, ppath)
    bpath = opt.fsolve(LfEulerSys, b_guess, args=(eullf_objs),
                       xtol=tp_tol)
    cpath, c_cstr = get_cvec_lf(ci_tilde, rpath, wpath, pcpath, ppath,
                    n, np.append(beg_wealth, bpath))
    cipath, cm_cstr = get_cimat_lf(alpha[:,:p], ci_tilde, cpath, pcpath, ppath)
    b_err_params = (beta, sigma)
    b_err_vec = ssf.get_b_errors(b_err_params, rpath[1:], cpath,
                                   c_cstr, diff=True)
    return bpath, cpath, cipath, b_err_vec


def LfEulerSys(bvec, *objs):
    '''
    Generates vector of all Euler errors for a given bvec, which errors
    characterize all optimal lifetime decisions

    Inputs:
        bvec       = [p-1,] vector, remaining lifetime savings decisions
                     where p is the number of remaining periods
        objs       = length 9 tuple, (p, beta, sigma, beg_wealth, n,
                     rpath, wpath, pmpath, ppath)
        p          = integer in [2,S], remaining periods in life
        beta       = scalar in [0,1), discount factor
        sigma      = scalar > 0, coefficient of relative risk aversion
        beg_wealth = scalar, wealth at the beginning of first age
        n       = [p,] vector, remaining exogenous labor supply
        rpath      = [p,] vector, interest rates over remaining life
        wpath      = [p,] vector, wages rates over remaining life
        pcpath     = [I, p] matrix, remaining lifetime
                     consumption good prices
        ppath      = [p,] vector, remaining lifetime composite
                     goods prices
        ppath      = 

    Functions called:
        get_cvec_lf
        ssf.get_b_errors

    Objects in function:
        bvec2        = [p, ] vector, remaining savings including initial
                       savings
        cvec         = [p, ] vector, remaining lifetime consumption
                       levels implied by bvec2
        c_constr     = [p, ] boolean vector, =True if c_{s,t}<=0
        b_err_params = length 2 tuple, parameters to pass into
                       get_b_errors (beta, sigma)
        b_err_vec    = [p-1,] vector, Euler errors from lifetime
                       consumption vector

    Returns: b_err_vec
    '''
    (p, beta, sigma, beg_wealth, ci_tilde, n, rpath, wpath, pcpath,
        ppath) = objs
    bvec2 = np.append(beg_wealth, bvec)
    cvec, c_cstr = get_cvec_lf(ci_tilde, rpath, wpath, pcpath, ppath,
                               n, bvec2)
    b_err_params = (beta, sigma)
    b_err_vec = ssf.get_b_errors(b_err_params, rpath[1:], cvec,
                                   c_cstr, diff=True)
    return b_err_vec


def get_cvec_lf(ci_tilde, rpath, wpath, pcpath, ppath, n, bvec):
    '''
    Generates vector of remaining lifetime consumptions from individual
    savings, and the time path of interest rates and the real wages

    Inputs:
        p      = integer in [2,80], number of periods remaining in
                 individual life
        rpath  = [p,] vector, remaining interest rates
        wpath  = [p,] vector, remaining wages
        pcpath = [I, p] matrix, remaining industry prices
        ppath  = [p,] vector, remaining composite prices
        n   = [p,] vector, remaining exogenous labor supply
        bvec   = [p,] vector, remaining savings including initial
                 savings

    Functions called: None

    Objects in function:
        c_cstr = [p,] boolean vector, =True if element c_s <= 0
        b_s    = [p,] vector, bvec
        b_sp1  = [p,] vector, last p-1 elements of bvec and 0 in last
                 element
        cvec   = [p,] vector, remaining consumption by age c_s

    Returns: cvec, c_constr
    '''
    b_s = bvec
    b_sp1 = np.append(bvec[1:], [0])
    cvec = (1 / ppath) *((1 + rpath) * b_s + wpath * n -
           (pcpath * ci_tilde).sum(axis=0) - b_sp1)
    c_cstr = cvec <= 0
    return cvec, c_cstr


def get_cimat_lf(alpha, ci_tilde, cpath, pcpath, ppath):
    '''
    Generates matrix of remaining lifetime consumptions of individual
    goods

    Inputs:
        p      = integer in [2,80], number of periods remaining in
                 individual life
        rpath  = [p,] vector, remaining interest rates
        wpath  = [p,] vector, remaining wages
        pcpath = [I, p] matrix, remaining industry prices
        ppath  = [p,] vector, remaining composite prices
        n   = [p,] vector, remaining exogenous labor supply
        bvec   = [p,] vector, remaining savings including initial
                 savings

    Functions called: None

    Objects in function:
        c_cstr = [p,] boolean vector, =True if element c_s <= 0
        b_s    = [p,] vector, bvec
        b_sp1  = [p,] vector, last p-1 elements of bvec and 0 in last
                 element
        cvec   = [p,] vector, remaining consumption by age c_s

    Returns: cvec, c_constr
    '''

    cimat = alpha * ((ppath * cpath) / pcpath) + ci_tilde

    cm_cstr = cimat <= 0
    return cimat, cm_cstr


def get_Cipath(cipath):
    '''
    Generates vector of aggregate consumption C_m of good m

    Inputs:
        cipath = [S, S+T-1, I] array, time path of distribution of
                 individual consumption of each good c_{m,s,t}

    Functions called: None

    Objects in function:
        Cipath = [I,S+T-1] matrix, aggregate consumption of all goods

    Returns: Cipath
    '''
    
    Cipath = np.reshape(cipath[:, :, :].sum(axis=0),((cipath.shape)[2],(cipath.shape)[1]))

    return Cipath



def solve_Ympath(Ympath_init_guess, params, rpath, wpath, Cipath, A, gamma,
  epsilon, delta, xi, pi, I, M):

    '''
    Generate matrix (vectors) of time path of aggregate output Y_{m,t}
    by industry given r_t, w_t, and C_{m,t}
    
    Inputs:
        Ympath_init_guess = [M*T,] vector, initial guess of Ympath
        Km_ss             = [M,] vector, steady-state capital stock by industry 
        rpath             = [T,] vector, real interest rates
        wpath             = [T,] vector, real wage rates
        Cipath            = [I,T] matrix, aggregate consumption of each good
                             along the time path     
        A                 = [M,T] matrix, total factor productivity values for all
                            industries
        gamma             = [M,T] matrix, capital shares of income for all
                            industries
        epsilon           = [M,T] matrix, elasticities of substitution between
                            capital and labor for all industries
        delta             = [M,T] matrix, model period depreciation rates for all
                            industries
        xi                = [M,M] matrix, element i,j gives the fraction of capital used by 
                            industry j that comes from the output of industry i
        pi                = [I,M] matrix, element i,j gives the fraction of consumption
        T                 = integer > S, number of time periods until steady
                           state
        I                 = integer, number unique consumption goods
        M                 = integer, number unique production industires 


    Functions called: None

    Objects in function:
        Inv = [M,T] matrix, investment demand from each industry
        Y_inv = [M,T] matrix, demand for output from each industry due to 
                 investment demand
        Y_c   = [M,T] matrix, demand for output from each industry due to 
                 consumption demand
        Kmpath  = [M,T] matrix, capital demand of all industries
        Ympath  = [M,T] matrix, output from each industry
        rc_errors = [M*T,] vector, errors in resource constraint
                    for each production industry along time path

    Returns: rc_errors
    '''

    T, Km_ss = params

    #unpack guesses, which needed to be a vector
    Ympath = np.zeros((M,T))
    for m in range(0,M):
        Ympath[m,:] = Ympath_init_guess[(m*T):((m+1)*T)]
    
    Kmpath = get_Kmpath(rpath, wpath, Ympath, A, gamma, epsilon, delta)
    Inv = np.zeros((M,T))
    Inv[:,:-1] = Kmpath[:,1:] - (1-delta[:,:-1])*Kmpath[:,:-1]
    Inv[:,T-1] = Km_ss - (1-delta[:,T-1])*Kmpath[:,T-1]

    Y_inv = np.zeros((M,T))
    Y_c = np.zeros((M,T))
    for t in range(0,T):
        Y_inv[:,t] = np.dot(Inv[:,t],xi)
        Y_c[:,t] = np.dot(np.reshape(Cipath[:,t],(1,I)),pi)

    rc_errors = np.reshape(Y_c  + Y_inv - Ympath,(M*T,))

    return rc_errors
    

def get_Kmpath(rpath, wpath, Ympath, A, gamma, epsilon, delta):
    '''
    Generates vector of capital demand from production industry m 
    along the time path for a given Ympath, rpath, wpath.

    Inputs:
        rpath      = [T,] vector, real interest rates
        wpath      = [T,] vector, real wage rates
        Ympath  = [M,T] matrix, output from each industry
        A       = [M,T] matrix, total factor productivity values for all
                   industries
        gamma = [M,T] matrix, capital shares of income for all
                 industries
        epsilon = [M,T] matrix, elasticities of substitution between
                 capital and labor for all industries
        delta = [M,T] matrix, model period depreciation rates for all
                 industries

    Functions called: None

    Objects in function:
        aa    = [M,T] matrix, gamma
        bb    = [M,T] matrix, 1 - gamma
        cc    = [M,T] matrix, (1 - gamma) / gamma
        dd    = [M,T] matrix, (r + delta) / w
        ee    = [M,T] matrix, 1 / epsilon
        ff    = [M,T] matrix, (epsilon - 1) / epsilon
        gg    = [M,T] matrix, epsilon - 1
        hh    = [M,T] matrix, epsilon / (1 - epsilon)
        ii    = [M,T] matrix, ((1 / A) * (((aa ** ee) + (bb ** ee) *
                (cc ** ff) * (dd ** gg)) ** hh))
        Kmpath = [M,T] matrix, capital demand of all industries

    Returns: Kmpath
    '''
    aa = gamma
    bb = 1 - gamma
    cc = (1 - gamma) / gamma
    dd = (rpath + delta) / wpath
    ee = 1 / epsilon
    ff = (epsilon - 1) / epsilon
    gg = epsilon - 1
    hh = epsilon / (1 - epsilon)

    Kmpath = ((Ympath / A) *
         (((aa ** ee) + (bb ** ee) * (cc ** ff) * (dd ** gg)) ** hh))

    return Kmpath



def get_Lmpath(Kmpath, rpath, wpath, gamma, epsilon, delta):
    '''
    Generates vector of labor demand L_m for good m given Y_m, p_m and w

    Inputs:
        Kmpath = [M, T] matrix, time path of aggregate output by
                 industry
        rpath  = [T, ] matrix, time path of real interest rate
        wpath  = [T, ] matrix, time path of real wage
        gamma = [M,T] matrix, capital shares of income for all
                 industries
        epsilon = [M,T] matrix, elasticities of substitution between
                 capital and labor for all industries
        delta = [M,T] matrix, rate of phyical depreciation for all industries

    Functions called: None

    Objects in function:
        Lmpath = [M,T] matrix, labor demand from each industry

    Returns: Lmpath
    '''
    Lmpath = Kmpath*((1-gamma)/gamma)*(((rpath+delta)/wpath)**epsilon)

    return Lmpath




def TP(params, rpath_init, wpath_init, Km_ss, Ym_ss, Gamma1, ci_tilde, A,
  gamma, epsilon, delta, xi, pi, I, M, S, n, graphs):

    '''
    Generates equilibrium time path for all endogenous objects from
    initial state (Gamma1) to the steady state using initial guesses
    rpath_init and wpath_init.

    Inputs:
        params     = length 11 tuple, (S, T, alpha, beta, sigma, r_ss,
                     w_ss, maxiter, mindist, xi, tp_tol)
        S          = integer in [3,80], number of periods an individual
                     lives
        T          = integer > S, number of time periods until steady
                     state
        I          = integer, number unique consumption goods
        M          = integer, number unique production industires
        alpha      = [I,T+S-1] matrix, expenditure share on each good
                      along the time path
        beta       = scalar in [0,1), discount factor for each model
                     period
        sigma      = scalar > 0, coefficient of relative risk aversion
        r_ss       = scalar > 0, steady-state interest rate
        w_ss       = scalar > 0, steady-state wage
        tp_tol    = scalar > 0, tolerance level for fsolve's in TP solution
        rpath_init = [T+S-1,] vector, initial guess for the time path of
                     the interest rate
        wpath_init = [T+S-1,] vector, initial guess for the time path of
                     the wage
        Ym_ss      = [M,] vector, steady-state industry output levels
        Gamma1     = [S-1,] vector, initial period savings distribution
        ci_tilde   = [I,T+S-1] matrix, minimum consumption values for all
                     goods
        A       = [M,T+S-1] matrix, total factor productivity values for
                     all industries
        gamma     = [M,T+S-1] matrix, capital shares of income for all
                     industries
        epsilon     = [M,T+S-1] matrix, elasticities of substitution between
                     capital and labor for all industries
        delta     = [M,T+S-1] matrix, model period depreciation rates for
                     all industries
        xi      = [M,M] matrix, element i,j gives the fraction of capital used by 
               industry j that comes from the output of industry i
        pi      = [I,M] matrix, element i,j gives the fraction of consumption
        n       = [S,] vector, exogenous labor supply n_{s}
        graphs     = boolean, =True if want graphs of TPI objects

    Functions called:
        get_pmpath
        get_ppath
        get_cbepath

    Objects in function:
        start_time   = scalar, current processor time in seconds (float)
        pm_params    = length 4 tuple, objects to be passed to
                       get_pmpath function:
                       (A, gamma, epsilon, delta)
        pmpath       = [M, T+S-1] matrix, time path of industry output prices
        pcpath       = [I, T+S-1] matrix, time path of consumption good prices
        ppath        = [T+S-1] vector, time path of composite price

        r_params     = length 3 tuple, parameters passed in to get_r
        w_params     = length 2 tuple, parameters passed in to get_w
        cbe_params   = length 5 tuple. parameters passed in to
                       get_cbepath
        rpath        = [T+S-2,] vector, equilibrium time path of the
                       interest rate
        wpath        = [T+S-2,] vector, equilibrium time path of the
                       real wage
        cpath        = [S, T+S-2] matrix, equilibrium time path values
                       of individual consumption c_{s,t}
        bpath        = [S-1, T+S-2] matrix, equilibrium time path values
                       of individual savings b_{s+1,t+1}
        EulErrPath   = [S-1, T+S-2] matrix, equilibrium time path values
                       of Euler errors corresponding to individual
                       savings b_{s+1,t+1} (first column is zeros)
        Kpath_constr = [T+S-2,] boolean vector, =True if K_t<=0
        Kpath        = [T+S-2,] vector, equilibrium time path of the
                       aggregate capital stock
        Y_params     = length 2 tuple, parameters to be passed to get_Y
        Ympath        = [M,T+S-2] matrix, equilibrium time path of
                       industry output 
        Cipath        = [I, T+S-2] matrix, equilibrium time path of
                       aggregate consumption
        elapsed_time = scalar, time to compute TPI solution (seconds)

    Returns: bpath, cpath, wpath, rpath, Kpath, Ypath, Cpath,
             EulErrpath, elapsed_time
    '''
    start_time = time.clock()
    (S, T, alpha, beta, sigma, r_ss, w_ss, tp_tol) = params

    rpath = np.zeros(T+S-1)
    wpath = np.zeros(T+S-1)
    rpath[:T] = rpath_init[:T]
    wpath[:T] = wpath_init[:T]
    rpath[T:] = r_ss
    wpath[T:] = w_ss


    pm_params = (A, gamma, epsilon, delta)
    pmpath = get_pmpath(pm_params, rpath, wpath)
    pcpath = get_pcpath(pmpath, pi, I)
    ppath = get_ppath(alpha, pcpath)
    cbe_params = (S, T, alpha, beta, sigma, tp_tol)
    bpath, cpath, cipath, eulerrpath = get_cbepath(cbe_params,
        Gamma1, rpath, wpath, pcpath, ppath, ci_tilde, I,
        n)
    Cipath = get_Cipath(cipath[:, :T, :])

    Ympath_params = (T, Km_ss)
    Ympath_init = np.zeros((M,T))
    for t in range(0,T):
        Ympath_init[:,t] = np.reshape((np.dot(np.reshape(Cipath[:,t],(1,I)),pi))/I,(M,))

    Ympath_init_guess = np.reshape(Ympath_init,(T*I,)) #need a vector going into fsolve

    Ympath_sol = opt.fsolve(solve_Ympath, Ympath_init_guess, args=(Ympath_params, rpath[:T], wpath[:T], 
             Cipath, A[:,:T], gamma[:,:T], epsilon[:,:T], delta[:,:T], xi, pi, I, 
             M), xtol=tp_tol, col_deriv=1)
    Ympath = np.zeros((M,T))
    for m in range(0,M): # unpack vector of Ympath solved by fsolve
        Ympath[m,:] = Ympath_sol[(m*T):((m+1)*T)]

    Kmpath = get_Kmpath(rpath[:T], wpath[:T], Ympath, A[:,:T], gamma[:,:T], epsilon[:,:T], delta[:,:T])

    Lmpath = get_Lmpath(Kmpath, rpath[:T], wpath[:T], gamma[:,:T], epsilon[:,:T], delta[:,:T])
    
    RCdiff_path = (Ympath[:, :T-1] - Cipath[:, :T-1] - Kmpath[:, 1:T] +
                (1 - delta[:,:T-1]) * Kmpath[:, :T-1])
    
    MCKerrpath = bpath[:, :T].sum(axis=0) - Kmpath.sum(axis=0)
    MCLerrpath = n.sum() - Lmpath.sum(axis=0)
    elapsed_time = time.clock() - start_time

    if graphs == True:
        # Plot time path of aggregate capital stock
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        #plt.plot(tvec, Kmpath[0,:T])
        plt.plot(tvec, Kmpath[1,:T])
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for aggregate capital stock')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'Aggregate capital $K_{t}$')
        # plt.savefig('Kt_Sec2')
        plt.show()

        # Plot time path of aggregate output (GDP)
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, Ympath[0,:T])
        plt.plot(tvec, Ympath[1,:T])
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for aggregate output (GDP)')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'Aggregate output $Y_{t}$')
        # plt.savefig('Yt_Sec2')
        plt.show()

        # Plot time path of aggregate consumption
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, Cipath[0,:T])
        plt.plot(tvec, Cipath[1,:T])
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for aggregate consumption')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'Aggregate consumption $C_{t}$')
        # plt.savefig('Ct_Sec2')
        plt.show()

        
        # Plot time path of real wage
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, wpath[:T])
        plt.plot(tvec, np.ones(T)*w_ss)
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for real wage')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'Real wage $w_{t}$')
        # plt.savefig('wt_Sec2')
        plt.show()

        # Plot time path of real interest rate
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, rpath[:T])
        plt.plot(tvec, np.ones(T)*r_ss)
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for real interest rate')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'Real interest rate $r_{t}$')
        # plt.savefig('rt_Sec2')
        plt.show()

        # Plot time path of the differences in the resource constraint
        tvec = np.linspace(1, T-1, T-1)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, ResmDiff[0,:T-1])
        plt.plot(tvec, ResmDiff[1,:T-1])
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for resource constraint')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'RC Difference')
        # plt.savefig('wt_Sec2')
        plt.show()

        # Plot time path of the differences in the market clearing conditions
        tvec = np.linspace(1, T, T)
        minorLocator   = MultipleLocator(1)
        fig, ax = plt.subplots()
        plt.plot(tvec, MCKerrpath[:T])
        plt.plot(tvec, MCLerrpath[:T])
        # for the minor ticks, use no labels; default NullFormatter
        ax.xaxis.set_minor_locator(minorLocator)
        plt.grid(b=True, which='major', color='0.65',linestyle='-')
        plt.title('Time path for resource constraint')
        plt.xlabel(r'Period $t$')
        plt.ylabel(r'RC Difference')
        # plt.savefig('wt_Sec2')
        plt.show()

        # Plot time path of individual savings distribution
        tgrid = np.linspace(1, T, T)
        sgrid = np.linspace(2, S, S - 1)
        tmat, smat = np.meshgrid(tgrid, sgrid)
        cmap_bp = matplotlib.cm.get_cmap('summer')
        fig = plt.figure()
        ax = fig.gca(projection='3d')
        ax.set_xlabel(r'period-$t$')
        ax.set_ylabel(r'age-$s$')
        ax.set_zlabel(r'individual savings $b_{s,t}$')
        strideval = max(int(1), int(round(S/10)))
        ax.plot_surface(tmat, smat, bpath[:, :T], rstride=strideval,
            cstride=strideval, cmap=cmap_bp)
        # plt.savefig('bpath')
        plt.show()

        # Plot time path of individual savings distribution
        tgrid = np.linspace(1, T-1, T-1)
        sgrid = np.linspace(1, S, S)
        tmat, smat = np.meshgrid(tgrid, sgrid)
        cmap_cp = matplotlib.cm.get_cmap('summer')
        fig = plt.figure()
        ax = fig.gca(projection='3d')
        ax.set_xlabel(r'period-$t$')
        ax.set_ylabel(r'age-$s$')
        ax.set_zlabel(r'individual consumption $c_{s,t}$')
        strideval = max(int(1), int(round(S/10)))
        ax.plot_surface(tmat, smat, cpath[:, :T-1], rstride=strideval,
            cstride=strideval, cmap=cmap_cp)
        # plt.savefig('bpath')
        plt.show()

    return (rpath, wpath, pmpath, ppath, bpath, cpath, cipath,
        eulerrpath, Cipath, Ympath, Kmpath, Lmpath, MCKerrpath,
        MCLerrpath, elapsed_time)


def TP_fsolve(guesses, params, Km_ss, Ym_ss, Gamma1, ci_tilde, A,
  gamma, epsilon, delta, xi, pi, I, M, S, n, graphs):

    '''
    Generates equilibrium time path for all endogenous objects from
    initial state (Gamma1) to the steady state using initial guesses
    rpath_init and wpath_init.

    Inputs:
        params     = length 11 tuple, (S, T, alpha, beta, sigma, r_ss,
                     w_ss, maxiter, mindist, xi, tp_tol)
        S          = integer in [3,80], number of periods an individual
                     lives
        T          = integer > S, number of time periods until steady
                     state
        I          = integer, number unique consumption goods
        M          = integer, number unique production industires
        alpha      = [I,T+S-1] matrix, expenditure share on each good
                      along the time path
        beta       = scalar in [0,1), discount factor for each model
                     period
        sigma      = scalar > 0, coefficient of relative risk aversion
        r_ss       = scalar > 0, steady-state interest rate
        w_ss       = scalar > 0, steady-state wage
        tp_tol    = scalar > 0, tolerance level for fsolve's in TP solution
        rpath_init = [T+S-1,] vector, initial guess for the time path of
                     the interest rate
        wpath_init = [T+S-1,] vector, initial guess for the time path of
                     the wage
        Ym_ss      = [M,] vector, steady-state industry output levels
        Gamma1     = [S-1,] vector, initial period savings distribution
        ci_tilde   = [M,T+S-1] matrix, minimum consumption values for all
                     goods
        A       = [M,T+S-1] matrix, total factor productivity values for
                     all industries
        gamma     = [M,T+S-1] matrix, capital shares of income for all
                     industries
        epsilon     = [M,T+S-1] matrix, elasticities of substitution between
                     capital and labor for all industries
        delta     = [M,T+S-1] matrix, model period depreciation rates for
                     all industries
        xi      = [M,M] matrix, element i,j gives the fraction of capital used by 
               industry j that comes from the output of industry i
        pi      = [I,M] matrix, element i,j gives the fraction of consumption
        n       = [S,] vector, exogenous labor supply n_{s}
        graphs     = boolean, =True if want graphs of TPI objects

    Functions called:
        get_pmpath
        get_ppath
        get_cbepath

    Objects in function:
        start_time   = scalar, current processor time in seconds (float)
        rpath_new    = [T+S-2,] vector, new time path of the interest
                       rate implied by household and firm optimization
        wpath_new    = [T+S-2,] vector, new time path of the wage
                       implied by household and firm optimization
        pm_params    = length 4 tuple, objects to be passed to
                       get_pmpath function:
                       (A, gamma, epsilon, delta)
        pmpath       = [M, T+S-1] matrix, time path of industry output prices
        pcpath       = [I, T+S-1] matrix, time path of consumption good prices
        ppath        = [T+S-1] vector, time path of composite price

        r_params     = length 3 tuple, parameters passed in to get_r
        w_params     = length 2 tuple, parameters passed in to get_w
        cbe_params   = length 5 tuple. parameters passed in to
                       get_cbepath
        rpath        = [T+S-2,] vector, equilibrium time path of the
                       interest rate
        wpath        = [T+S-2,] vector, equilibrium time path of the
                       real wage
        cpath        = [S, T+S-2] matrix, equilibrium time path values
                       of individual consumption c_{s,t}
        bpath        = [S-1, T+S-2] matrix, equilibrium time path values
                       of individual savings b_{s+1,t+1}
        EulErrPath   = [S-1, T+S-2] matrix, equilibrium time path values
                       of Euler errors corresponding to individual
                       savings b_{s+1,t+1} (first column is zeros)
        Kpath_constr = [T+S-2,] boolean vector, =True if K_t<=0
        Kpath        = [T+S-2,] vector, equilibrium time path of the
                       aggregate capital stock
        Y_params     = length 2 tuple, parameters to be passed to get_Y
        Ympath        = [M,T+S-2] matrix, equilibrium time path of
                       industry output 
        Cipath        = [I, T+S-2] matrix, equilibrium time path of
                       aggregate consumption
        elapsed_time = scalar, time to compute TPI solution (seconds)

    Returns: bpath, cpath, wpath, rpath, Kpath, Ypath, Cpath,
             EulErrpath, elapsed_time
    '''
    start_time = time.clock()
    (S, T, alpha, beta, sigma, r_ss, w_ss, tp_tol) = params

    rpath = np.zeros(T+S-1)
    wpath = np.zeros(T+S-1)
    rpath[:T] = guesses[0:T]
    wpath[:T] = guesses[T:]
    rpath[T:] = r_ss
    wpath[T:] = w_ss


    pm_params = (A, gamma, epsilon, delta)
    pmpath = get_pmpath(pm_params, rpath, wpath)
    pcpath = get_pcpath(pmpath, pi, I)
    ppath = get_ppath(alpha, pcpath)
    cbe_params = (S, T, alpha, beta, sigma, tp_tol)
    bpath, cpath, cipath, eulerrpath = get_cbepath(cbe_params,
        Gamma1, rpath, wpath, pcpath, ppath, ci_tilde, I,
        n)
    print 'bpath FIRMS: ', bpath 
    print 'bpath shape: ', bpath.shape
    print 'rpath', rpath
    quit()
    Cipath = get_Cipath(cipath[:, :T, :])

    Ympath_params = (T, Km_ss)
    Ympath_init = np.zeros((M,T))
    for t in range(0,T):
        Ympath_init[:,t] = np.reshape((np.dot(np.reshape(Cipath[:,t],(1,I)),pi))/I,(M,))

    Ympath_init_guess = np.reshape(Ympath_init,(T*I,)) #need a vector going into fsolve

    Ympath_sol = opt.fsolve(solve_Ympath, Ympath_init_guess, args=(Ympath_params, rpath[:T], wpath[:T], 
             Cipath, A[:,:T], gamma[:,:T], epsilon[:,:T], delta[:,:T], xi, pi, I, 
             M), xtol=tp_tol, col_deriv=1)
    Ympath = np.zeros((M,T))
    for m in range(0,M): # unpack vector of Ympath solved by fsolve
        Ympath[m,:] = Ympath_sol[(m*T):((m+1)*T)]

    Kmpath = get_Kmpath(rpath[:T], wpath[:T], Ympath, A[:,:T], gamma[:,:T], epsilon[:,:T], delta[:,:T])

    Lmpath = get_Lmpath(Kmpath, rpath[:T], wpath[:T], gamma[:,:T], epsilon[:,:T], delta[:,:T])

    #print 'Kmpath: ', Kmpath
    #print 'Lmpath: ', Lmpath

    # Check market clearing in each period
    K_market_error = bpath[:, :T].sum(axis=0) - Kmpath[:, :].sum(axis=0)
    L_market_error = n.sum() - Lmpath[:, :].sum(axis=0)

    # Check and punish constraing violations
    mask1 = rpath[:T] <= 0
    mask2 = wpath[:T] <= 0
    mask3 = np.isnan(rpath[:T])
    mask4 = np.isnan(wpath[:T])
    K_market_error[mask1] += 1e14
    L_market_error[mask2] += 1e14
    K_market_error[mask3] += 1e14
    L_market_error[mask4] += 1e14


    print 'max capital market clearing distance: ', np.absolute(K_market_error).max()
    print 'max labor market clearing distance: ', np.absolute(L_market_error).max()
    print 'min capital market clearing distance: ', np.absolute(K_market_error).min()
    print 'min labor market clearing distance: ', np.absolute(L_market_error).min()

    errors = np.append(K_market_error, L_market_error)

    return errors

