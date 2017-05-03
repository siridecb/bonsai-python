import time
import requests
import json
import urllib
import logging
import re

import configparser
import os

import sys
import types
import random

# import asyncio
# import websockets

# protobuf
from google.protobuf.text_format import MessageToString
from bonsai.protocols import BrainServerProtocol, BrainServerSimulatorProtocol
from bonsai.protocols import BrainServerGeneratorProtocol

from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator
from bonsai.proto.generator_simulator_api_pb2 import SimulatorToServer

from bonsai.common.message_builder import reconstitute
from bonsai.common.state_to_proto import convert_state_to_proto

from bonsai import run_for_training_or_prediction
from bonsai import simulator

logger = logging.getLogger('brain')

# constants for brain state
INKLING_LOADED = 'Inkling Loaded'
NOT_STARTED = 'Not Started'
STARTING = 'Starting'
IN_PROGRESS = 'In Progress'
COMPLETED = 'Completed'
FINISHING = 'Finishing'

def log_response(res):

	# load json, if any...
	try: dump = json.dumps(res.json(), indent=4, sort_keys=True)
	except: dump = "{}"

	logger.debug("url: {method} {url}\n\tstatus: {status}\n\tjson: {json}"\
		.format(method=res.request.method, url=res.url, status=res.status_code, json=dump) )
	pass

# a bonsai connection configuration object
class BonsaiConfig:
	def __repr__(self):
		return "{user} {apikey} {server}".format(
			user=self.user,
			apikey=self.apikey,
			server=self.server )

	def __init__(self, apikey=None, user=None, server=None, profile=None):
		self.user = None
		self.apikey = None
		self.server = None
		
		# internal
		if apikey is not None: self.apikey = apikey
		if user   is not None: self.user = user
		if server is not None: self.server = server

		# local dir
		self._load_config('./.bonsai', profile)

		# global dir
		self._load_config('~/.bonsai', profile)
		pass

	def _load_config(self, path, profile):
		config = configparser.ConfigParser()
		config.read(os.path.expanduser(path))
		
		# let the profile override the default
		def expand(key, var, profile):
			if var is not None:
				return var

			try:
				if profile is None:
					profile = config['DEFAULT']['profile']
				var = config[profile][key]
			except:
				try:
					var = config['DEFAULT'][key]
				except:
					pass
			return var

		self.user = expand('username', self.user, profile)
		self.apikey = expand('accesskey', self.apikey, profile)
		self.server = expand('url', self.server, profile)
		return

	def request_header(self):
		return {'Authorization': self.apikey}

	# return the URL for a given brain for a given config
	def brain_url(self, name):
		return "{server}/v1/{user}/{name}".format(
			server=self.server,
			user=self.user,
			name=urllib.parse.quote(name)
			)


def get_brains(config):
	url = "{server}/v1/{user}".format(server=config.server, user=config.user)
	r = requests.get(url, headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		{
		    "brains": [
		        {
		            "last_modified": "2017-04-02T01:15:49.198000Z", 
		            "name": "baz2", 
		            "state": "Not Started", 
		            "url": "/v1/mikest/baz2", 
		            "version": 0
		        }, 
		        {
		            "last_modified": "2017-02-23T21:03:47.718000Z", 
		            "name": "other", 
		            "state": "Complete", 
		            "url": "/v1/mikest/other", 
		            "version": 2
		        }, 
		        {
		            "last_modified": "2017-04-03T18:19:46.786000Z", 
		            "name": "tinman", 
		            "state": "Inkling Loaded", 
		            "url": "/v1/mikest/tinman", 
		            "version": 1
		        }, 
		        {
		            "last_modified": "2017-04-03T19:19:48.971000Z", 
		            "name": "tinman2", 
		            "state": "Not Started", 
		            "url": "/v1/mikest/tinman2", 
		            "version": 0
		        }
		    ], 
		    "datasets": [], 
		    "user": "mikest"
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	pass


# request the brain info 
def get_info(address):
	name, config = address
	# request brain
	r = requests.get(url=config.brain_url(name), headers=config.request_header())
	log_response(r)

	# parse on success
	if r.ok:
		""" Example:
		{
			"name": "other",
			"user": "mikest",
			"versions":
				[
					{
						"url": "/v1/mikest/other/2",
						"version": 2
					},
					{
						"url": "/v1/mikest/other/1",
						"version": 1
					}
				],
			"description": ""
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	pass


def get_status(address):
	name, config = address

	# request brain
	r = requests.get(url=config.brain_url(name) + "/status", headers=config.request_header())
	log_response(r)

	# parse on success
	if r.ok:
		""" Example:
		{
			u'episode': 0,
			u'objective_score': 0.0,
			u'models': 1,
			u'episode_length': 0,
			u'iteration': 0,
			u'state': u'Complete',
			u'name': u'other',
			u'simulator_loaded': False,
			u'user': u'mikest',
			u'concepts':
				[
					{
						u'concept_name': u'height',
						u'objective_name': u'???',
						u'training_end': u'2017-02-23T22:05:02Z',
						u'training_start': u'2017-02-23T21:05:02Z',
						u'state': u'Error'
					}
				],

			u'objective_name': u'open_ai_gym_default_objective',
			u'training_end': u'2017-02-23T23:05:05.413000Z',
			u'training_start': u'2017-02-23T21:04:58.179000Z'
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	pass

# upload inkling, compile it, and return compilation results
def set_inkling(address, inkling=None):
	name, config = address

	params = { 'ink_content': inkling }
	url = config.brain_url(name) + "/ink"
	r = requests.post(url, json=params, headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		{
			u'url': u'/v1/mikest/tinman',
			u'ink_compile':
			{
				u'errors':[],
				u'success': True,
				u'compiler_version': u'1.8.24',
				u'warnings':
				[
						u'Inkling compiler encountered warnings and/or other messages.',
						u'Warning. At line 7, column 9, the default range ... integer type has a set size capped at 16K'
				]
			},
			u'name': u'tinman',
			u'description': u'if i only had a heart'
		}
		"""
		return r.json()
	else:
		# probably a compilation error...
		if r.status_code == 400:
			print(r.json()['error'])
		r.raise_for_status()
	return

# download the currently loaded inkling, no version means download latest
def get_inkling(address, version):
	name, config = address

	url = config.brain_url(name) + "/{version}/ink".format(version=version)
	r = requests.get(url, headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		{
			u'compiler_version': u'1.8.23',
			u'inkling': u'schema GameState\n Float32 cos_theta0,\n Float32 sin_theta0,\n...etc'
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	return

# get status on the current sim
def get_sims(address):
	name, config = address

	url = config.brain_url(name) + "/sims"
	r = requests.get(url, headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		{
			u'compiler_version': u'1.8.23',
			u'inkling': u'schema GameState\n Float32 cos_theta0,\n Float32 sin_theta0,\n...etc'
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	return


# start a new training session, will create a new brain version
def start_training(address):
	name, config = address

	# request brain
	r = requests.put(url=config.brain_url(name) + "/train", headers=config.request_header())
	log_response(r)
	if r.ok:
		"""
		{
		    "brain_url": "/v1/mikest/tinman/2", 
		    "compiler_version": "1.8.24", 
		    "name": "tinman", 
		    "simulator_connect_url": "/v1/mikest/tinman/sims/ws", 
		    "simulator_predictions_url": "/v1/mikest/tinman/2/predictions/ws", 
		    "user": "mikest", 
		    "version": 2
		}
		"""
		return r.json()
	else:
		r.raise_for_status()
	return

# stop training, will prepare the current version for predictions
def stop_training(address):
	name, config = address

	# request brain
	r = requests.put(url=config.brain_url(name) + "/stop", headers=config.request_header())
	log_response(r)
	if r.ok:
		"""
		"""
		return r.json()
	else:
		r.raise_for_status()
	return

	return

# update the brain description
def edit(address, description):
	name, config = address

	# params = {u'description':description}
	# print(json.dumps(params))
	# r = requests.put(self.base_url(), data=json.dumps(params), headers=self.config.api_request_header())
	# if r.ok:
	# 	print("Updated descriptiong for {name}".format(name=self.name))
	# else:
	# 	print("Failed to update description for {name} {error}".format(name=self.name, error=r.status_code))
	# 	print(r.json())
	return

# delete the brain from the server
def delete(address):
	name, config = address

	r = requests.delete(config.brain_url(name), headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		No JSON
		"""
	else:
		r.raise_for_status()
	return



# create a new brain on the server
def create(address, description=None):
	name, config = address

	url = "{server}/v1/{user}/brains".format(server=config.server, user=config.user)
	params = { 'name':name, 'description':description }
	r = requests.post(url, json=params, headers=config.request_header())
	log_response(r)

	if r.ok:
		"""
		{
		    "description": null, 
		    "name": "tinman", 
		    "url": "/v1/admin/tinman"
		}
		"""

		# return as an address
		return (name, config)
	else:
		r.raise_for_status()
	return


class Brain:
	def __init__(self, address, inkling=None, file=None):
		self.name, self.config = address
		self.address = address
		self.state = None
		self.latest_version = 0
		self.inkling = inkling
		self.objective_name = None
		self.simulator_name = None
		self.ws = None

		# attempt to get the state for the brain
		json = None
		try:
			self.refresh_status()

		# couldn't get state because of a 404?
		except requests.HTTPError as err:
			if err.response.status_code == 404:
				# create the new brain... and get its status
				new = create(self.address)
				print('Created new brain: ' + new[0])
				self.refresh_status()

		# # if the server is started, stop it
		# if self.state == IN_PROGRESS:
		# 	self.stop_training()

		# now load the inkling
		if self.inkling is not None or file is not None:
			# prefer file over inkling if both exist
			if file is not None:
				print('Read inkling file "{file}"...'.format(file=file))
				with open(file, 'r') as f:
					self.inkling = f.read()

			# upload inkling text
			if self.state == NOT_STARTED and self.inkling is not None:
				print('Loading inkling...')
				set_inkling(self.address, self.inkling)
		
		else:
			self.inkling = get_inkling(self.address, self.latest_version)['inkling']

		# regex out the simulator name from the inkling...
		found = re.search(r'\with\ssimulator\s([a-zA-Z_]+)', self.inkling)
		self.simulator_name = found.group(1)

		print('Using simulator name: ' + self.simulator_name)
		pass


	def refresh_status(self):
		logger.debug('Getting {brain} info...'.format(brain=self.name))
		info = get_info(self.address)

		if len(info['versions']) > 0:
			self.latest_version = info['versions'][0]['version']
		else:
			self.latest_version = 0

		logger.debug('...using version {version}'.format(version=self.latest_version))

		logger.debug('Getting status...')		
		status = get_status(self.address)
		self.state = status['state']
		self.objective_name = status['objective_name']

		logger.debug('State is {state}, reward function is {objective_name}'.format(state=self.state, objective_name=self.objective_name))
		pass


	def stop_training(self):
		# try to stop training for 20 seconds
		delay = 0.5
		while delay < 20:
			self.refresh_status()

			# already stopped
			if self.state == COMPLETED:
				break

			# stop if running
			if self.state == IN_PROGRESS:
				stop_training(self.address)

			# stopping...
			if delay < 1:
				print("Brain is " + self.state, end='')
			else:
				print('.', end='')

			# wait a little bit before polling status again...
			time.sleep(delay)
			delay += 2

		print('\n')

		# if we couldn't stop, raise
		if self.state == COMPLETED:
			raise Exception('Failed to stop brain ' + self.name + ' for training')

	# start up training and return when the server is read to connect a simulator
	def start_training(self):

		# try to connect for 20 seconds
		print('Starting training', end='', flush=True)
		delay = 0.5
		while delay < 20:
			self.refresh_status()

			# already started
			if self.state == IN_PROGRESS:
				break

			# not started? start...
			if self.state != IN_PROGRESS and self.state != STARTING:
				print('!', end='', flush=True)
				start_training(self.address)

			# wait a little bit before polling status again...
			time.sleep(delay)
			delay += 2

			# mark the end of this loop...
			print('.', end='', flush=True)

		# if we couldn't connect, raise
		if self.state != IN_PROGRESS:
			raise Exception('failed to start up brain ' + self.name + ' for training')
		else:
			print('\nIn Progress.')
		pass



class Simulation(simulator.Simulator):
	def __init__(self, brainObj):
		simulator.Simulator.__init__(self)
		self.brain = brainObj
		self.sim_name = self.brain.simulator_name
		self.clientState = None
		self.properties = None
		self.terminal = False
		self.reward = 0.

		print('Starting...')
		return

	def start_training(self):
		try:
			sys.argv.remove('--predict')
		except:
			pass

		# start the training session on the server
		self.brain.start_training()

		sys.argv.append('--access-key')
		sys.argv.append(self.brain.config.apikey)
		
		# sys.argv.append('--train-brain')
		# sys.argv.append(self.brain.name)
		
		sys.argv.append('--brain-url')
		sys.argv.append("ws" + self.brain.config.brain_url(self.brain.name)[4:] + "/sims/ws")

		# print(self.brain.simulator_name)
		# print(sys.argv)

		if self.brain.objective_name is not None:
			setattr(self, self.brain.objective_name, self.reward_function)
		else:
			print('No objective defined...')

		run_for_training_or_prediction(name=self.brain.simulator_name, simulator_or_generator=self)
		return

	def start_prediction(self):
		try:
			sys.argv.remove('--predict')
		except:
			pass

		sys.argv.append('--access-key')
		sys.argv.append(self.brain.config.apikey)
		
		# sys.argv.append('--predict-brain')
		# sys.argv.append(self.brain.name)
		
		# sys.argv.append('--predict-version')
		# sys.argv.append(str(self.brain.latest_version))

		sys.argv.append('--brain-url')
		#sys.argv.append('ws://localhost:32936/v1/admin/test/3/predictions/ws')
		sys.argv.append("ws" + self.brain.config.brain_url(self.brain.name)[4:] + "/{version}/predictions/ws".format(version=self.brain.latest_version))

		print(self.brain.simulator_name)

		self.brain.stop_training()

		run_for_training_or_prediction(name=self.brain.simulator_name, simulator_or_generator=self)
		return

	def start(self):
		logger.debug('start')
		return

	def stop(self):
		logger.debug('stop')
		return

	def reset(self):
		logger.debug('reset')
		if self.clientState is not None:
			self.episode_stop()

		self.clientState = None
		self.terminal = False
		self.reward = 0.	#...don't reset the reward, it gets set after the state is reset
		return

	def advance(self, actions):
		logger.debug('advance' + str(actions))

		# according to @rstory if our last get_state returned is_terminal=True we should reset tht sim
		# and ignore the passed in actions for this advance.
		if self.terminal is True:
			self.reset()
		else:
			self.clientState, self.terminal, self.reward = self.simulate(self.clientState, actions, self.brain.objective_name)
		return

	def set_properties(self, **kwargs):
		logger.debug('set_properties' + str(kwargs))
		self.properties = kwargs
		return

	def get_state(self):
		logger.debug('get_state')

		# initial start happens on the first get_state call
		if self.clientState is None:
			self.clientState = self.episode_start(self.properties)

		# save the state from this or last round before we reset
		current = simulator.SimState(state=self.clientState, is_terminal=self.terminal)

		# return the last state
		return current

	def reward_function(self):
		logger.debug('reward_function')
		return self.reward

	"""
	called when an episode should be started, if properties is not None
	then it contains the episode initialization parameters, otherwise the defaults
	should be used.

	client should start up their simulation with the initialization parameters and
	return the initial state
	"""
	def episode_start(self, properties=None):
		return self.clientState

	"""
	run a step in the simulation, using the current action and reward function
	return the reward for the function if one is specified, or None if was wasn't
	"""
	def simulate(self, previousState, action, objective=None ):
	 	return self.reward, self.clientState, self.terminal

	"""
	called when the episode ends, before the next episide starts
	or if the episode was cancelled before it finished
	"""
	def episode_stop(self):
		return