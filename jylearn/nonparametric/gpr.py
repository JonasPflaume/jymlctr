from jylearn.parametric.regression import Regression
import torch as th
from torch.optim import LBFGS, Adam
from tqdm import tqdm
device = "cuda" if th.cuda.is_available() else "cpu"
th.pi = th.acos(th.zeros(1)).item() * 2

class ExactGPR(Regression):
    
    def __init__(self, kernel):
        '''
            kernel:
                    the kernel function
        '''
        self.kernel = kernel

    def fit(self, X, Y, call_hyper_opt=False, optimizer_type="LBFGS", **kwargs):
        '''
        '''
        if len(X.shape) == 1:
            # in case the data is 1-d
            X = X.reshape(-1,1)
        if len(Y.shape) == 1:
            Y = Y.reshape(-1,1)
        n = X.shape[0]
        d = X.shape[1]
        m = Y.shape[1] # output dimension
        self._X = X.clone().detach()
        # call the hyperparameter optimization
        
        if call_hyper_opt:
            lr, epoch = kwargs.get("lr"), kwargs.get("epoch")
            evidence = float("-inf")
            self.kernel.train()
            pbar = tqdm(range(epoch), desc =str(evidence))
            if optimizer_type == "LBFGS":
                optimizer = LBFGS(params=self.kernel.parameters(), 
                                    lr=lr, 
                                    max_iter=10)
                
                self.curr_evidence = evidence
                def closure():
                    optimizer.zero_grad()
                    evidence = ExactGPR.evidence(self.kernel, X, Y)
                    self.curr_evidence = evidence.item()
                    objective = -evidence
                    objective.backward()
                    return objective
                
                for _ in pbar:
                    optimizer.step(closure)
                    pbar.set_description("{:.2f}".format(self.curr_evidence))
            elif optimizer_type == "Adam":
                optimizer = Adam(params=self.kernel.parameters(), lr=lr)
                self.curr_evidence = evidence
                batch_size = kwargs.get("batch_size", 256)
                for _ in pbar:
                    optimizer.zero_grad()
                    batch_index = th.randperm(len(X))[:batch_size]
                    evidence = ExactGPR.evidence(self.kernel, X[batch_index], Y[batch_index])
                    self.curr_evidence = evidence.item()
                    objective = -evidence
                    objective.backward()
                    optimizer.step()
                    pbar.set_description("{:.2f}".format(self.curr_evidence))
                    
                    # this technique can be used in sgd methods
                    for p in self.kernel.parameters():
                        p.data.clamp_(0)
                
            self.kernel.eval()
            self.kernel.stop_autograd()
        
        K = self.kernel(X, X) # K has shape (ny, n, n)
        try:
            u = th.cholesky(K) # u has shape (ny, n, n)
        except:
            print("The cho_factor meet singular matrix, now add damping...")
            K += th.eye(K.shape[1]).unsqueeze(0).repeat(m, 1, 1).to(device) * 1e-6
            u = th.cholesky(K) # u has shape (ny, n, n)
        
        Y = Y.permute(1, 0)
        Y = Y.unsqueeze(2)
        self.alpha = th.cholesky_solve(Y, u) # (ny, n, 1) solve ny linear system independently
        self.L = u # shape (ny, n, n)
        
        # print the margianl likelyhood
        # Y (ny, n, 1), alpha (ny, n, 1), L (ny, n, n)
        diagonal_term = th.log(th.diagonal(self.L, dim1=1, dim2=2)).sum(dim=1)
        evidence = - 0.5 * th.einsum("ijk,ijk->i", Y, self.alpha) - diagonal_term - n / 2 * th.log(2*th.tensor([th.pi]).to(device))
        evidence = evidence.sum(axis=-1)
        print("The evidence is: ", evidence)
        del K, u, evidence
        th.cuda.empty_cache()
        
    @staticmethod
    def evidence(kernel, X, Y):
        n = X.shape[0]
        m = Y.shape[1] # output dimension

        K = kernel(X, X) # K has shape (ny, n, n)
        try:
            u = th.cholesky(K) # u has shape (ny, n, n)
        except:
            K += th.eye(K.shape[1]).unsqueeze(0).repeat(m, 1, 1).to(device) * 1e-6
            u = th.cholesky(K) # u has shape (ny, n, n)
            
        Y = Y.permute(1, 0)
        Y = Y.unsqueeze(2)

        alpha = th.cholesky_solve(Y, u) # (ny, n, 1) solve ny linear system independently
        L = u # shape (ny, n, n)
        
        # print the margianl likelyhood
        # Y (ny, n, 1), alpha (ny, n, 1), L (ny, n, n)
        diagonal_term = th.log(th.diagonal(L, dim1=1, dim2=2)).sum(dim=1)
        evidence = - 0.5 * th.einsum("ijk,ijk->i", Y, alpha) - diagonal_term - n / 2 * th.log(2*th.tensor([th.pi]).to(device))
        evidence = evidence.sum(axis=-1)
        del K, u, alpha, L, diagonal_term
        th.cuda.empty_cache()
        return evidence
    
    def predict(self, x, return_var=False):
        '''
        '''
        if len(x.shape) == 1:
            # in case the data is 1-d
            x = x.reshape(-1,1)
            
        k = self.kernel(x, self._X) # (ny, n_*, n), alpha: (ny, n, 1)
        mean = th.einsum("ijk,ikb->ji", k, self.alpha)
        if return_var:
            k = k.permute(0,2,1)
            v = th.triangular_solve(k, self.L, upper=False)[0] # (ny, n, n_*)
            v = v.permute(2, 0, 1) # (n_*, ny, n)
            prior_std = self.kernel(x,x,diag=True) # the diag in kernel base class changed. (ny, n_*)
            var = prior_std.T - th.einsum("ijk,ijk->ij", v, v)
            del k, v, prior_std
            th.cuda.empty_cache()
            return mean, var.reshape(-1,self.kernel.output_dim)
        else:
            del k
            th.cuda.empty_cache()
            return mean
        
if __name__ == "__main__":
    # test
    import matplotlib.pyplot as plt
    from jylearn.kernel.kernels import RBF, White, Matern, DotProduct, RQK, Constant
    import numpy as np
    from torch.nn import MSELoss
    Loss = MSELoss()
    np.random.seed(0)
    th.manual_seed(0)
    
    l = np.ones([1, 2]) * 0.5
    sigma = np.array([1., 1.])
    c = np.array([0.1, 0.1])
    
    kernel = White(c=c, dim_in=1, dim_out=2) + RBF(l=l, sigma=sigma, dim_in=1, dim_out=2)
    gpr = ExactGPR(kernel=kernel)
    
    train_data_num = 90 # bug? when n=100
    X = np.linspace(-10,10,100).reshape(-1,1)
    Y = np.concatenate([np.cos(X), np.sin(X)], axis=1)
    Xtrain = np.linspace(-10,10,train_data_num).reshape(-1,1)
    Ytrain1 = np.cos(Xtrain) + np.random.randn(train_data_num, 1) * 0.3 # add state dependent noise
    Ytrain2 = np.sin(Xtrain) + np.random.randn(train_data_num, 1) * 0.3
    Ytrain = np.concatenate([Ytrain1, Ytrain2], axis=1)
    Xtrain, Ytrain, X, Y = th.from_numpy(Xtrain).to(device), th.from_numpy(Ytrain).to(device),\
        th.from_numpy(X).to(device), th.from_numpy(Y).to(device)
    
    # train
    gpr.fit(Xtrain, Ytrain, call_hyper_opt=True, lr=1e-3, epoch=2000, optimizer_type="Adam", batch_size=60)
    print( list(gpr.kernel.parameters()) )
    import time
    s = time.time()
    for i in range(50):
        mean, var = gpr.predict(X, return_var=True)
    e = time.time()
    print("The time for each pred: %.5f" % ((e-s)/100))
    X = X.detach().cpu().numpy()
    Y = Y.detach().cpu().numpy()
    mean = mean.detach().cpu().numpy()
    var = var.detach().cpu().numpy()
    Xtrain, Ytrain = Xtrain.detach().cpu().numpy(), Ytrain.detach().cpu().numpy()
    plt.figure(figsize=[6,8])
    plt.subplot(211)
    plt.plot(X, mean[:,0], label="mean")
    plt.plot(X, mean[:,0] + 1.96*var[:,0], '-.r', label="var")
    plt.plot(X, mean[:,0] - 1.96*var[:,0], '-.r')
    plt.plot(X, Y[:,0], label="GroundTueth")
    plt.plot(Xtrain, Ytrain[:,0], 'rx', label="data", alpha=0.4)
    plt.grid()
    plt.ylabel("Output 1")
    
    plt.subplot(212)
    plt.plot(X, mean[:,1], label="mean")
    plt.plot(X, mean[:,1] + 1.96*var[:,1], '-.r', label="var")
    plt.plot(X, mean[:,1] - 1.96*var[:,1], '-.r')
    plt.plot(X, Y[:,1], label="GroundTueth")
    plt.plot(Xtrain, Ytrain[:,1], 'rx', label="data", alpha=0.4)
    plt.grid()
    plt.xlabel("Input")
    plt.ylabel("Output 2")
    plt.legend()
    plt.tight_layout()
    plt.show()