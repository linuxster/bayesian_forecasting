import unittest
import bayesian_forecasting as bf
from utilities import *
import pandas as pd
import numpy as np
from scipy.linalg import block_diag
import numpy.testing as npt

class TestCases(unittest.TestCase):
    
    def test_grid_search(self):
        """ This test makes sure the discount factor grid search
        class is initialized and populated properly."""
        T = 100
        Y = np.random.randn(T)
        F = np.identity(1)[np.newaxis,:].repeat(T,axis = 0)
        m0 = np.zeros(1)
        C0 = np.identity(1)
        V = None
        G = np.identity(1)
        grid_search = bf.GridSearchDiscountFFBS(np.linspace(0.9,0.99,2),
                                                np.linspace(0.9,0.99,2),
                                                F,G,Y,m0,C0)
        self.assertTrue((grid_search.best_evo is not None) and (grid_search.best_obs is not None) )
        
    def test_log_likelihood(self):
        """ Test for calculation of marginal model likelihood
        assuming a known, constant observational variance"""
        
        T = 4
        Y = np.random.randn(T)
        F = np.identity(1)[np.newaxis,:].repeat(T,axis = 0)
        m0 = np.zeros(1)
        C0 = np.identity(1)
        V = 1.0
        G = np.identity(1)
        ffbs = bf.FFBS(F,G,Y,m0,C0,obs_discount = False,V=V)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        ll = ffbs.ll_sum
        self.assertTrue(ll > -10.0 and ll < -4.0)
        
    def test_log_likelihood_obs_discount(self):
        """ Test for calculation of marginal model likelihood
        assuming an unknown, constant observational variance.
        under an inverse-gamma model of the variance."""
        
        T = 4
        Y = np.random.randn(T)
        F = np.identity(1)[np.newaxis,:].repeat(T,axis = 0)
        m0 = np.zeros(1)
        C0 = np.identity(1)
        V = None
        G = np.identity(1)
        ffbs = bf.FFBS(F,G,Y,m0,C0)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        ll = ffbs.ll_sum
        self.assertTrue(ll > -10.0 and ll < -4.0)
        
    def test_append_observation(self):
        """Test to make sure that adding a single new observation at the end of the data record
        gives same model score as training with that observation along with all others from the
        very start."""
        T = 4
        Y = np.random.randn(T)
        F = np.identity(1)[np.newaxis,:].repeat(T,axis = 0)
        m0 = np.zeros(1)
        C0 = np.identity(1)
        V = 1.0
        G = np.identity(1)
        ffbs = bf.FFBS(F,G,Y,m0,C0,obs_discount = False,V=V)
        ffbs.forward_filter()


        ffbs_partial = bf.FFBS(F[0:-1,:],G,Y[0:-1],m0,C0,obs_discount = False,V=V)
        ffbs_partial.forward_filter()
        new_F = F[-1,:]
        new_Y = Y[-1]
        ffbs_partial.append_observation(new_F,new_Y)
        self.assertTrue(ffbs.mae,ffbs_partial.mae)
           
    def test_ar(self):
        """ This test case simulates an AR(3) model over 10^5 timesteps with minimal variance
        and attempts to recover the original autoregression coefficients used to generate the data."""

        coefficients = np.asarray([-0.5,0.2,-0.1])
        order = len(coefficients)
        sigma = 0.05
        initial = 0.1
        length = 1000
        
        y,F = simulate_and_data_matrix_arp(coefficients,sigma,length,initial)

        G = np.identity(order)
        W = np.identity(order) * sigma
        V = 0.1
        Y = y
        m0 = np.ones(order)*0.5
        C0 = np.identity(order) * 0.25
        ffbs = bf.FFBS(F[:,:,np.newaxis],G,Y,m0,C0,W=W,
                       evolution_discount =False, V=V, obs_discount = False)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        sample = ffbs.backward_sample()
        isOkay = True
        for i in range(order):
            upper95 = np.percentile(ffbs.a[:,i],95)
            lower5 = np.percentile(ffbs.a[:,i],5)
            if not (coefficients[i] > lower5) & (coefficients[i] < upper95):
                isOkay = False
        self.assertTrue(isOkay)
         
    def test_cyclic(self):
        """ This test case attempts to model a multidecadal temperature time series 
        with a seasonal DLM of order 12 (corresponding to monthly data).
        The mean absolute deviation (i.e. the forecast error in degrees C)
        should be less than 4.0 for the last 10 years of the record."""
        
        sample_data = parse_mopex('./sample_data/brookings.csv')
        sample_data = sample_data.dropna(axis = 0)
        monthly = sample_data.groupby(pd.TimeGrouper('m')).mean()
        ld = np.log(monthly['discharge'])
        temp = monthly['max_temp']
        T = len(temp)
        p = 12
        G = permutation_matrix(p)
        W = 5.0
        V = 5.0
        Y = temp
        F = np.zeros([T,p,1])
        F[:,0,:] = 1.0
        m0 = np.ones(p)
        C0 = np.identity(p)
        ffbs = bf.FFBS(F,G,Y,m0,C0,evolution_discount = False,W=W,V=V, obs_discount = False)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        self.assertTrue(np.mean(np.abs(ffbs.e[-120::])) < 4.0)
    
    def test_cyclic_sample(self):
        """ This test case constructs a noisy sine wave, applies 
        forward filtering/backward smoothing and draws a sample
        trajectory. The observational variance is assumed to be known."""
        T = 200
        signal = np.sin(2*np.pi*np.arange(T) / 20)
        Y = signal + np.random.randn(T) * 0.5
        F = signal[:,np.newaxis,np.newaxis]
        G = np.identity(1)
        m0 = np.ones(1)* 0.5
        C0 = np.identity(1) * 0.5
        V = 1.0
        ffbs = bf.FFBS(F,G,Y,m0,C0,V=V, obs_discount = False)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        theta  = ffbs.backward_sample()
        median = np.median(theta)
        error = np.abs(1.0 - median)
        self.assertTrue(error < 0.5)
        
    def test_cyclic_sample_obs_discount(self):
        """ This test case constructs a noisy sine wave, applies 
        forward filtering/backward smoothing and draws a sample
        trajectory. The observational variance is not known."""
        T = 200
        signal = np.sin(2*np.pi*np.arange(T) / 20)
        Y = signal + np.random.randn(T)
        F = signal[:,np.newaxis,np.newaxis]
        G = np.identity(1)

        m0 = np.ones(1)* 0.5
        C0 = np.identity(1) * 0.5
        ffbs = bf.FFBS(F,G,Y,m0,C0,obs_discount = True)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        theta  = ffbs.backward_sample()
        mean   = np.mean(theta)
        median = np.median(theta)
        median_error = np.abs(1.0- median)
        mean_error   = np.abs(1.0 - mean)
        self.assertTrue(median_error < 1.5 and mean_error < 1.5)
         
    def test_cyclic_discount(self):
        """ This test case is identical to 'test_cyclic' save for 
        specification of an innovation discount factor instead of a 
        matrix W. The mean absolute deviation (i.e. the forecast error in degrees C)
        should be less than 4.0 for the last 10 years of the record."""
        
        sample_data = parse_mopex('./sample_data/brookings.csv')
        sample_data = sample_data.dropna(axis = 0)
        monthly = sample_data.groupby(pd.TimeGrouper('m')).mean()
        ld = np.log(monthly['discharge'])
        temp = monthly['max_temp']
        T = len(temp)
        p = 12
        G = permutation_matrix(p)
        V = 5.0
        Y = temp
        F = np.zeros([T,p,1])
        F[:,0,:] = 1.0
        m0 = np.ones(p)
        C0 = np.identity(p) * 5
        ffbs = bf.FFBS(F,G,Y,m0,C0,evolution_discount = True,
                       evo_discount_factor=[0.999],obs_discount = False,V=V)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        mae_error = np.mean(np.abs(ffbs.e))
        self.assertTrue(mae_error < 3.0 and mae_error > 2.0)
 
    def test_poly(self):
        """ This test case considers a simple polynomial growth model in which
        the 2nd order coefficient starts at 0.3. The mean absolute error
        of the estimated 2nd state element compared to the true 2nd state
        element should be less than 5.0 and is typically on the order of 1.0."""
        
        n = 2
        r = 1
        T = 1000
        
        static_F = np.asarray([1,0])
        G = np.asarray([[1.0,1.0],[0.0,1.0]])
        W = np.identity(2) 
        V = 1.0
        m0 = np.ones(2)
        m0[1] = 0.3
        
        states,Y = univariate_dlm_simulation(static_F,G,W,V,m0,n,T)
        F = static_F[np.newaxis,:].repeat(T,axis = 0)[:,:,np.newaxis]
        C0 = np.identity(n)
        polynomial_ffbs = bf.FFBS(F,G,Y,m0,C0,evolution_discount = False,
                                  W=W,V=V,obs_discount = False)
        polynomial_ffbs.forward_filter()
        polynomial_ffbs.backward_smooth()
        _ = polynomial_ffbs.backward_sample()
        estimated_states = polynomial_ffbs.m
        mae_error = np.mean(np.abs(estimated_states[:,1] - states[:,1]))
        self.assertTrue(mae_error < 5.0)
        
    def test_composite(self):
        """ This test case parses and loads some MOPEX hydrology data and applies
        a dynamic regression, a constant and an AR1 model component."""
        mopex = parse_mopex('./sample_data/01372500.dly')
        mopex = water_year_means(mopex)
        forcings = mopex[['precipitation','pet','max_temp','min_temp']]
        forcings['past_discharge'] = np.roll(mopex['discharge'],1)
        forcings['precipitation_squared'] = forcings['precipitation']**2
        forcings = forcings.iloc[1::]
        observations = mopex['discharge'].iloc[1::]
        assert np.any(np.isnan(forcings)) == False
        T = forcings.shape[0]

        # F_regression has shape (T,n_regression)
        F_regression = forcings.values

        # F_polynomial has shape [T,poly_order]
        F_polynomial = np.asarray([1,0])[np.newaxis,:].repeat(T,axis = 0)
        F_constant = np.asarray([1])[:,np.newaxis].repeat(T,axis = 0)
        F = np.hstack([F_regression,F_constant])[:,:,np.newaxis]
        n = F.shape[1]
        G = block_diag(*([1.0]*7))
        V = 0.2
        assert G.shape[0] == n

        ffbs = bf.FFBS(F,G,observations.values,
                       np.ones(n) * 0.1, np.identity(n) * 0.01,evo_discount_factor = [0.99],V=V,
                      obs_discount = False)
        ffbs.forward_filter()
        ffbs.backward_smooth()
        self.assertTrue(ffbs.mae < 0.3)
        
if __name__ == '__main__':
    unittest.main()