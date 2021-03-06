# -*- coding: utf-8 -*-
"""
Deep Q-network implementation with chainer and rlglue
Copyright (c) 2015  Naoto Yoshida All Right Reserved.
"""
import argparse
import copy

import pickle
import numpy as np
import scipy.misc as spm

from chainer import cuda, FunctionSet, Variable, optimizers
import chainer.functions as F



    
class DQN_class:
    # Hyper-Parameters
    gamma = 0.99  # Discount factor
    initial_exploration = 100#10**4  # Initial exploratoin. original: 5x10^4
    #replay_size = 1000  # Replay (batch) size
    target_model_update_freq = 10**4  # Target update frequancy. original: 10^4
    #data_size = 10**5  # Data size of history. original: 10^6
    
    def __init__(self, gpu_id, state_dimention,batchsize,historysize, enable_controller,arch):
        self.gpu_id = gpu_id
        self.num_of_actions = len(enable_controller)
        self.enable_controller = enable_controller  # Default setting : "Pong"
        self.arch = arch
        self.replay_size = batchsize
        self.data_size = historysize
        
        self.state_dimention = state_dimention
        print "Initializing DQN..."
        #	Initialization of Chainer 1.1.0 or older.
        #        print "CUDA init"
        #        cuda.init()

        print "Model Building"
        #self.model = dnn_6_new.Q_DNN(self.state_dimention,200,self.num_of_actions)
        self.model = self.set_model(self.arch,self.state_dimention,200,self.num_of_actions)
        self.model.to_gpu(self.gpu_id)
        
        
        self.model_target = copy.deepcopy(self.model)

        print "Initizlizing Optimizer"
        self.optimizer = optimizers.RMSpropGraves(lr=0.00025, alpha=0.95, momentum=0.95, eps=0.0001)
        self.optimizer.setup(self.model)

        # History Data :  D=[s, a, r, s_dash, end_episode_flag]
        self.D = [np.zeros((self.data_size, 1, self.state_dimention), dtype=np.float32),
                  np.zeros(self.data_size, dtype=np.int8),
                  np.zeros((self.data_size, 1), dtype=np.float32),
                  np.zeros((self.data_size, 1, self.state_dimention), dtype=np.float32),
                  np.zeros((self.data_size, 1), dtype=np.bool)]

    def forward(self, state, action, Reward, state_dash, episode_end):
        num_of_batch = state.shape[0]
        
        Q = self.model.Q_func(state)  # Get Q-value

        # Generate Target Signals
        tmp = self.model_target.Q_func(state_dash)  # Q(s',*)
        tmp = list(map(np.max, tmp.data.get()))  # max_a Q(s',a)
        max_Q_dash = np.asanyarray(tmp, dtype=np.float32)
        target = np.asanyarray(Q.data.get(), dtype=np.float32)

        for i in xrange(num_of_batch):
            if not episode_end[i][0]:
                tmp_ = Reward[i] + self.gamma * max_Q_dash[i]
            else:
                tmp_ = Reward[i]
            #print action
            action_index = self.action_to_index(action[i])
            target[i, action_index] = tmp_

        # TD-error clipping
        td = Variable(cuda.to_gpu(target,self.gpu_id)) - Q  # TD error
        td_tmp = td.data + 1000.0 * (abs(td.data) <= 1)  # Avoid zero division
        td_clip = td * (abs(td.data) <= 1) + td/abs(td_tmp) * (abs(td.data) > 1)

        zero_val = Variable(cuda.to_gpu(np.zeros((self.replay_size, self.num_of_actions), dtype=np.float32),self.gpu_id))
        loss = F.mean_squared_error(td_clip, zero_val)
        return loss, Q

    def stockExperience(self, time,
                        state, action, reward, state_dash,
                        episode_end_flag):
        data_index = time % self.data_size

        if episode_end_flag is True:
            #print state,action,reward
            self.D[0][data_index] = state
            self.D[1][data_index] = action
            self.D[2][data_index] = reward
        else:
            #print state, action,reward,state_dash
            self.D[0][data_index] = state
            self.D[1][data_index] = action
            self.D[2][data_index] = reward
            self.D[3][data_index] = state_dash
        self.D[4][data_index] = episode_end_flag

    def experienceReplay(self, time):

        if self.initial_exploration < time:
            # Pick up replay_size number of samples from the Data
            if time < self.data_size:  # during the first sweep of the History Data
                replay_index = np.random.randint(0, time, (self.replay_size, 1))
            else:
                replay_index = np.random.randint(0, self.data_size, (self.replay_size, 1))

            s_replay = np.ndarray(shape=(self.replay_size, 1, self.state_dimention), dtype=np.float32)
            a_replay = np.ndarray(shape=(self.replay_size, 1), dtype=np.int8)
            r_replay = np.ndarray(shape=(self.replay_size, 1), dtype=np.float32)
            s_dash_replay = np.ndarray(shape=(self.replay_size, 1, self.state_dimention), dtype=np.float32)
            episode_end_replay = np.ndarray(shape=(self.replay_size, 1), dtype=np.bool)
            for i in xrange(self.replay_size):
                s_replay[i] = np.asarray(self.D[0][replay_index[i]], dtype=np.float32)
                a_replay[i] = self.D[1][replay_index[i]]
                r_replay[i] = self.D[2][replay_index[i]]
                s_dash_replay[i] = np.array(self.D[3][replay_index[i]], dtype=np.float32)
                episode_end_replay[i] = self.D[4][replay_index[i]]

            s_replay = cuda.to_gpu(s_replay,self.gpu_id)
            s_dash_replay = cuda.to_gpu(s_dash_replay,self.gpu_id)

            # Gradient-based update
            self.model.cleargrads()
            self.model_target.cleargrads()#???????????????????????????????????????
            loss, _ = self.forward(s_replay, a_replay, r_replay, s_dash_replay, episode_end_replay)
            loss.backward()
            self.optimizer.update()

    
        
    
    def e_greedy(self, state, epsilon):
        if self.arch == 'dnn_6_BN':
            Q = self.model.Q_func(state,train=False)
        else:
            Q = self.model.Q_func(state)
            
        Q = Q.data

        if np.random.rand() < epsilon:
            index_action = np.random.randint(0, self.num_of_actions)
            #print "RANDOM"
        else:
            index_action = np.argmax(Q.get())
            #print "GREEDY"
        
        return self.index_to_action(index_action), Q

    def target_model_update(self):
        self.model_target = copy.deepcopy(self.model)

    def index_to_action(self, index_of_action):
        return self.enable_controller[index_of_action]

    def action_to_index(self, action):
        return self.enable_controller.index(action)
    
    def save_model(self, folder_name, epoch):
        print 'save model'
        self.model.to_cpu()
        with open(folder_name+'model'+str(epoch),'wb') as o:
            pickle.dump(self.model,o)
        self.model.to_gpu(self.gpu_id)
        self.optimizer.setup(self.model)

    def load_model(self, model):
        with open(model, 'rb') as m:
            print "open " + model
            self.model = pickle.load(m)
            print 'load model'
            self.model.to_gpu(self.gpu_id)
            
    def get_model_copy(self):
        return copy.deepcopy(self.model)
        
    def model_to_gpu(self):
        self.model.to_gpu(self.gpu_id)
    
    def set_model(self, arch, input_num, hidden_num, output_num):
        if arch == 'dnn_6_f':
            import dnn_6_f
            model =  dnn_6_f.Q_DNN(input_num,hidden_num,output_num)
        elif arch == 'dnn_6_BN':
            import dnn_6_BN
            model = dnn_6_BN.Q_DNN(input_num,hidden_num,output_num)
        elif arch == 'dnn_6_new':
            import dnn_6_new
            model = dnn_6_new.Q_DNN(input_num,hidden_num,output_num)
        elif arch == 'dnn_6_hidout':
            import dnn_6_hidout
            model = dnn_6_hidout.Q_DNN(input_num,hidden_num,output_num)
            
        return model
        
class dqn_agent():  # RL-glue Process
    #lastAction = Action()
    policyFrozen = False
    learning_freq = 2#??????????????????????????????
    
    def __init__(self,gpu_id,enable_controller,state_dimention=0,batchsize=0,historysize=0,epsilon_discount_size=0,arch='dnn_6_f'):
        self.gpu_id = gpu_id
        self.enable_controller = enable_controller
        self.state_dimention = state_dimention
        self.batchsize = batchsize
        self.historysize = historysize
        self.epsilon_discount_size = epsilon_discount_size
        self.arch = arch

    def agent_init(self):
        # Some initializations for rlglue
        #self.lastAction = Action()

        self.time = 0
        self.learned_time = 0
        self.epsilon = 1.0  # Initial exploratoin rate
        self.max_Q_list = []
        self.reward_list = []
        self.Q_recent = 0
        
        # Pick a DQN from DQN_class
        self.DQN = DQN_class(gpu_id=self.gpu_id,state_dimention=self.state_dimention,batchsize=self.batchsize,historysize=self.historysize,enable_controller=self.enable_controller,arch=self.arch)  # default is for "Pong".

    def agent_start(self, observation):

        
        # Initialize State
        self.state = observation
        state_ = cuda.to_gpu(np.asanyarray(self.state, dtype=np.float32),self.gpu_id)

        # Generate an Action e-greedy
        action, Q_now = self.DQN.e_greedy(state_, self.epsilon)
        self.Q_recent = Q_now.get()[0]
        # Update for next step
        self.lastAction = action
        self.last_state = self.state.copy()
        self.last_observation = observation.copy()
        self.max_Q_list.append(np.max(self.Q_recent))
        
        return action
        
    def agent_step(self, reward, observation):

        self.state = observation
        state_ = cuda.to_gpu(np.asanyarray(self.state, dtype=np.float32),self.gpu_id)

        # Exploration decays along the time sequence
        if self.policyFrozen is False:  # Learning ON/OFF
            if self.DQN.initial_exploration < self.time:
                self.epsilon -= 1.0/self.epsilon_discount_size
                if self.epsilon < 0.1:
                    self.epsilon = 0.1
                eps = self.epsilon
            else:  # Initial Exploation Phase
                #print "Initial Exploration : %d/%d steps" % (self.time, self.DQN.initial_exploration)
                eps = 1.0
        else:  # Evaluation
                #print "Policy is Frozen"
                #eps = 0.1
                eps = 0.05
        # Generate an Action by e-greedy action selection
        action, Q_now = self.DQN.e_greedy(state_, eps)
        self.Q_recent = Q_now.get()[0]

        self.max_Q_list.append(np.max(self.Q_recent))
        self.reward_list.append(reward)

        # Learning Phase
        if self.policyFrozen is False:  # Learning ON/OFF
            if (self.time % self.learning_freq) == 0:
                self.DQN.stockExperience(self.learned_time, self.last_state, self.lastAction, reward, self.state, False)
                self.DQN.experienceReplay(self.learned_time)
                self.learned_time += 1

        # Target model update
        if self.DQN.initial_exploration < self.learned_time and np.mod(self.learned_time, self.DQN.target_model_update_freq) == 0:
            #print "########### MODEL UPDATED ######################"
            self.DQN.target_model_update()
            
        # Simple text based visualization
        #print ' Time Step %d /   ACTION  %d  /   REWARD %.4f   / EPSILON  %.6f  /   Q_max  %3f' % (self.time, action, reward, eps, np.max(Q_now.get()))
        #print Q_now.get()

        # Updates for next step
        self.last_observation = observation.copy()

        if self.policyFrozen is False:
            self.lastAction = action
            self.last_state = self.state.copy()
            self.time += 1

        return action

    def agent_end(self, reward):  # Episode Terminated

        self.reward_list.append(reward)
        # Learning Phase
        if self.policyFrozen is False:  # Learning ON/OFF
            if (self.time % self.learning_freq) == 0:
                self.DQN.stockExperience(self.learned_time, self.last_state, self.lastAction, reward, self.last_state, True)
                self.DQN.experienceReplay(self.learned_time)
                self.learned_time += 1

        # Target model update
        if self.DQN.initial_exploration < self.learned_time and np.mod(self.learned_time, self.DQN.target_model_update_freq) == 0:
            #print "########### MODEL UPDATED ######################"
            self.DQN.target_model_update()
            
            
        # Simple text based visualization
        #print '  REWARD %.1f   / EPSILON  %.5f' % (np.sign(reward), self.epsilon)

        # Time count
        if self.policyFrozen is False:
            self.time += 1
    
    def init_max_Q_list(self):
        self.max_Q_list = []
        
    def init_reward_list(self):
        self.reward_list = []
        
    def get_average_Q(self):
        return sum(self.max_Q_list)/len(self.max_Q_list)
        
    def get_average_reward(self):
        return sum(self.reward_list)/len(self.reward_list)
    
    def get_variance_Q(self):
        return np.var(np.array(self.max_Q_list))
        
    def get_varance_reward(self):
        return np.var(np.array(self.reward_list))
        
    def get_learned_time(self):
        return self.learned_time
        
    def agent_cleanup(self):
        pass

    def agent_message(self, inMessage):
        if inMessage.startswith("freeze learning"):
            self.policyFrozen = True
            return "message understood, policy frozen"

        if inMessage.startswith("unfreeze learning"):
            self.policyFrozen = False
            return "message understood, policy unfrozen"

        if inMessage.startswith("save model"):
            with open('dqn_model.dat', 'w') as f:
                pickle.dump(self.DQN.model, f)
            return "message understood, model saved"


