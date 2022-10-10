### JY's machine learning and control workspace, 
The **SARCOS** dataset, which is intended for a regression problem of robot inverse dynamics, is regarded as the benchmark of ML.  
The gym **pendulum** environment is chosen to be the benchmark of control project.
  
Finished functions:
#### Machine learning  
| Approach      | MSE           |
| ------------- |:-------------:|
| Ridge + feature      | 2.207 |
| MLP      | 1.469      |
| ... |       |
#### Control  
| Approach        | Reward Mean (50 runs) | Reward Variance|
| ------------- |:-------------:|:-------------:|
| iLQR      | -305.57 |   38239.82    |
| SAC | -144.04 | 8377.89 |
| ...| | |

Note: In SAC(soft actor-critic) the reinforcement learning package stablebaseline3 was used to compare with various control strategies. The training ran for 50k timesteps, to a convergence of the epi reward. The cost matrices in iLQR are troublesome to tune by hand. Therefore, its performance is just ok, but no problem to swing up and stabilize.
