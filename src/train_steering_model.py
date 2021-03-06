#!/usr/bin/env python
"""
Steering angle prediction model
"""
import os
import argparse
import json
from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten, Lambda, ELU
from keras.layers.convolutional import Convolution2D
from keras.callbacks import Callback
from keras.models import model_from_json

from server import client_generator


def gen(hwm, host, port):
  for tup in client_generator(hwm=hwm, host=host, port=port):
    X, Y, _ = tup
    Y = Y[:, -1]
    if X.shape[1] == 1:  # no temporal context
      X = X[:, -1]
    yield X, Y


#provided by comma ai
def get_base_model(time_len=1):
  ch, row, col = 3, 160, 320  # camera format

  model = Sequential()
  model.add(Lambda(lambda x: x/127.5 - 1.,
            input_shape=(ch, row, col),
            output_shape=(ch, row, col)))
  model.add(Convolution2D(16, 8, 8, subsample=(4, 4), border_mode="same"))
  model.add(ELU())
  model.add(Convolution2D(32, 5, 5, subsample=(2, 2), border_mode="same"))
  model.add(ELU())
  model.add(Convolution2D(64, 5, 5, subsample=(2, 2), border_mode="same"))
  model.add(Flatten())
  model.add(Dropout(.2))
  model.add(ELU())
  model.add(Dense(512))
  model.add(Dropout(.5))
  model.add(ELU())
  model.add(Dense(1))

  model.compile(optimizer="adam", loss="mse")

  return model

#nvidea
#https://devblogs.nvidia.com/parallelforall/deep-learning-self-driving-cars/
def get_model(time_len=1):
  #ch, row, col = 3, 160, 320  # camera format
  ch, row, col = 3, 256, 256  # camera format - todo read it in!

  model = Sequential()
  model.add(Lambda(lambda x: x/127.5 - 1.,
            input_shape=(ch, row, col),
            output_shape=(ch, row, col)))
  model.add(Convolution2D(24, 5, 5, subsample=(2, 2), border_mode="same"))
  model.add(ELU())
  model.add(Convolution2D(36, 5, 5, subsample=(2, 2), border_mode="same"))
  model.add(ELU())
  model.add(Convolution2D(48, 3, 3, subsample=(2, 2), border_mode="same"))
  model.add(ELU())
  model.add(Convolution2D(64, 3, 3, subsample=(2, 2), border_mode="same"))
  model.add(Flatten())
  model.add(Dropout(.2))
  model.add(ELU())
  model.add(Dense(512))
  model.add(Dropout(.5))
  model.add(ELU())
  model.add(Dense(256))
  model.add(ELU())
  model.add(Dense(128))
  model.add(ELU())
  model.add(Dense(1))

  model.compile(optimizer="adam", loss="mse")

  return model

class SaveCB(Callback):
  def __init__(self, output):
    self.output = output

  def on_epoch_end(self, epoch, logs={}):
    self.save_weights()
  
  def on_train_begin(self, logs={}):
    self.save_weights()

  def on_train_end(self, logs={}):
    self.save_weights()

  def save_weights(self):
    print("\nSaving model weights and configuration file.")
    path, filename = os.path.split(self.output)
    if not os.path.exists(path):
        os.makedirs(path)
    self.model.save_weights(self.output + ".keras", True)
    with open(self.output + '.json', 'w') as outfile:
      json.dump(self.model.to_json(), outfile)

def run_default_training(output, resume):
  if resume:
    with open(output + '.json', 'r') as jfile:
      model = model_from_json(json.load(jfile))
    model.compile(optimizer="adam", loss="mse")
    weights_file = output + '.keras'
    model.load_weights(weights_file)
    print 'picking up from previous training run.'
  else:
    model = get_model()
  
  model.fit_generator(
    gen(20, '127.0.0.1', port=5557),
    samples_per_epoch=10000,
    nb_epoch=200,
    validation_data=gen(20, '127.0.0.1', port=5556),
    nb_val_samples=1000,
    callbacks=[SaveCB(output)]
  )

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Steering angle model trainer')
  parser.add_argument('--host', type=str, default="localhost", help='Data server ip address.')
  parser.add_argument('--port', type=int, default=5557, help='Port of server.')
  parser.add_argument('--val_port', type=int, default=5556, help='Port of server for validation dataset.')
  parser.add_argument('--batch', type=int, default=64, help='Batch size.')
  parser.add_argument('--epoch', type=int, default=200, help='Number of epochs.')
  parser.add_argument('--epochsize', type=int, default=10000, help='How many frames per epoch.')
  parser.add_argument('--skipvalidate', dest='skipvalidate', action='store_true', help='Multiple path output.')
  parser.add_argument('--output', dest='output', default='./outputs/steering_model/steering_angle', help='output file.')
  parser.add_argument('--resume', type=str, default=None, help='Optional path to model definition json. Model weights should be on the same path.')
  parser.set_defaults(skipvalidate=False)
  parser.set_defaults(loadweights=False)
  args = parser.parse_args()

  #optionally start from a previous training run.
  if args.resume != None:
    with open(args.resume, 'r') as jfile:
      model = model_from_json(json.load(jfile))
    model.compile(optimizer="adam", loss="mse")
    weights_file = args.resume.replace('json', 'keras')
    model.load_weights(weights_file)
    print 'picking up from previous training run.'
  else:
    model = get_model()

  model.fit_generator(
    gen(20, args.host, port=args.port),
    samples_per_epoch=10000,
    nb_epoch=args.epoch,
    validation_data=gen(20, args.host, port=args.val_port),
    nb_val_samples=1000,
    callbacks=[SaveCB(args.output)]
  )

