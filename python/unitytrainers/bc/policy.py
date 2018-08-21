import logging

import numpy as np
import tensorflow as tf
from unitytrainers.bc.models import BehavioralCloningModel
from unitytrainers.policy import Policy

logger = logging.getLogger("unityagents")


class BCPolicy(Policy):
    def __init__(self, seed, brain, trainer_parameters, sess):
        """
        :param seed: Random seed.
        :param brain: Assigned Brain object.
        :param trainer_parameters: Defined training parameters.
        :param sess: TensorFlow session.
        """
        super().__init__(seed, brain, trainer_parameters, sess)

        with tf.variable_scope(self.variable_scope):
            tf.set_random_seed(seed)
            self.model = BehavioralCloningModel(
                h_size=int(trainer_parameters['hidden_units']),
                lr=float(trainer_parameters['learning_rate']),
                n_layers=int(trainer_parameters['num_layers']),
                m_size=self.m_size,
                normalize=False,
                use_recurrent=trainer_parameters['use_recurrent'],
                brain=brain)

        self.inference_dict = {'action': self.model.sample_action}
        self.update_dict = {'policy_loss': self.model.loss,
                            'update_batch': self.model.update}
        if self.use_recurrent:
            self.inference_dict['memory_out'] = self.model.memory_out

    def evaluate(self, brain_info):
        """
        Evaluates policy based on brain_info.
        :param brain_info: BrainInfo input to network.
        :return: Results of evaluation.
        """
        feed_dict = {self.model.dropout_rate: 1.0, self.model.sequence_length: 1}

        if self.use_visual_obs:
            for i, _ in enumerate(brain_info.visual_observations):
                feed_dict[self.model.visual_in[i]] = brain_info.visual_observations[i]
        if self.use_vector_obs:
            feed_dict[self.model.vector_in] = brain_info.vector_observations
        if self.use_recurrent:
            if brain_info.memories.shape[1] == 0:
                brain_info.memories = np.zeros((len(brain_info.agents), self.m_size))
            feed_dict[self.model.memory_in] = brain_info.memories
        network_output = self.sess.run(list(self.inference_dict.values()), feed_dict)
        run_out = dict(zip(list(self.inference_dict.keys()), network_output))
        return run_out

    def update(self, mini_batch, num_sequences):
        """
        Performs update on model.
        :param mini_batch: Batch of experiences.
        :param num_sequences: Number of sequences to process.
        :return: Results of update.
        """

        feed_dict = {self.model.dropout_rate: 0.5,
                     self.model.batch_size: num_sequences,
                     self.model.sequence_length: self.sequence_length}
        if self.use_continuous_act:
            feed_dict[self.model.true_action] = mini_batch['actions']. \
                reshape([-1, self.brain.vector_action_space_size[0]])
        else:
            feed_dict[self.model.true_action] = mini_batch['actions'].reshape(
                [-1, len(self.brain.vector_action_space_size)])
        if self.use_vector_obs:
            apparent_obs_size = self.brain.vector_observation_space_size * \
                                self.brain.num_stacked_vector_observations
            feed_dict[self.model.vector_in] = mini_batch['vector_observations'] \
                .reshape([-1,apparent_obs_size])
        if self.use_vector_obs:
            for i, _ in enumerate(self.model.visual_in):
                visual_obs = mini_batch['visual_observations%d' % i]
                feed_dict[self.model.visual_in[i]] = visual_obs
        if self.use_recurrent:
            feed_dict[self.model.memory_in] = np.zeros([num_sequences, self.m_size])
        network_output = self.sess.run(list(self.update_dict.values()), feed_dict=feed_dict)
        run_out = dict(zip(list(self.update_dict.keys()), network_output))
        return run_out
