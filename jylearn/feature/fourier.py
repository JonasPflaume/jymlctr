import numpy as np
from sklearn.preprocessing import PolynomialFeatures

class FourierBases:
    def __init__(self, degree=1):
        self.degree = degree
        
    def fit_transform(self, X):
        ''' check if the first entry is 1
            Then conduct the sin cos expansion
        '''
        if np.all( X[:,0]==1. ):
            X_aug = X[:,1:]
        else:
            X_aug = np.concatenate([np.ones([X.shape[0],1], dtype='f'), X], axis=1)
        
        for k in range(1, self.degree+1):
            X_aug = np.concatenate([X_aug, np.cos(k*X)], axis=1)
            X_aug = np.concatenate([X_aug, np.sin(k*X)], axis=1)
            
        return X_aug